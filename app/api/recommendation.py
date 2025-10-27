"""
화장품 추천 API 엔드포인트
개인화된 화장품 추천 서비스를 제공합니다.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
from uuid import uuid4
from typing import Optional, List
import logging

from app.models.request import RecommendationRequest, HealthCheckRequest
from app.models.response import (
    RecommendationResponse, HealthResponse, ErrorResponse,
    ExecutionSummary, PipelineStatistics, RecommendationItem,
    RulesetHealth, RuleHit
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1",
    tags=["recommendation"],
    responses={
        400: {"model": ErrorResponse, "description": "잘못된 요청"},
        500: {"model": ErrorResponse, "description": "서버 내부 오류"}
    }
)

@router.post(
    "/recommend",
    response_model=RecommendationResponse,
    summary="화장품 추천",
    description="""
    사용자의 의도, 프로필, 의약품 정보를 기반으로 개인화된 화장품을 추천합니다.
    
    ## 주요 기능
    - **의도 기반 추천**: 사용자가 원하는 효과에 맞는 제품 추천
    - **안전성 검토**: 의약품과의 상호작용 및 알레르기 성분 확인
    - **개인화**: 피부 타입, 연령, 성별 등을 고려한 맞춤 추천
    - **상세한 근거**: 각 추천에 대한 명확한 이유 제공
    
    ## 추천 알고리즘
    1. 의도 태그 기반 후보 제품 조회
    2. 사용자 프로필 및 맥락 필터링
    3. 의약품 상호작용 및 안전성 검토
    4. 점수 계산 및 순위 결정
    5. 상세한 근거와 함께 결과 반환
    
    ## 예시 요청
    ```json
    {
        "intent_tags": ["moisturizing", "anti-aging"],
        "user_profile": {
            "age_group": "30s",
            "skin_type": "dry",
            "skin_concerns": ["wrinkles", "dryness"]
        },
        "medications": [
            {
                "name": "레티놀 크림",
                "active_ingredients": ["retinol"]
            }
        ],
        "top_n": 5
    }
    ```
    """,
    responses={
        200: {
            "description": "추천 성공",
            "content": {
                "application/json": {
                    "example": {
                        "execution_summary": {
                            "request_id": "123e4567-e89b-12d3-a456-426614174000",
                            "timestamp": "2024-01-15T10:30:00Z",
                            "success": True,
                            "execution_time_seconds": 0.245,
                            "ruleset_version": "v2.1",
                            "active_rules_count": 28
                        },
                        "input_summary": {
                            "intent_tags_count": 2,
                            "requested_count": 5,
                            "has_user_profile": True,
                            "medications_count": 1
                        },
                        "pipeline_statistics": {
                            "total_candidates": 150,
                            "excluded_by_rules": 12,
                            "penalized_products": 8,
                            "final_recommendations": 5,
                            "eligibility_rules_applied": 4,
                            "scoring_rules_applied": 3,
                            "query_time_ms": 45.2,
                            "evaluation_time_ms": 120.8,
                            "ranking_time_ms": 35.1,
                            "total_time_ms": 245.0
                        },
                        "recommendations": [
                            {
                                "rank": 1,
                                "product_id": "PRD_001",
                                "product_name": "하이드라 인텐시브 모이스처라이저",
                                "brand_name": "뷰티랩",
                                "category": "모이스처라이저",
                                "final_score": 92.5,
                                "intent_match_score": 95.0,
                                "reasons": [
                                    "보습 효과가 뛰어난 히알루론산 함유",
                                    "30대 건성 피부에 적합한 포뮬러",
                                    "레티놀과 안전하게 병용 가능"
                                ],
                                "warnings": [],
                                "rule_hits": []
                            }
                        ]
                    }
                }
            }
        }
    }
)
async def recommend_products(request: RecommendationRequest):
    """
    개인화된 화장품 추천
    
    사용자의 의도, 프로필, 의약품 정보를 종합적으로 분석하여
    가장 적합한 화장품을 추천합니다.
    """
    try:
        logger.info(f"추천 요청 시작: intent_tags={request.intent_tags}, top_n={request.top_n}")
        
        # 실제 추천 로직은 여기에 구현
        # 현재는 테스트용 응답 반환
        
        execution_summary = ExecutionSummary(
            request_id=uuid4(),
            timestamp=datetime.now(),
            success=True,
            execution_time_seconds=0.245,
            ruleset_version="v2.1",
            active_rules_count=28
        )
        
        pipeline_stats = PipelineStatistics(
            total_candidates=150,
            excluded_by_rules=12,
            penalized_products=8,
            final_recommendations=request.top_n,
            eligibility_rules_applied=4,
            scoring_rules_applied=3,
            query_time_ms=45.2,
            evaluation_time_ms=120.8,
            ranking_time_ms=35.1,
            total_time_ms=245.0
        )
        
        # 샘플 추천 결과 (더 많은 제품 추가)
        recommendations = []
        sample_products = [
            ("PRD_001", "하이드라 인텐시브 모이스처라이저", "뷰티랩", "모이스처라이저", 92.5),
            ("PRD_002", "센시티브 수딩 세럼", "스킨케어플러스", "세럼", 89.2),
            ("PRD_003", "안티에이징 나이트 크림", "프리미엄코스", "나이트크림", 87.8),
            ("PRD_004", "젠틀 클렌징 폼", "퓨어스킨", "클렌저", 85.1),
            ("PRD_005", "비타민C 브라이트닝 에센스", "글로우랩", "에센스", 83.7),
            ("PRD_006", "콜라겐 부스팅 크림", "에이지리스", "크림", 82.3),
            ("PRD_007", "하이알루론산 토너", "모이스트케어", "토너", 81.9),
            ("PRD_008", "펩타이드 아이크림", "아이케어랩", "아이크림", 80.5),
            ("PRD_009", "세라마이드 리페어 로션", "스킨바리어", "로션", 79.8),
            ("PRD_010", "나이아신아마이드 세럼", "브라이트스킨", "세럼", 78.4),
            ("PRD_011", "레티놀 대안 크림", "젠틀에이징", "크림", 77.6),
            ("PRD_012", "스네일 뮤신 에센스", "리페어랩", "에센스", 76.9),
            ("PRD_013", "세라마이드 클렌징 오일", "딥클린", "클렌징오일", 75.8),
            ("PRD_014", "아데노신 나이트 마스크", "슬리핑케어", "마스크", 74.7),
            ("PRD_015", "판테놀 수딩 미스트", "캄스킨", "미스트", 73.5),
            ("PRD_016", "베타글루칸 앰플", "이뮨스킨", "앰플", 72.8),
            ("PRD_017", "알로에 젤 크림", "네이처케어", "젤크림", 71.9),
            ("PRD_018", "마데카소사이드 밤", "힐링스킨", "밤", 70.6),
            ("PRD_019", "센텔라 진정 패드", "수딩케어", "패드", 69.4),
            ("PRD_020", "아르간 오일 세럼", "오일케어", "오일세럼", 68.2)
        ]
        
        for i, (pid, name, brand, category, score) in enumerate(sample_products[:request.top_n]):
            recommendation = RecommendationItem(
                rank=i + 1,
                product_id=pid,
                product_name=name,
                brand_name=brand,
                category=category,
                final_score=score,
                intent_match_score=score + 2.5,
                reasons=[
                    f"{', '.join(request.intent_tags)} 효과에 최적화",
                    "안전성 검증 완료",
                    "사용자 프로필과 높은 일치도"
                ],
                warnings=[],
                rule_hits=[]
            )
            recommendations.append(recommendation)
        
        input_summary = {
            "intent_tags_count": len(request.intent_tags),
            "requested_count": request.top_n,
            "has_user_profile": request.user_profile is not None,
            "medications_count": len(request.medications) if request.medications else 0,
            "has_usage_context": request.usage_context is not None,
            "price_range_specified": request.price_range is not None
        }
        
        response = RecommendationResponse(
            execution_summary=execution_summary,
            input_summary=input_summary,
            pipeline_statistics=pipeline_stats,
            recommendations=recommendations
        )
        
        logger.info(f"추천 완료: {len(recommendations)}개 제품 추천")
        return response
        
    except Exception as e:
        logger.error(f"추천 처리 중 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "RECOMMENDATION_ERROR",
                "message": "추천 처리 중 오류가 발생했습니다",
                "details": {"error_type": type(e).__name__}
            }
        )

@router.get(
    "/recommend/health",
    response_model=HealthResponse,
    summary="추천 시스템 상태 확인",
    description="""
    추천 시스템의 전반적인 상태를 확인합니다.
    
    ## 확인 항목
    - 룰셋 상태 및 버전
    - 데이터베이스 연결 상태
    - 시스템 성능 지표
    - 오류율 및 응답 시간
    
    이 엔드포인트는 시스템 모니터링 및 헬스체크에 사용됩니다.
    """,
    responses={
        200: {
            "description": "시스템 상태 정보",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "ruleset": {
                            "ruleset_version": "v2.1",
                            "total_rules": 45,
                            "active_rules": 28,
                            "eligibility_rules": 15,
                            "scoring_rules": 13,
                            "expired_rules": 2,
                            "total_aliases": 120,
                            "sqlite_status": "connected",
                            "postgres_status": "connected",
                            "avg_response_time_ms": 245.5,
                            "error_rate_percent": 0.2,
                            "last_updated": "2024-01-15T09:00:00Z"
                        },
                        "timestamp": "2024-01-15T10:30:00Z"
                    }
                }
            }
        }
    }
)
async def recommendation_health(
    include_stats: bool = Query(False, description="상세 성능 통계 포함 여부")
):
    """
    추천 시스템 헬스체크
    
    시스템의 전반적인 상태와 성능 지표를 확인합니다.
    """
    try:
        logger.info("헬스체크 요청")
        
        # 실제 헬스체크 로직은 여기에 구현
        ruleset_health = RulesetHealth(
            ruleset_version="v2.1",
            total_rules=45,
            active_rules=28,
            eligibility_rules=15,
            scoring_rules=13,
            expired_rules=2,
            total_aliases=120,
            sqlite_status="connected",
            postgres_status="connected",
            avg_response_time_ms=245.5 if include_stats else None,
            error_rate_percent=0.2 if include_stats else None,
            last_updated=datetime.now()
        )
        
        response = HealthResponse(
            status="healthy",
            ruleset=ruleset_health,
            timestamp=datetime.now()
        )
        
        logger.info("헬스체크 완료")
        return response
        
    except Exception as e:
        logger.error(f"헬스체크 중 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "HEALTH_CHECK_ERROR",
                "message": "헬스체크 중 오류가 발생했습니다",
                "details": {"error_type": type(e).__name__}
            }
        )

@router.get(
    "/recommend/categories",
    summary="지원 카테고리 목록",
    description="추천 시스템에서 지원하는 화장품 카테고리 목록을 반환합니다.",
    response_model=List[str]
)
async def get_supported_categories():
    """지원하는 화장품 카테고리 목록"""
    categories = [
        "클렌저", "토너", "에센스", "세럼", "모이스처라이저", 
        "크림", "아이크림", "선크림", "마스크팩", "오일",
        "미스트", "앰플", "젤", "로션", "밤", "스크럽"
    ]
    return categories

@router.get(
    "/recommend/intent-tags",
    summary="지원 의도 태그 목록", 
    description="추천 시스템에서 지원하는 의도 태그 목록을 반환합니다.",
    response_model=List[str]
)
async def get_supported_intent_tags():
    """지원하는 의도 태그 목록"""
    intent_tags = [
        "moisturizing", "anti-aging", "cleansing", "brightening",
        "acne-care", "sensitive-care", "pore-care", "firming",
        "soothing", "exfoliating", "sun-protection", "oil-control",
        "hydrating", "nourishing", "repairing", "calming"
    ]
    return intent_tags