"""
추천 API - 실제 추천 엔진 연동
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
from uuid import uuid4
import logging

# 기존 모델 임포트
from app.models.request import RecommendationRequest
from app.models.response import RecommendationResponse

# 유틸리티 임포트
from app.utils.time_tracker import TimeTracker
from app.utils.fallback_factory import create_error_response

logger = logging.getLogger(__name__)

# 추천 라우터
router = APIRouter(
    prefix="/api/v1",
    tags=["recommendation"]
)

@router.post("/recommend", response_model=RecommendationResponse)
async def recommend_products(request: RecommendationRequest):
    """
    화장품 추천 API - 실제 추천 엔진 사용
    """
    # 시간 측정 시작
    tracker = TimeTracker("recommendation_api").start()
    request_id = uuid4()
    
    try:
        logger.info(f"추천 요청 시작: {request_id}")
        
        # 추천 엔진 초기화
        tracker.step("engine_init")
        from app.services.recommendation_engine import RecommendationEngine
        engine = RecommendationEngine()
        
        # 추천 실행
        tracker.step("recommendation")
        response = await engine.recommend(request)
        
        # 성공 로그
        metrics = tracker.finish()
        logger.info(f"추천 완료: {request_id} ({metrics.total_ms:.2f}ms)")
        
        return response
        
    except ValueError as e:
        # 잘못된 요청 (400 에러)
        metrics = tracker.finish()
        logger.warning(f"잘못된 요청: {request_id} - {e} ({metrics.total_ms:.2f}ms)")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        # 시스템 오류 (500 에러) - 깔끔한 폴백 응답
        metrics = tracker.finish()
        logger.error(f"추천 처리 오류: {request_id} - {e} ({metrics.total_ms:.2f}ms)")
        
        # 폴백 응답 생성 (하드코딩 제거!)
        fallback_response = create_error_response(
            error=e,
            request=request,
            request_id=request_id,
            execution_time_seconds=metrics.total_seconds,
            error_type='system_error'
        )
        
        return fallback_response

@router.get("/recommend/health")
async def recommendation_health():
    """추천 시스템 헬스체크"""
    return {
        "status": "healthy",
        "service": "recommendation",
        "timestamp": datetime.now().isoformat(),  # 실시간 시간!
        "version": "1.0.0"  # TODO: shared.constants.SYSTEM_VERSION 사용
    }

# 레거시 라우터 (호환성용)
legacy_router = APIRouter(
    prefix="/api/v1/legacy",
    tags=["legacy"],
    deprecated=True
)

@legacy_router.get("/status")
async def legacy_status():
    """레거시 API 상태"""
    return {
        "message": "이 API는 사용 중단되었습니다. /api/v1/recommend를 사용하세요.",
        "deprecated": True,
        "new_endpoint": "/api/v1/recommend"
    }