from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4
import time
import logging

# 모델 imports
from app.models.request import RecommendationRequest, RequestSummary
from app.models.response import (
    RecommendationResponse, ProductRecommendation, ExecutionSummary, 
    PipelineStatistics, ErrorResponse, ErrorDetail
)

# 서비스 imports
from app.services import (
    ProductService, IngredientService, RuleService,
    EligibilityEngine, ScoringEngine, RankingService
)
from app.utils import AliasMapper, LoggerService, RequestValidator, ValidationError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/recommendations", tags=["Cosmetic Recommendations"])


@router.post("/", response_model=RecommendationResponse)
async def get_cosmetic_recommendations(
    request: RecommendationRequest,
    background_tasks: BackgroundTasks
) -> RecommendationResponse:
    """
    화장품 추천 API
    
    전체 추천 파이프라인을 실행하여 사용자 조건에 맞는 화장품을 추천합니다.
    
    파이프라인:
    1. 입력 검증 및 정제
    2. 후보 제품 조회 (SQLite)
    3. 배제 평가 (eligibility rules)
    4. 감점 평가 (scoring rules)  
    5. 정렬 및 순위 결정
    6. 로깅 및 응답 생성
    """
    request_id = uuid4()
    start_time = time.time()
    
    # 서비스 초기화
    validator = RequestValidator()
    product_service = ProductService()
    eligibility_engine = EligibilityEngine()
    scoring_engine = ScoringEngine()
    ranking_service = RankingService()
    logger_service = LoggerService()
    rule_service = RuleService()
    
    try:
        logger.info(f"추천 요청 시작: {request_id}")
        
        # 1단계: 입력 검증 및 정제
        validation_start = time.time()
        sanitized_request, validation_errors = validator.validate_and_sanitize(request)
        
        if validation_errors:
            # 검증 오류가 있는 경우 400 에러 반환
            error_messages = [f"{error.field}: {error.message}" for error in validation_errors]
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "입력 검증 실패",
                        "details": error_messages
                    },
                    "timestamp": datetime.now().isoformat(),
                    "request_id": str(request_id)
                }
            )
        
        validation_time = (time.time() - validation_start) * 1000
        
        # 2단계: 후보 제품 조회
        query_start = time.time()
        
        # 실행 가능성 검증
        is_feasible, feasibility_message = product_service.validate_request_feasibility(sanitized_request)
        if not is_feasible:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "NO_CANDIDATES",
                        "message": feasibility_message,
                        "details": {"request": sanitized_request.model_dump()}
                    },
                    "timestamp": datetime.now().isoformat(),
                    "request_id": str(request_id)
                }
            )
        
        # 후보 제품 조회
        candidate_products = product_service.get_candidate_products(sanitized_request, limit=200)
        if not candidate_products:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "NO_PRODUCTS_FOUND",
                        "message": "조건에 맞는 제품을 찾을 수 없습니다",
                        "details": {"request": sanitized_request.model_dump()}
                    },
                    "timestamp": datetime.now().isoformat(),
                    "request_id": str(request_id)
                }
            )
        
        query_time = (time.time() - query_start) * 1000
        
        # 3단계: 배제 평가
        eligibility_start = time.time()
        eligibility_result = eligibility_engine.evaluate_products(
            candidate_products, sanitized_request, request_id
        )
        
        # 배제 후 남은 제품들
        remaining_products = [
            p for p in candidate_products 
            if p.product_id not in eligibility_result.excluded_products
        ]
        
        if not remaining_products:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": {
                        "code": "ALL_PRODUCTS_EXCLUDED",
                        "message": "모든 제품이 안전성 검토에서 배제되었습니다",
                        "details": {
                            "total_candidates": len(candidate_products),
                            "excluded_count": len(eligibility_result.excluded_products),
                            "exclusion_reasons": list(eligibility_result.exclusion_reasons.values())[:3]
                        }
                    },
                    "timestamp": datetime.now().isoformat(),
                    "request_id": str(request_id)
                }
            )
        
        eligibility_time = (time.time() - eligibility_start) * 1000
        
        # 4단계: 감점 평가
        scoring_start = time.time()
        scoring_results = scoring_engine.evaluate_products(
            remaining_products, sanitized_request, request_id
        )
        scoring_time = (time.time() - scoring_start) * 1000
        
        # 5단계: 정렬 및 순위 결정
        ranking_start = time.time()
        ranked_products = ranking_service.rank_products(
            remaining_products, scoring_results, sanitized_request, eligibility_result.excluded_products
        )
        
        # 최종 추천 결과 생성
        final_recommendations = ranking_service.convert_to_recommendation_response(
            ranked_products, top_n=sanitized_request.top_n
        )
        ranking_time = (time.time() - ranking_start) * 1000
        
        # 6단계: 응답 생성
        total_time = time.time() - start_time
        
        # 룰셋 정보
        rule_stats = rule_service.get_rule_statistics()
        
        # 실행 요약
        execution_summary = ExecutionSummary(
            request_id=request_id,
            timestamp=datetime.now(),
            success=True,
            execution_time_seconds=total_time,
            ruleset_version=rule_stats.get('ruleset_version', 'unknown'),
            active_rules_count=rule_stats.get('active_rules', 0)
        )
        
        # 입력 요약
        input_summary = RequestSummary.from_request(sanitized_request).model_dump()
        
        # 파이프라인 통계
        pipeline_statistics = PipelineStatistics(
            total_candidates=len(candidate_products),
            excluded_by_rules=eligibility_result.total_excluded,
            penalized_products=len([r for r in scoring_results.values() if r.penalty_score < 0]),
            final_recommendations=len(final_recommendations),
            eligibility_rules_applied=len(set(hit.rule_id for hit in eligibility_result.rule_hits)),
            scoring_rules_applied=len(set(hit.rule_id for r in scoring_results.values() for hit in r.rule_hits)),
            query_time_ms=query_time,
            evaluation_time_ms=eligibility_time + scoring_time,
            ranking_time_ms=ranking_time,
            total_time_ms=total_time * 1000
        )
        
        # 최종 응답
        response = RecommendationResponse(
            execution_summary=execution_summary,
            input_summary=input_summary,
            pipeline_statistics=pipeline_statistics,
            recommendations=final_recommendations
        )
        
        # 백그라운드 로깅
        background_tasks.add_task(
            _log_recommendation_request,
            logger_service,
            request_id,
            sanitized_request.model_dump(),
            total_time,
            len(candidate_products),
            eligibility_result.total_excluded,
            len(final_recommendations)
        )
        
        logger.info(f"추천 요청 완료: {request_id} ({total_time:.3f}초)")
        
        return response
        
    except HTTPException:
        # HTTP 예외는 그대로 재발생
        raise
    except Exception as e:
        # 예상치 못한 오류
        logger.error(f"추천 요청 오류: {request_id} - {str(e)}")
        
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "내부 서버 오류가 발생했습니다",
                    "details": {"error_type": type(e).__name__}
                },
                "timestamp": datetime.now().isoformat(),
                "request_id": str(request_id)
            }
        )
    
    finally:
        # 리소스 정리
        try:
            validator.close()
            eligibility_engine.close()
            scoring_engine.close()
            logger_service.close_session()
            rule_service.close_session()
        except Exception as e:
            logger.warning(f"리소스 정리 중 오류: {e}")


