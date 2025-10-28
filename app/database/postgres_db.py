"""
PostgreSQL 데이터베이스 연결 및 세션 관리
SQLAlchemy 기반 ORM 및 연결 풀링
"""
import os
from typing import Generator, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import logging

logger = logging.getLogger(__name__)

# 환경변수 기반 설정
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://user:password@localhost:5432/cosmetic_rules"
)

# 연결 풀 설정 (Supabase 최적화)
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,           # 연결 수 줄임 (Supabase 제한 고려)
    max_overflow=10,       # 최대 추가 연결 수 줄임
    pool_pre_ping=True,    # 연결 유효성 검사
    pool_recycle=1800,     # 30분마다 연결 재생성 (더 자주)
    pool_timeout=30,       # 연결 대기 시간 30초
    echo=False,            # SQL 로깅 (개발시에만 True)
    connect_args={
        "sslmode": "require",
        "application_name": "cosmetic_recommendation_api"
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class DatabaseManager:
    """데이터베이스 연결 관리자"""
    
    def __init__(self):
        self._engine = engine
        self._session_factory = SessionLocal
    
    def get_session(self) -> Session:
        """새 세션 생성"""
        return self._session_factory()
    
    def test_connection(self) -> bool:
        """연결 테스트"""
        try:
            with self._engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.fetchone()[0] == 1
        except Exception as e:
            logger.error(f"PostgreSQL 연결 테스트 실패: {e}")
            return False
    
    def get_connection_info(self) -> dict:
        """연결 정보 조회"""
        try:
            with self._engine.connect() as conn:
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                
                pool = self._engine.pool
                return {
                    "status": "connected",
                    "version": version,
                    "pool_size": pool.size(),
                    "checked_in": pool.checkedin(),
                    "checked_out": pool.checkedout(),
                    "overflow": pool.overflow(),
                    "invalid": pool.invalid()
                }
        except Exception as e:
            logger.error(f"연결 정보 조회 실패: {e}")
            return {"status": "disconnected", "error": str(e)}
    
    def close(self):
        """연결 풀 종료"""
        self._engine.dispose()

# 전역 데이터베이스 매니저
db_manager = DatabaseManager()

def get_db_session() -> Generator[Session, None, None]:
    """
    의존성 주입용 세션 생성기
    FastAPI Depends와 함께 사용
    """
    session = db_manager.get_session()
    try:
        yield session
    except Exception as e:
        session.rollback()
        logger.error(f"데이터베이스 세션 오류: {e}")
        raise
    finally:
        session.close()

def get_db_session_sync() -> Session:
    """
    동기 코드용 세션 생성
    수동으로 close() 호출 필요
    """
    return db_manager.get_session()

# 헬스체크용 함수
def check_database_health() -> dict:
    """데이터베이스 상태 확인"""
    return db_manager.get_connection_info()