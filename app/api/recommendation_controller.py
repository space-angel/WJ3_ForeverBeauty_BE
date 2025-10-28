"""
깔끔한 추천 API 컨트롤러
비즈니스 로직은 서비스 레이어로 분리
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List
import logging

from app.models.request import RecommendationRequest
from app.models.response import RecommendationResponse, HealthResponse, ErrorResponse
from app.services.recommendation_engine import RecommendationEngine
from app.services.health_service import HealthService
from app.config.intent_config import CategoryConfig, TagConfig

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["recommendation"],
    responses={
        400: {"model": ErrorResponse, "description": "잘못된 요청"},
        500: {"model": ErrorResponse, "description": "서버 내부 오류"}
    }
)

class RecommendationController:
    """추천 API 컨트롤러"""
    
    def __init__(self):
        self.recommendation_engine = RecommendationEngine()
        self.health_service = HealthService()

# 컨트롤러 인스턴스
controller = RecommendationController()

@router.post(
    "/recommend",
    response_model=RecommendationResponse,
    summary="화장품 추천",
    description="사용자 의도 기반 개인화된 화장품 추천"
)
async def recommend_products(request: RecommendationRequest):
    """
    개인화된 화장품 추천
    
    - **intent_tags**: 사용자 의도 (필수)
    - **user_profile**: 사용자 프로필 (선택)
    - **medications**: 복용 중인 의약품 (선택)
    - **top_n**: 추천 개수 (기본 5개)
    """
    try:
        logger.info(f"추천 요청: {request.intent_tags}")
        
        # 입력 검증
        _validate_request(request)
        
        # 추천 실행
        response = await controller.recommendation_engine.recommend(request)
        
        logger.info(f"추천 완료: {len(response.recommendations)}개")
        return response
        
    except ValueError as e:
        logger.warning(f"잘못된 요청: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"추천 처리 오류: {e}")
        raise HTTPException(status_code=500, detail="추천 처리 중 오류가 발생했습니다")

@router.get(
    "/recommend/health",
    response_model=HealthResponse,
    summary="추천 시스템 상태 확인"
)
async def recommendation_health(
    include_stats: bool = Query(False, description="상세 통계 포함 여부")
):
    """추천 시스템 헬스체크"""
    try:
        return await controller.health_service.check_recommendation_health(include_stats)
    except Exception as e:
        logger.error(f"헬스체크 오류: {e}")
        raise HTTPException(status_code=500, detail="헬스체크 중 오류가 발생했습니다")

@router.get(
    "/recommend/categories",
    response_model=List[str],
    summary="지원 카테고리 목록"
)
async def get_supported_categories():
    """지원하는 화장품 카테고리 목록"""
    return CategoryConfig.SUPPORTED_CATEGORIES

@router.get(
    "/recommend/intent-tags",
    response_model=List[str],
    summary="지원 의도 태그 목록"
)
async def get_supported_intent_tags():
    """지원하는 의도 태그 목록"""
    return TagConfig.SUPPORTED_INTENT_TAGS

def _validate_request(request: RecommendationRequest):
    """요청 유효성 검증"""
    
    # 의도 태그 검증
    if not request.intent_tags:
        raise ValueError("의도 태그가 필요합니다")
    
    # 지원하지 않는 의도 태그 확인
    unsupported_tags = [
        tag for tag in request.intent_tags 
        if tag not in TagConfig.SUPPORTED_INTENT_TAGS
    ]
    if unsupported_tags:
        raise ValueError(f"지원하지 않는 의도 태그: {unsupported_tags}")
    
    # 추천 개수 검증
    if request.top_n < 1 or request.top_n > 20:
        raise ValueError("추천 개수는 1-20 사이여야 합니다")
    
    logger.debug(f"요청 검증 완료: {request.intent_tags}")