async def _log_recommendation_request(
    logger_service: LoggerService,
    request_id,
    input_data: Dict[str, Any],
    execution_time_seconds: float,
    products_found: int,
    products_excluded: int,
    products_recommended: int
):
    """백그라운드 로깅 작업"""
    try:
        logger_service.log_recommendation_request(
            request_id=request_id,
            input_data=input_data,
            execution_time_seconds=execution_time_seconds,
            products_found=products_found,
            products_excluded=products_excluded,
            products_recommended=products_recommended
        )
    except Exception as e:
        logger.error(f"백그라운드 로깅 실패: {e}")
    finally:
        logger_service.close_session()


@router.get("/sample")
async def get_sample_recommendation():
    """샘플 추천 요청 (테스트용)"""
    from app.models.request import UseContext, MedProfile, PriceRange
    
    sample_request = RecommendationRequest(
        intent_tags=["보습", "진정"],
        category_like="로션",
        use_context=UseContext(leave_on=True, face=True),
        med_profile=MedProfile(codes=["B01AA03"]),
        price=PriceRange(min_price=10000, max_price=50000),
        top_n=5
    )
    
    return {
        "message": "샘플 추천 요청",
        "sample_request": sample_request.model_dump(),
        "endpoint": "POST /api/v1/recommendations/",
        "description": "위 샘플 요청을 POST로 전송하여 실제 추천 결과를 받을 수 있습니다"
    }


