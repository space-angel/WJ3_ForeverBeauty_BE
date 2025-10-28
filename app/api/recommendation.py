"""
추천 API
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# 추천 라우터
router = APIRouter(
    prefix="/api/v1",
    tags=["recommendation"]
)

# 요청 모델
class UserProfile(BaseModel):
    age_group: Optional[str] = None
    gender: Optional[str] = None
    skin_type: Optional[str] = None
    skin_concerns: Optional[List[str]] = None
    allergies: Optional[List[str]] = None

class RecommendationRequest(BaseModel):
    intent_tags: List[str]
    user_profile: Optional[UserProfile] = None
    top_n: Optional[int] = 5

# 응답 모델
class RecommendationItem(BaseModel):
    product_id: str
    name: str
    brand: str
    category: str
    price: Optional[int] = None
    score: float
    reasons: List[str]

class RecommendationResponse(BaseModel):
    recommendations: List[RecommendationItem]
    total_found: int
    execution_time_ms: float
    request_id: str

@router.post("/recommend", response_model=RecommendationResponse)
async def recommend_products(request: RecommendationRequest):
    """
    화장품 추천 API
    """
    try:
        import time
        import uuid
        
        start_time = time.time()
        
        # 간단한 목업 데이터로 응답
        mock_recommendations = [
            RecommendationItem(
                product_id="prod_001",
                name="하이드레이팅 모이스처라이저",
                brand="뷰티브랜드",
                category="moisturizer",
                price=45000,
                score=0.95,
                reasons=["보습 효과 우수", "30대 건성 피부에 적합", "안티에이징 성분 함유"]
            ),
            RecommendationItem(
                product_id="prod_002", 
                name="리뉴얼 세럼",
                brand="스킨케어",
                category="serum",
                price=65000,
                score=0.88,
                reasons=["주름 개선 효과", "보습과 안티에이징 동시 효과"]
            ),
            RecommendationItem(
                product_id="prod_003",
                name="너리싱 나이트 크림",
                brand="프리미엄케어",
                category="night_cream", 
                price=55000,
                score=0.82,
                reasons=["야간 집중 케어", "건성 피부 맞춤형"]
            )
        ]
        
        # 요청된 개수만큼 제한
        recommendations = mock_recommendations[:request.top_n]
        
        execution_time = (time.time() - start_time) * 1000
        
        return RecommendationResponse(
            recommendations=recommendations,
            total_found=len(mock_recommendations),
            execution_time_ms=round(execution_time, 2),
            request_id=str(uuid.uuid4())
        )
        
    except Exception as e:
        logger.error(f"추천 처리 오류: {e}")
        raise HTTPException(status_code=500, detail="추천 처리 중 오류가 발생했습니다")

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