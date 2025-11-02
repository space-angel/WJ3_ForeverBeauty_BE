"""
PostgreSQL 데이터베이스 연결 관리
psycopg2 기반 연결 풀 및 헬스체크 기능 (asyncpg 대신 사용)
"""

import asyncio
import os
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class PostgreSQLDB:
    """PostgreSQL 데이터베이스 연결 클래스 (postgres_sync 래퍼)"""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        PostgreSQL 데이터베이스 초기화
        
        Args:
            database_url: PostgreSQL 연결 URL (환경변수에서 자동 로드)
        """
        from app.database.postgres_sync import PostgreSQLSyncDB
        self._sync_db = PostgreSQLSyncDB(database_url)
        self.database_url = self._sync_db.database_url
        self._closing = False
        
    def is_supabase_connection(self) -> bool:
        """수퍼베이스 연결인지 확인"""
        return 'supabase.com' in self.database_url if self.database_url else False
    
    async def create_pool(self, min_size: int = 1, max_size: int = 3):
        """연결 풀 생성 - postgres_sync 사용"""
        if self._closing:
            raise RuntimeError("데이터베이스가 종료 중입니다")
        
        try:
            logger.info("PostgreSQL 연결 풀 생성 시작")
            self._sync_db.create_pool(min_conn=min_size, max_conn=max_size)
            logger.info(f"PostgreSQL 연결 풀 생성 완료 (min={min_size}, max={max_size})")
            return self._sync_db._pool
        except Exception as e:
            logger.error(f"PostgreSQL 연결 풀 생성 실패: {e}")
            raise
    

    
    async def close_pool(self):
        """연결 풀 종료"""
        self._closing = True
        try:
            self._sync_db.close_pool()
        except Exception as e:
            logger.debug(f"연결 풀 종료 중 오류 (무시됨): {e}")
    
    def is_pool_active(self) -> bool:
        """연결 풀이 활성 상태인지 확인"""
        return self._sync_db.is_pool_active()
    
    def is_supabase_connection(self) -> bool:
        """수퍼베이스 연결인지 확인"""
        return 'supabase.com' in self.database_url if self.database_url else False
    
    async def optimize_for_supabase(self):
        """수퍼베이스 무료 플랜 최적화 - 단순화"""
        if not self.is_supabase_connection():
            return
        
        logger.info("수퍼베이스 연결 최적화 시작")
        
        # 단순한 풀 생성
        await self.create_pool(min_size=1, max_size=1)
        
        logger.info("수퍼베이스 무료 플랜 최적화 완료")
    
    @asynccontextmanager
    async def get_connection(self):
        """연결 풀에서 연결 획득 - 동시성 문제 해결"""
        connection = None
        
        # 풀 상태 확인 (락 없이 빠른 확인)
        if not self.is_pool_active():
            logger.warning("연결 풀이 비활성 상태")
            raise asyncpg.ConnectionDoesNotExistError("연결 풀이 비활성 상태입니다")
        
        try:
            # 연결 획득 (간단하고 빠르게)
            connection = await self._pool.acquire()
            
            # 연결 상태 확인
            if connection.is_closed():
                raise asyncpg.ConnectionDoesNotExistError("Connection is closed")
            
            # 성공적으로 연결 획득
            yield connection
            
        except Exception as e:
            logger.warning(f"연결 획득 실패: {e}")
            # 연결 정리
            if connection:
                try:
                    await self._pool.release(connection, close=True)
                except:
                    pass
                connection = None
            raise
                
        finally:
            # 연결 반환 (안전한 정리)
            if connection:
                try:
                    if not connection.is_closed() and self._pool and not self._pool._closed:
                        await self._pool.release(connection)
                except Exception as e:
                    logger.debug(f"연결 반환 중 오류 (무시됨): {e}")
    
    async def execute_query(self, query: str, *args) -> List[Dict[str, Any]]:
        """쿼리 실행 및 결과 반환"""
        return await self._sync_db.execute_query(query, *args)
    
    async def execute_single(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """단일 결과 쿼리 실행"""
        results = await self.execute_query(query, *args)
        return results[0] if results else None
    
    async def execute_scalar(self, query: str, *args) -> Any:
        """스칼라 값 반환 쿼리 실행"""
        # 연결 풀 상태 확인 및 재생성
        if not self.is_pool_active():
            await self.create_pool()
        
        async with self.get_connection() as conn:
            try:
                return await conn.fetchval(query, *args)
            except Exception as e:
                logger.error(f"스칼라 쿼리 실행 오류: {e}")
                raise
    
    async def execute_command(self, query: str, *args) -> str:
        """INSERT/UPDATE/DELETE 명령 실행"""
        async with self.get_connection() as conn:
            try:
                return await conn.execute(query, *args)
            except Exception as e:
                logger.error(f"명령 실행 오류: {e}")
                raise
    
    async def execute_many(self, query: str, args_list: List[tuple]) -> None:
        """배치 실행"""
        async with self.get_connection() as conn:
            try:
                await conn.executemany(query, args_list)
            except Exception as e:
                logger.error(f"배치 실행 오류: {e}")
                raise
    
    async def test_connection(self) -> bool:
        """데이터베이스 연결 테스트"""
        return self._sync_db.test_connection()
    
    async def get_health_status(self) -> Dict[str, Any]:
        """데이터베이스 헬스체크"""
        try:
            start_time = asyncio.get_event_loop().time()
            
            async with self.get_connection() as conn:
                # 기본 연결 테스트
                await conn.fetchval("SELECT 1")
                
                # 데이터베이스 정보 조회
                db_version = await conn.fetchval("SELECT version()")
                current_time = await conn.fetchval("SELECT NOW()")
                
                # 연결 풀 상태
                pool_info = {
                    'size': self._pool.get_size() if self._pool else 0,
                    'min_size': self._pool.get_min_size() if self._pool else 0,
                    'max_size': self._pool.get_max_size() if self._pool else 0,
                    'idle_size': self._pool.get_idle_size() if self._pool else 0
                }
                
                response_time = (asyncio.get_event_loop().time() - start_time) * 1000
                
                health_info = {
                    'status': 'healthy',
                    'database': self._connection_config['database'],
                    'host': self._connection_config['host'],
                    'port': self._connection_config['port'],
                    'version': db_version,
                    'current_time': current_time,
                    'response_time_ms': round(response_time, 2),
                    'pool': pool_info
                }
                
                # 수퍼베이스 무료 플랜 정보 추가
                if self.is_supabase_connection():
                    health_info['supabase_free_plan'] = True
                    health_info['connection_limit_warning'] = pool_info['size'] >= 2
                    health_info['optimization_applied'] = True
                
                return health_info
                
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'database': self._connection_config.get('database'),
                'host': self._connection_config.get('host'),
                'port': self._connection_config.get('port')
            }
    
    async def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """테이블 정보 조회"""
        query = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = $1
            ORDER BY ordinal_position
        """
        return await self.execute_query(query, table_name)
    
    async def get_table_names(self) -> List[str]:
        """모든 테이블 이름 조회"""
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """
        results = await self.execute_query(query)
        return [row['table_name'] for row in results]
    
    async def get_table_count(self, table_name: str) -> int:
        """테이블 레코드 수 조회"""
        query = f"SELECT COUNT(*) FROM {table_name}"
        return await self.execute_scalar(query)


# 전역 데이터베이스 인스턴스
_db_instance: Optional[PostgreSQLDB] = None

def get_postgres_db() -> PostgreSQLDB:
    """PostgreSQL 데이터베이스 인스턴스 반환 (싱글톤) - 안정성 강화"""
    global _db_instance
    if _db_instance is None:
        _db_instance = PostgreSQLDB()
        logger.debug("새로운 PostgreSQL 인스턴스 생성")
    return _db_instance

async def init_database():
    """데이터베이스 초기화 (애플리케이션 시작 시 호출) - 안정성 강화"""
    db = get_postgres_db()
    
    logger.info("PostgreSQL 데이터베이스 초기화 시작")
    
    # 수퍼베이스인 경우 최적화된 설정 사용
    if db.is_supabase_connection():
        logger.info("수퍼베이스 연결 감지 - 안정화된 설정 적용")
        try:
            await asyncio.wait_for(db.optimize_for_supabase(), timeout=30.0)  # 충분한 시간 제공
        except asyncio.TimeoutError:
            logger.error("수퍼베이스 초기화 시간 초과")
            raise Exception("수퍼베이스 연결 초기화 시간 초과")
        except Exception as e:
            logger.error(f"수퍼베이스 초기화 실패: {e}")
            raise
    else:
        try:
            await asyncio.wait_for(db.create_pool(), timeout=15.0)
        except asyncio.TimeoutError:
            logger.error("PostgreSQL 초기화 시간 초과")
            raise Exception("PostgreSQL 연결 초기화 시간 초과")
        except Exception as e:
            logger.error(f"PostgreSQL 초기화 실패: {e}")
            raise
    
    # 연결 테스트 (충분한 시간 제공)
    try:
        connection_test = await asyncio.wait_for(db.test_connection(), timeout=10.0)
        if connection_test:
            logger.info("PostgreSQL 데이터베이스 초기화 및 연결 테스트 완료")
        else:
            raise Exception("PostgreSQL 데이터베이스 연결 테스트 실패")
    except asyncio.TimeoutError:
        logger.error("PostgreSQL 연결 테스트 시간 초과")
        raise Exception("PostgreSQL 연결 테스트 시간 초과")
    except Exception as e:
        logger.error(f"PostgreSQL 연결 테스트 실패: {e}")
        raise

async def close_database():
    """데이터베이스 연결 종료 (애플리케이션 종료 시 호출) - 안전한 정리"""
    global _db_instance
    if not _db_instance:
        return
    
    try:
        # 이벤트 루프 상태 확인
        try:
            loop = asyncio.get_running_loop()
            if loop.is_closed():
                logger.warning("이벤트 루프가 이미 닫힘 - 강제 데이터베이스 정리")
                _db_instance = None
                return
        except RuntimeError:
            logger.warning("이벤트 루프 없음 - 강제 데이터베이스 정리")
            _db_instance = None
            return
        
        # 타임아웃을 적용한 안전한 종료
        try:
            await asyncio.wait_for(_db_instance.close_pool(), timeout=1.0)
            logger.info("데이터베이스 연결 정상 종료 완료")
        except asyncio.TimeoutError:
            logger.warning("데이터베이스 종료 시간 초과 - 강제 종료")
            # 강제 종료
            if _db_instance._pool:
                try:
                    _db_instance._pool.terminate()
                except:
                    pass
        except Exception as e:
            logger.warning(f"데이터베이스 종료 중 오류: {e}")
        
    except Exception as e:
        logger.error(f"데이터베이스 정리 중 예외: {e}")
    finally:
        # 항상 인스턴스 정리
        _db_instance = None

def get_db_session_sync():
    """동기 코드에서 사용할 수 있는 데이터베이스 세션 반환"""
    import asyncio
    
    try:
        # 현재 이벤트 루프가 있는지 확인
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 이미 실행 중인 루프가 있으면 새 스레드에서 실행
            import concurrent.futures
            import threading
            
            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    db = get_postgres_db()
                    return new_loop.run_until_complete(db.create_pool())
                finally:
                    new_loop.close()
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
        else:
            # 루프가 실행 중이 아니면 직접 실행
            db = get_postgres_db()
            return loop.run_until_complete(db.create_pool())
    except RuntimeError:
        # 이벤트 루프가 없으면 새로 생성
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            db = get_postgres_db()
            return loop.run_until_complete(db.create_pool())
        finally:
            loop.close()