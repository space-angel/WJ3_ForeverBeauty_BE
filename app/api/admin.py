"""
관리자 API 엔드포인트
시스템 모니터링, 설정 관리, 운영 도구를 제공합니다.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import logging

from app.models.response import HealthResponse, RulesetHealth, ErrorResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
    responses={
        401: {"model": ErrorResponse, "description": "인증 필요"},
        403: {"model": ErrorResponse, "description": "권한 없음"},
        500: {"model": ErrorResponse, "description": "서버 내부 오류"}
    }
)

@router.get(
    "/health",
    response_model=HealthResponse,
    summary="전체 시스템 상태 확인",
    description="""
    전체 시스템의 상태를 종합적으로 확인합니다.
    
    ## 확인 항목
    - 데이터베이스 연결 상태 (SQLite, PostgreSQL)
    - 룰셋 상태 및 통계
    - 시스템 성능 지표
    - 최근 오류 현황
    
    이 엔드포인트는 시스템 관리자가 전체적인 시스템 상태를 
    모니터링하는 데 사용됩니다.
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
async def system_health():
    """
    전체 시스템 헬스체크
    
    데이터베이스 연결, 룰셋 상태, 성능 지표 등을 종합적으로 확인합니다.
    """
    try:
        logger.info("시스템 헬스체크 시작")
        
        # 실제 헬스체크 로직 구현 필요
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
            avg_response_time_ms=245.5,
            error_rate_percent=0.2,
            last_updated=datetime.now()
        )
        
        response = HealthResponse(
            status="healthy",
            ruleset=ruleset_health,
            timestamp=datetime.now()
        )
        
        logger.info("시스템 헬스체크 완료")
        return response
        
    except Exception as e:
        logger.error(f"시스템 헬스체크 중 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "SYSTEM_HEALTH_ERROR",
                "message": "시스템 헬스체크 중 오류가 발생했습니다",
                "details": {"error_type": type(e).__name__}
            }
        )

@router.get(
    "/stats",
    summary="시스템 통계",
    description="""
    시스템의 상세한 통계 정보를 제공합니다.
    
    ## 포함 정보
    - 요청 처리 통계
    - 추천 성능 지표
    - 룰 적용 통계
    - 오류 발생 현황
    """,
    response_model=Dict[str, Any]
)
async def get_system_stats(
    period: str = Query("24h", description="통계 기간 (1h, 24h, 7d, 30d)"),
    include_details: bool = Query(False, description="상세 정보 포함 여부")
):
    """시스템 통계 조회"""
    try:
        logger.info(f"시스템 통계 조회: period={period}")
        
        # 실제 통계 로직 구현 필요
        stats = {
            "period": period,
            "request_stats": {
                "total_requests": 1250,
                "successful_requests": 1235,
                "failed_requests": 15,
                "success_rate_percent": 98.8,
                "avg_response_time_ms": 245.5
            },
            "recommendation_stats": {
                "total_recommendations": 6175,
                "avg_recommendations_per_request": 4.94,
                "most_common_intent_tags": ["moisturizing", "anti-aging", "cleansing"],
                "category_distribution": {
                    "모이스처라이저": 25.2,
                    "세럼": 18.7,
                    "클렌저": 15.3,
                    "크림": 12.8,
                    "기타": 28.0
                }
            },
            "rule_stats": {
                "eligibility_rules_triggered": 145,
                "scoring_rules_triggered": 89,
                "most_triggered_rules": ["medication_interaction", "age_restriction", "skin_type_mismatch"]
            },
            "timestamp": datetime.now().isoformat()
        }
        
        if include_details:
            stats["detailed_metrics"] = {
                "hourly_request_count": [52, 48, 55, 61, 58, 49, 53, 57],
                "error_breakdown": {
                    "validation_errors": 8,
                    "database_errors": 3,
                    "timeout_errors": 2,
                    "other_errors": 2
                },
                "performance_percentiles": {
                    "p50_ms": 180.2,
                    "p90_ms": 420.1,
                    "p95_ms": 580.5,
                    "p99_ms": 890.3
                }
            }
        
        return stats
        
    except Exception as e:
        logger.error(f"통계 조회 중 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "STATS_ERROR",
                "message": "통계 조회 중 오류가 발생했습니다",
                "details": {"error_type": type(e).__name__}
            }
        )

@router.get(
    "/rules",
    summary="룰 관리",
    description="시스템에서 사용 중인 룰들의 상태를 조회하고 관리합니다.",
    response_model=Dict[str, Any]
)
async def get_rules_status(
    rule_type: Optional[str] = Query(None, description="룰 타입 필터 (eligibility, scoring)"),
    active_only: bool = Query(True, description="활성 룰만 조회")
):
    """룰 상태 조회"""
    try:
        logger.info(f"룰 상태 조회: type={rule_type}, active_only={active_only}")
        
        # 실제 룰 조회 로직 구현 필요
        rules_info = {
            "summary": {
                "total_rules": 45,
                "active_rules": 28,
                "inactive_rules": 17,
                "eligibility_rules": 15,
                "scoring_rules": 13
            },
            "rules": [
                {
                    "rule_id": "ELIG_001",
                    "type": "eligibility",
                    "name": "의약품 상호작용 검사",
                    "description": "특정 의약품과 상호작용하는 성분 배제",
                    "active": True,
                    "weight": 100,
                    "created_at": "2024-01-01T00:00:00Z",
                    "last_modified": "2024-01-10T15:30:00Z"
                },
                {
                    "rule_id": "SCOR_001", 
                    "type": "scoring",
                    "name": "연령대 적합성 점수",
                    "description": "사용자 연령대에 따른 제품 점수 조정",
                    "active": True,
                    "weight": 20,
                    "created_at": "2024-01-01T00:00:00Z",
                    "last_modified": "2024-01-05T10:15:00Z"
                }
            ],
            "timestamp": datetime.now().isoformat()
        }
        
        return rules_info
        
    except Exception as e:
        logger.error(f"룰 조회 중 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "RULES_ERROR",
                "message": "룰 조회 중 오류가 발생했습니다",
                "details": {"error_type": type(e).__name__}
            }
        )

@router.post(
    "/cache/clear",
    summary="캐시 초기화",
    description="시스템 캐시를 초기화합니다. 룰 변경 후 적용을 위해 사용됩니다.",
    response_model=Dict[str, Any]
)
async def clear_cache(
    cache_type: Optional[str] = Query(None, description="캐시 타입 (rules, products, all)")
):
    """캐시 초기화"""
    try:
        logger.info(f"캐시 초기화 요청: type={cache_type}")
        
        # 실제 캐시 초기화 로직 구현 필요
        cleared_caches = []
        
        if cache_type is None or cache_type == "all":
            cleared_caches = ["rules", "products", "aliases", "statistics"]
        else:
            cleared_caches = [cache_type]
        
        result = {
            "success": True,
            "cleared_caches": cleared_caches,
            "timestamp": datetime.now().isoformat(),
            "message": f"{len(cleared_caches)}개 캐시가 초기화되었습니다"
        }
        
        logger.info(f"캐시 초기화 완료: {cleared_caches}")
        return result
        
    except Exception as e:
        logger.error(f"캐시 초기화 중 오류: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "code": "CACHE_CLEAR_ERROR",
                "message": "캐시 초기화 중 오류가 발생했습니다",
                "details": {"error_type": type(e).__name__}
            }
        )