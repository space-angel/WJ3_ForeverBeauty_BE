"""
레거시 추천 API (사용 중단 예정)
새로운 recommendation_controller.py로 이전됨
"""
from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)

# 빈 라우터 (레거시 호환성용)
router = APIRouter(
    prefix="/api/v1/legacy",
    tags=["legacy"],
    deprecated=True
)

@router.get("/status")
async def legacy_status():
    """레거시 API 상태"""
    return {
        "message": "이 API는 사용 중단되었습니다. /api/v1/recommend를 사용하세요.",
        "deprecated": True,
        "new_endpoint": "/api/v1/recommend"
    }