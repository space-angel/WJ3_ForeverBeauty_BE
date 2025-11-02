"""
PostgreSQL 데이터베이스 연결 관리
asyncpg 기반 연결 풀 및 헬스체크 기능
"""

import asyncpg
import asyncio
import os
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class PostgreSQLDB:
    """PostgreSQL 데이터베이스 연결 클래스"""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        PostgreSQL 데이터베이스 초기화
        
        Args:
            database_url: PostgreSQL 연결 URL (환경변수에서 자동 로드)
        """
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            raise ValueError("DATABASE_URL 환경변수가 설정되지 않았습니다.")
        
        self._pool: Optional[asyncpg.Pool] = None
        self._connection_config = self._parse_database_url()
        self._pool_lock = None  # 나중에 초기화
        self._closing = False  # 종료 상태 플래그
        
    def _parse_database_url(self) -> Dict[str, Any]:
        """DATABASE_URL 파싱하여 연결 설정 추출"""
        parsed = urlparse(self.database_url)
        
        config = {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/'),
            'user': parsed.username,
            'password': parsed.password,
        }
        
        # 수퍼베이스 SSL 설정 최적화
        if 'sslmode=require' in self.database_url or 'supabase.com' in self.database_url:
            import ssl
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            config['ssl'] = ssl_context
        
        return config
    
    async def create_pool(self, min_size: int = 1, max_size: int = 3) -> asyncpg.Pool:
        """연결 풀 생성 - 단순화 및 안정성 강화"""
        # 종료 중이면 풀 생성하지 않음
        if self._closing:
            raise RuntimeError("데이터베이스가 종료 중입니다")
        
        # 기존 풀이 있고 활성 상태면 그대로 반환
        if self._pool and not self._pool._closed:
            return self._pool
        
        # 기존 풀 정리
        if self._pool is not None:
            try:
                self._pool.terminate()
            except:
                pass
            self._pool = None
        
        # 수퍼베이스 최적화 설정
        if self.is_supabase_connection():
            min_size = 1
            max_size = 1  # 단일 연결
            connection_timeout = 15.0
            command_timeout = 20.0
            max_inactive_lifetime = 300.0  # 5분
            max_queries = 1000
        else:
            connection_timeout = 10.0
            command_timeout = 15.0
            max_inactive_lifetime = 180.0
            max_queries = 500
        
        try:
            logger.info("PostgreSQL 연결 풀 생성 시작")
            
            # 단순한 풀 생성 (복잡한 설정 제거)
            self._pool = await asyncio.wait_for(
                asyncpg.create_pool(
                    **self._connection_config,
                    min_size=min_size,
                    max_size=max_size,
                    max_inactive_connection_lifetime=max_inactive_lifetime,
                    max_queries=max_queries,
                    command_timeout=command_timeout,
                    server_settings={
                        'application_name': 'cosmetic_api',
                        'timezone': 'UTC'
                    }
                ),
                timeout=connection_timeout
            )
            
            # 간단한 연결 테스트
            async with self._pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            
            logger.info(f"PostgreSQL 연결 풀 생성 완료 (min={min_size}, max={max_size})")
            return self._pool
            
        except Exception as e:
            logger.error(f"PostgreSQL 연결 풀 생성 실패: {e}")
            if self._pool:
                try:
                    self._pool.terminate()
                except:
                    pass
                self._pool = None
            raise
    

    
    async def close_pool(self):
        """연결 풀 종료 - 단순화"""
        self._closing = True
        
        if not self._pool:
            return
        
        try:
            logger.info("PostgreSQL 연결 풀 종료 시작")
            self._pool.terminate()
            logger.info("PostgreSQL 연결 풀 종료 완료")
        except Exception as e:
            logger.debug(f"연결 풀 종료 중 오류 (무시됨): {e}")
        finally:
            self._pool = None
    
    def is_pool_active(self) -> bool:
        """연결 풀이 활성 상태인지 확인"""
        try:
            return self._pool is not None and not self._pool._closed
        except:
            return False
    
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
        """쿼리 실행 및 결과 반환 - 단순화"""
        try:
            async with self.get_connection() as conn:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"쿼리 실행 오류: {e}")
            raise
    
    async def execute_single(self, query: str, *args) -> Optional[Dict[str, Any]]:
        """단일 결과 쿼리 실행"""
        # 연결 풀 상태 확인 및 재생성
        if not self.is_pool_active():
            await self.create_pool()
        
        async with self.get_connection() as conn:
            try:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
            except Exception as e:
                logger.error(f"단일 쿼리 실행 오류: {e}")
                raise
    
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
        try:
            async with self.get_connection() as conn:
                result = await conn.fetchval("SELECT 1")
                return result == 1
        except Exception as e:
            logger.error(f"PostgreSQL 연결 테스트 실패: {e}")
            return False
    
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