# 운영 API 엔드포인트들

@router.get("/health", response_model=Dict[str, Any])
async def get_recommendation_health():
    """
    추천 시스템 헬스체크
    
    시스템 상태, 데이터베이스 연결, 룰셋 정보 등을 확인합니다.
    """
    try:
        # 서비스 초기화
        product_service = ProductService()
        rule_service = RuleService()
        logger_service = LoggerService()
        
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0"
        }
        
        # 데이터베이스 연결 상태
        try:
            # SQLite 연결 테스트
            product_count = product_service.get_total_product_count()
            health_data["sqlite_status"] = "connected"
            health_data["total_products"] = product_count
        except Exception as e:
            health_data["sqlite_status"] = f"error: {str(e)}"
            health_data["status"] = "degraded"
        
        try:
            # PostgreSQL 연결 테스트
            rule_stats = rule_service.get_rule_statistics()
            health_data["postgres_status"] = "connected"
            health_data["ruleset"] = rule_stats
        except Exception as e:
            health_data["postgres_status"] = f"error: {str(e)}"
            health_data["status"] = "degraded"
        
        # 로깅 시스템 상태
        try:
            logging_stats = logger_service.get_logging_statistics(days=1)
            health_data["logging_status"] = "active"
            health_data["recent_requests"] = logging_stats["total_requests"]
        except Exception as e:
            health_data["logging_status"] = f"error: {str(e)}"
            health_data["status"] = "degraded"
        
        return health_data
        
    except Exception as e:
        logger.error(f"헬스체크 오류: {e}")
        return {
            "status": "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "error": str(e)
        }
    finally:
        try:
            rule_service.close_session()
            logger_service.close_session()
        except:
            pass


@router.get("/stats", response_model=Dict[str, Any])
async def get_recommendation_statistics():
    """
    추천 시스템 통계 정보
    
    제품, 성분, 룰, 로깅 등의 상세 통계를 제공합니다.
    """
    try:
        # 서비스 초기화
        product_service = ProductService()
        ingredient_service = IngredientService()
        rule_service = RuleService()
        logger_service = LoggerService()
        alias_mapper = AliasMapper()
        
        stats = {
            "timestamp": datetime.now().isoformat(),
            "system_version": "1.0.0"
        }
        
        # 제품 통계
        try:
            product_stats = product_service.get_product_statistics()
            stats["products"] = product_stats
        except Exception as e:
            stats["products"] = {"error": str(e)}
        
        # 성분 통계
        try:
            ingredient_stats = ingredient_service.get_ingredient_statistics()
            tag_stats = ingredient_service.get_tag_statistics()
            stats["ingredients"] = {**ingredient_stats, "tag_stats": tag_stats}
        except Exception as e:
            stats["ingredients"] = {"error": str(e)}
        
        # 룰 통계
        try:
            rule_stats = rule_service.get_rule_statistics()
            rule_integrity = rule_service.validate_ruleset_integrity()
            stats["rules"] = {**rule_stats, "integrity": rule_integrity}
        except Exception as e:
            stats["rules"] = {"error": str(e)}
        
        # 별칭 통계
        try:
            alias_stats = alias_mapper.get_alias_statistics()
            stats["aliases"] = alias_stats
        except Exception as e:
            stats["aliases"] = {"error": str(e)}
        
        # 로깅 통계
        try:
            logging_stats_7d = logger_service.get_logging_statistics(days=7)
            logging_stats_30d = logger_service.get_logging_statistics(days=30)
            stats["logging"] = {
                "last_7_days": logging_stats_7d,
                "last_30_days": logging_stats_30d
            }
        except Exception as e:
            stats["logging"] = {"error": str(e)}
        
        return stats
        
    except Exception as e:
        logger.error(f"통계 조회 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "STATS_ERROR",
                    "message": "통계 조회 중 오류가 발생했습니다",
                    "details": str(e)
                },
                "timestamp": datetime.now().isoformat()
            }
        )
    finally:
        try:
            rule_service.close_session()
            logger_service.close_session()
            alias_mapper.close()
        except:
            pass


