from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import importlib.util
spec = importlib.util.spec_from_file_location("database", "app/database.py")
db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db_module)
get_db = db_module.get_db

router = APIRouter(prefix="/health", tags=["Health Check"])


@router.get("/")
async def health_check():
    """기본 헬스 체크"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "FastAPI Recommendation System"
    }


@router.get("/db")
async def database_health_check(db: Session = Depends(get_db)):
    """데이터베이스 연결 상태 확인"""
    try:
        # 간단한 쿼리로 DB 연결 테스트
        result = db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "message": "PostgreSQL (Supabase) 연결 성공",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database": "disconnected",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }