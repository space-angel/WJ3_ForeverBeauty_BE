"""
PostgreSQL 동기 연결 관리 (psycopg2 기반)
asyncpg 이벤트 루프 문제 해결을 위한 대안
"""

import psycopg2
import psycopg2.pool
import psycopg2.extras
import os
import logging
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class PostgreSQLSyncDB:
    """PostgreSQL 동기 데이터베이스 연결 클래스"""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        PostgreSQL 데이터베이스 초기화
        
        Args:
            database_url: PostgreSQL 연결 URL (환경변수에서 자동 로드)
        """
        self.database_url = database_url or os.getenv('DATABASE_URL')
        if not self.database_url:
            logger.warning("DATABASE_URL 환경변수가 설정되지 않았습니다. 데이터베이스 연결을 건너뜁니다.")
            self._pool = None
            self._connection_config = {}
            self._executor = ThreadPoolExecutor(max_workers=5)
            self._lock = threading.Lock()
            return
        
        self._pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None
        self._connection_config = self._parse_database_url()
        self._executor = ThreadPoolExecutor(max_workers=5)
        self._lock = threading.Lock()
        
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
        
        # SSL 설정 처리
        if 'sslmode=require' in self.database_url or 'supabase.com' in self.database_url:
            config['sslmode'] = 'require'
        
        return config
    
    def create_pool(self, min_conn: int = 1, max_conn: int = 3) -> psycopg2.pool.ThreadedConnectionPool:
        """연결 풀 생성"""
        if not self.database_url:
            raise ValueError("DATABASE_URL이 설정되지 않아 연결 풀을 생성할 수 없습니다.")
            
        with self._lock:
            if self._pool and not self._pool.closed:
                return self._pool
            
            # 기존 풀 정리
            if self._pool:
                try:
                    self._pool.closeall()
                except:
                    pass
            
            try:
                logger.info("PostgreSQL 동기 연결 풀 생성 시작")
                
                # 수퍼베이스 최적화
                if 'supabase.com' in self.database_url:
                    min_conn = 1
                    max_conn = 2
                
                self._pool = psycopg2.pool.ThreadedConnectionPool(
                    minconn=min_conn,
                    maxconn=max_conn,
                    **self._connection_config
                )
                
                # 연결 테스트
                conn = self._pool.getconn()
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                        result = cur.fetchone()
                        if result[0] != 1:
                            raise Exception("연결 테스트 실패")
                finally:
                    self._pool.putconn(conn)
                
                logger.info(f"PostgreSQL 동기 연결 풀 생성 완료 (min={min_conn}, max={max_conn})")
                return self._pool
                
            except Exception as e:
                logger.error(f"PostgreSQL 동기 연결 풀 생성 실패: {e}")
                if self._pool:
                    try:
                        self._pool.closeall()
                    except:
                        pass
                    self._pool = None
                raise
    
    def close_pool(self):
        """연결 풀 종료"""
        with self._lock:
            if self._pool:
                try:
                    logger.info("PostgreSQL 동기 연결 풀 종료 시작")
                    self._pool.closeall()
                    logger.info("PostgreSQL 동기 연결 풀 종료 완료")
                except Exception as e:
                    logger.debug(f"연결 풀 종료 중 오류 (무시됨): {e}")
                finally:
                    self._pool = None
    
    def is_pool_active(self) -> bool:
        """연결 풀이 활성 상태인지 확인"""
        try:
            return self._pool is not None and not self._pool.closed
        except:
            return False
    
    def _execute_sync(self, query: str, *args) -> List[Dict[str, Any]]:
        """동기 쿼리 실행"""
        if not self.is_pool_active():
            self.create_pool()
        
        # asyncpg 형식($1, $2)을 psycopg2 형식(%s)으로 변환
        psycopg2_query = query
        param_count = 1
        while f'${param_count}' in psycopg2_query:
            psycopg2_query = psycopg2_query.replace(f'${param_count}', '%s')
            param_count += 1
        
        conn = None
        try:
            conn = self._pool.getconn()
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(psycopg2_query, args if args else None)
                rows = cur.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"동기 쿼리 실행 오류: {e}")
            raise
        finally:
            if conn:
                try:
                    self._pool.putconn(conn)
                except:
                    pass
    
    async def execute_query(self, query: str, *args) -> List[Dict[str, Any]]:
        """비동기 쿼리 실행 (ThreadPoolExecutor 사용)"""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._executor, 
                self._execute_sync, 
                query, 
                *args
            )
            return result
        except Exception as e:
            logger.error(f"비동기 쿼리 실행 오류: {e}")
            raise
    
    def test_connection(self) -> bool:
        """데이터베이스 연결 테스트"""
        if not self.database_url:
            logger.warning("DATABASE_URL이 없어 연결 테스트를 건너뜁니다.")
            return False
            
        try:
            result = self._execute_sync("SELECT 1")
            return len(result) > 0 and result[0].get('?column?') == 1
        except Exception as e:
            logger.error(f"PostgreSQL 연결 테스트 실패: {e}")
            return False


# 전역 인스턴스
_sync_db_instance: Optional[PostgreSQLSyncDB] = None

def get_postgres_sync_db() -> PostgreSQLSyncDB:
    """PostgreSQL 동기 데이터베이스 인스턴스 반환 (싱글톤)"""
    global _sync_db_instance
    if _sync_db_instance is None:
        _sync_db_instance = PostgreSQLSyncDB()
        logger.debug("새로운 PostgreSQL 동기 인스턴스 생성")
    return _sync_db_instance

async def init_sync_database():
    """동기 데이터베이스 초기화"""
    db = get_postgres_sync_db()
    
    # DATABASE_URL이 없으면 초기화 건너뛰기
    if not db.database_url:
        logger.warning("DATABASE_URL이 없어 동기 데이터베이스 초기화를 건너뜁니다.")
        return
    
    try:
        logger.info("PostgreSQL 동기 데이터베이스 초기화 시작")
        
        # 연결 풀 생성
        db.create_pool()
        
        # 연결 테스트
        if db.test_connection():
            logger.info("PostgreSQL 동기 데이터베이스 초기화 및 연결 테스트 완료")
        else:
            raise Exception("PostgreSQL 동기 데이터베이스 연결 테스트 실패")
            
    except Exception as e:
        logger.error(f"PostgreSQL 동기 데이터베이스 초기화 실패: {e}")
        raise

def close_sync_database():
    """동기 데이터베이스 연결 종료"""
    global _sync_db_instance
    if _sync_db_instance:
        try:
            _sync_db_instance.close_pool()
            logger.info("PostgreSQL 동기 데이터베이스 연결 종료 완료")
        except Exception as e:
            logger.error(f"PostgreSQL 동기 데이터베이스 종료 중 오류: {e}")
        finally:
            _sync_db_instance = None