@router.get("/logs/{request_id}")
async def get_request_logs(request_id: str):
    """
    특정 요청의 상세 로그 조회
    
    요청 ID를 통해 해당 요청의 전체 실행 과정을 추적합니다.
    """
    try:
        from uuid import UUID
        
        # UUID 형식 검증
        try:
            uuid_obj = UUID(request_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": {
                        "code": "INVALID_REQUEST_ID",
                        "message": "잘못된 요청 ID 형식입니다",
                        "details": {"request_id": request_id}
                    },
                    "timestamp": datetime.now().isoformat()
                }
            )
        
        logger_service = LoggerService()
        
        try:
            # 요청 요약 조회
            summary = logger_service.get_request_summary(uuid_obj)
            
            if not summary:
                raise HTTPException(
                    status_code=404,
                    detail={
                        "error": {
                            "code": "REQUEST_NOT_FOUND",
                            "message": "해당 요청 ID를 찾을 수 없습니다",
                            "details": {"request_id": request_id}
                        },
                        "timestamp": datetime.now().isoformat()
                    }
                )
            
            return summary
            
        finally:
            logger_service.close_session()
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"요청 로그 조회 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "LOG_RETRIEVAL_ERROR",
                    "message": "로그 조회 중 오류가 발생했습니다",
                    "details": str(e)
                },
                "timestamp": datetime.now().isoformat()
            }
        )


@router.get("/rules/health")
async def get_rules_health():
    """
    룰셋 상태 정보
    
    룰셋 버전, 활성 룰 수 등 운영 지표를 제공합니다.
    """
    try:
        rule_service = RuleService()
        
        try:
            # 룰 통계
            rule_stats = rule_service.get_rule_statistics()
            
            # 룰셋 무결성 검증
            integrity = rule_service.validate_ruleset_integrity()
            
            # 별칭 정보
            alias_map = rule_service.get_cached_alias_map()
            
            # 룰 히트 통계 (최근 7일)
            hit_stats = rule_service.get_rule_hit_statistics(days=7)
            
            return {
                "status": "healthy" if integrity["is_valid"] else "warning",
                "timestamp": datetime.now().isoformat(),
                "ruleset_version": rule_stats.get("ruleset_version", "unknown"),
                "total_rules": rule_stats.get("total_rules", 0),
                "active_rules": rule_stats.get("active_rules", 0),
                "eligibility_rules": rule_stats.get("eligibility_rules", 0),
                "scoring_rules": rule_stats.get("scoring_rules", 0),
                "total_aliases": len(alias_map),
                "integrity_check": integrity,
                "recent_activity": hit_stats,
                "cache_status": "active"
            }
            
        finally:
            rule_service.close_session()
            
    except Exception as e:
        logger.error(f"룰 헬스체크 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "RULES_HEALTH_ERROR",
                    "message": "룰 상태 확인 중 오류가 발생했습니다",
                    "details": str(e)
                },
                "timestamp": datetime.now().isoformat()
            }
        )


@router.post("/validate")
async def validate_recommendation_request(request: RecommendationRequest):
    """
    추천 요청 검증 (실제 추천 실행 없이)
    
    요청의 유효성을 검증하고 예상 결과를 미리 확인합니다.
    """
    try:
        validator = RequestValidator()
        product_service = ProductService()
        
        try:
            # 입력 검증
            sanitized_request, validation_errors = validator.validate_and_sanitize(request)
            
            validation_result = {
                "is_valid": len(validation_errors) == 0,
                "validation_errors": [
                    {
                        "field": error.field,
                        "message": error.message,
                        "code": error.code
                    }
                    for error in validation_errors
                ],
                "sanitized_request": sanitized_request.model_dump() if len(validation_errors) == 0 else None
            }
            
            # 유효한 경우 실행 가능성 확인
            if validation_result["is_valid"]:
                is_feasible, feasibility_message = product_service.validate_request_feasibility(sanitized_request)
                
                validation_result.update({
                    "feasibility": {
                        "is_feasible": is_feasible,
                        "message": feasibility_message
                    }
                })
                
                # 예상 후보 수 (실제 조회 없이 추정)
                if is_feasible:
                    validation_result["estimated_candidates"] = "10-50개 예상"
            
            return validation_result
            
        finally:
            validator.close()
            
    except Exception as e:
        logger.error(f"요청 검증 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "요청 검증 중 오류가 발생했습니다",
                    "details": str(e)
                },
                "timestamp": datetime.now().isoformat()
            }
        )