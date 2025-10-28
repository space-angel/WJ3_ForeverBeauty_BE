"""
추천 API - 실제 추천 엔진 연동
"""
from fastapi import APIRouter, HTTPException
import logging

# 기존 모델 임포트
from app.models.request import RecommendationRequest
from app.models.response import RecommendationResponse

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
    try:
        # 실제 추천 엔진 사용
        from app.services.recommendation_engine import RecommendationEngine
        
        engine = RecommendationEngine()
        response = await engine.recommend(request)
        
        return response
        
    except ValueError as e:
        logger.warning(f"잘못된 요청: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"추천 처리 오류: {e}")
        # 실제 엔진 실패 시 폴백 응답
        from app.models.response import (
            RecommendationResponse, ExecutionSummary, PipelineStatistics, 
            RecommendationItem
        )
        from datetime import datetime
        from uuid import uuid4
        
        request_id = uuid4()
        
        fallback_item = RecommendationItem(
            rank=1,
            product_id="fallback_001",
            product_name="시스템 오류 - 추천 불가",
            brand_name="시스템",
            category="error",
            final_score=0.0,
            intent_match_score=0.0,
            reasons=["추천 엔진 오류로 인한 폴백 응답"],
            warnings=["시스템 오류가 발생했습니다. 잠시 후 다시 시도해주세요."]
        )
        
        execution_summary = ExecutionSummary(
            request_id=request_id,
            timestamp=datetime.now(),
            success=False,
            execution_time_seconds=0.0,
            ruleset_version="error",
            active_rules_count=0
        )
        
        pipeline_stats = PipelineStatistics(
            total_candidates=0,
            excluded_by_rules=0,
            penalized_products=0,
            final_recommendations=1,
            eligibility_rules_applied=0,
            scoring_rules_applied=0,
            query_time_ms=0.0,
            evaluation_time_ms=0.0,
            ranking_time_ms=0.0,
            total_time_ms=0.0
        )
        
        return RecommendationResponse(
            execution_summary=execution_summary,
            input_summary={"error": "추천 엔진 오류"},
            pipeline_statistics=pipeline_stats,
            recommendations=[fallback_item]
        )

@router.get("/recommend/health")
async def recommendation_health():
    """추천 시스템 헬스체크"""
    return {
        "status": "healthy",
        "service": "recommendation",
        "timestamp": "2025-10-28T06:30:00Z",
        "version": "1.0.0"
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