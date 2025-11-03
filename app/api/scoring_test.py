"""
개발/디버깅용 스코어링 테스트 API
- 경로 B는 이제 메인 추천 API에서 기본으로 사용됨
- 이 API는 개발자용 디버깅 및 성능 테스트 목적
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4
import logging

from app.models.request import RecommendationRequest
from app.models.postgres_models import Product
from app.models.personalization_models import (
    ProfileMatchResult, ProductIngredientAnalysis, 
    IngredientEffect, SafetyLevel, EffectType, MatchLevel
)
from app.services.scoring_engine import ScoreCalculator
from app.services.product_service import ProductService
from app.services.user_profile_service import UserProfileService

logger = logging.getLogger(__name__)

# 개발/디버깅용 라우터
router = APIRouter(
    prefix="/api/v1/debug",
    tags=["debug", "development"],
    include_in_schema=False  # Swagger 문서에서 숨김 (프로덕션용)
)

@router.post("/scoring-engine-detailed")
async def test_scoring_engine_detailed(request: RecommendationRequest):
    """
    [개발자용] 상세 스코어링 분석
    - 메인 API는 /api/v1/recommend 사용
    - 이 엔드포인트는 디버깅용 상세 정보 제공
    """
    try:
        logger.info("🧪 경로 B 테스트 시작")
        
        # 1. 실제 제품 데이터 조회 (경로 A와 동일한 수)
        product_service = ProductService()
        products = await product_service.get_candidate_products(request, limit=350)
        
        if not products:
            raise HTTPException(status_code=404, detail="테스트할 제품이 없습니다")
        
        logger.info(f"📦 테스트 제품 수: {len(products)}")
        
        # 2. 임시 프로필 매칭 결과 생성
        profile_matches = _create_mock_profile_matches(products, request)
        
        # 3. 임시 성분 분석 결과 생성
        ingredient_analyses = _create_mock_ingredient_analyses(products)
        
        # 4. 사용자 프로필 준비
        user_profile = None
        if request.user_profile:
            user_profile = {
                "age_group": getattr(request.user_profile, 'age_group', None),
                "skin_type": getattr(request.user_profile, 'skin_type', None),
                "skin_concerns": getattr(request.user_profile, 'skin_concerns', []),
                "allergies": getattr(request.user_profile, 'allergies', [])
            }
        
        # 5. 커스텀 가중치 (테스트용)
        custom_weights = {
            "intent": 30.0,
            "personalization": 40.0,
            "safety": 30.0
        }
        
        # 6. ScoreCalculator 경로 B 실행
        calculator = ScoreCalculator()
        start_time = datetime.now()
        
        results = await calculator.calculate_product_scores(
            products=products,
            intent_tags=request.intent_tags or [],
            profile_matches=profile_matches,
            ingredient_analyses=ingredient_analyses,
            user_profile=user_profile,
            custom_weights=custom_weights
        )
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # 7. 결과 정리 (점수순 정렬)
        sorted_results = sorted(
            results.items(),
            key=lambda x: x[1].final_score,
            reverse=True
        )
        
        # 8. 응답 생성
        response_data = {
            "test_info": {
                "method": "calculate_product_scores (경로 B)",
                "execution_time_seconds": execution_time,
                "products_tested": len(products),
                "weights_used": custom_weights,
                "timestamp": datetime.now().isoformat()
            },
            "input_summary": {
                "intent_tags": request.intent_tags or [],
                "user_profile": user_profile,
                "top_n": request.top_n
            },
            "results": []
        }
        
        # 상위 결과들 추가
        for rank, (product_id, score_result) in enumerate(sorted_results[:request.top_n], 1):
            product = next(p for p in products if p.product_id == product_id)
            
            result_item = {
                "rank": rank,
                "product_id": product_id,
                "product_name": product.name,
                "brand_name": product.brand_name,
                "category": product.category_name,
                "scores": {
                    "final_score": round(score_result.final_score, 2),
                    "normalized_score": round(score_result.normalized_score, 2),
                    "intent_score": round(score_result.score_breakdown.intent_score, 2),
                    "personalization_score": round(score_result.score_breakdown.personalization_score, 2),
                    "safety_score": round(score_result.score_breakdown.safety_score, 2)
                },
                "weights": {
                    "intent_weight": score_result.score_breakdown.intent_weight,
                    "personalization_weight": score_result.score_breakdown.personalization_weight,
                    "safety_weight": score_result.score_breakdown.safety_weight
                },
                "recommendation_reasons": score_result.recommendation_reasons[:3],
                "caution_notes": score_result.caution_notes[:2],
                "mock_data_used": {
                    "profile_match_generated": True,
                    "ingredient_analysis_generated": True
                }
            }
            
            response_data["results"].append(result_item)
        
        # 통계 정보 추가
        all_scores = [r.final_score for r in results.values()]
        response_data["statistics"] = {
            "average_score": round(sum(all_scores) / len(all_scores), 2),
            "highest_score": round(max(all_scores), 2),
            "lowest_score": round(min(all_scores), 2),
            "score_range": round(max(all_scores) - min(all_scores), 2)
        }
        
        logger.info(f"✅ 경로 B 테스트 완료: {len(results)}개 제품 처리")
        return response_data
        
    except Exception as e:
        logger.error(f"❌ 경로 B 테스트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"테스트 실행 실패: {str(e)}")

def _create_mock_profile_matches(products: List[Product], request: RecommendationRequest) -> Dict[int, ProfileMatchResult]:
    """임시 프로필 매칭 결과 생성"""
    profile_matches = {}
    
    for product in products:
        # 제품 특성에 따른 가상 점수 생성
        age_score = _calculate_mock_age_score(product, request)
        skin_score = _calculate_mock_skin_score(product, request)
        preference_score = _calculate_mock_preference_score(product, request)
        
        # 전체 점수 계산
        overall_score = (age_score * 0.4 + skin_score * 0.4 + preference_score * 0.2)
        
        # 매칭 이유 생성
        reasons = []
        if age_score > 70:
            reasons.append(f"연령대에 적합한 제품")
        if skin_score > 70:
            reasons.append(f"피부타입에 맞는 성분")
        if preference_score > 70:
            reasons.append(f"선호도 높은 카테고리")
        
        if not reasons:
            reasons.append("기본 매칭")
        
        profile_matches[product.product_id] = ProfileMatchResult(
            user_id=None,
            product_id=product.product_id,
            age_match_score=age_score,
            skin_type_match_score=skin_score,
            preference_match_score=preference_score,
            overall_match_score=overall_score,
            match_reasons=reasons
        )
    
    return profile_matches

def _calculate_mock_age_score(product: Product, request: RecommendationRequest) -> float:
    """연령대 매칭 점수 (임시)"""
    if not request.user_profile or not hasattr(request.user_profile, 'age_group'):
        return 70.0
    
    age_group = request.user_profile.age_group
    product_name = product.name.lower()
    
    # 간단한 키워드 기반 매칭
    if age_group == "20s":
        if any(keyword in product_name for keyword in ["young", "fresh", "daily", "basic"]):
            return 85.0
        elif any(keyword in product_name for keyword in ["anti-aging", "wrinkle", "mature"]):
            return 40.0
    elif age_group in ["40s", "50s"]:
        if any(keyword in product_name for keyword in ["anti-aging", "wrinkle", "firming", "intensive"]):
            return 90.0
        elif any(keyword in product_name for keyword in ["teen", "young"]):
            return 45.0
    
    return 70.0  # 기본 점수

def _calculate_mock_skin_score(product: Product, request: RecommendationRequest) -> float:
    """피부타입 매칭 점수 (임시)"""
    if not request.user_profile or not hasattr(request.user_profile, 'skin_type'):
        return 70.0
    
    skin_type = request.user_profile.skin_type
    product_tags = [tag.lower() for tag in (product.tags or [])]
    product_name = product.name.lower()
    
    # 피부타입별 키워드 매칭
    if skin_type == "dry":
        positive_keywords = ["moistur", "hydrat", "보습", "수분"]
        negative_keywords = ["oil control", "sebum", "피지"]
    elif skin_type == "oily":
        positive_keywords = ["oil control", "sebum", "피지", "수렴"]
        negative_keywords = ["heavy", "rich", "무거운"]
    elif skin_type == "sensitive":
        positive_keywords = ["gentle", "mild", "sensitive", "진정", "순한"]
        negative_keywords = ["strong", "active", "자극"]
    else:
        return 70.0
    
    score = 70.0
    
    # 긍정적 키워드
    for keyword in positive_keywords:
        if any(keyword in tag for tag in product_tags) or keyword in product_name:
            score += 10
            break
    
    # 부정적 키워드
    for keyword in negative_keywords:
        if any(keyword in tag for tag in product_tags) or keyword in product_name:
            score -= 15
            break
    
    return max(30.0, min(95.0, score))

def _calculate_mock_preference_score(product: Product, request: RecommendationRequest) -> float:
    """선호도 점수 (임시)"""
    # 카테고리별 기본 선호도
    category_scores = {
        "스킨케어": 80.0,
        "세럼": 85.0,
        "크림": 75.0,
        "클렌징": 70.0,
        "마스크": 65.0
    }
    
    base_score = category_scores.get(product.category_name, 70.0)
    
    # 의도 태그와의 매칭도 반영
    if request.intent_tags:
        intent_match = False
        product_tags = [tag.lower() for tag in (product.tags or [])]
        
        for intent in request.intent_tags:
            if intent.lower() in [tag.lower() for tag in product_tags]:
                intent_match = True
                break
        
        if intent_match:
            base_score += 10
    
    return min(95.0, base_score)

def _create_mock_ingredient_analyses(products: List[Product]) -> Dict[int, ProductIngredientAnalysis]:
    """임시 성분 분석 결과 생성"""
    analyses = {}
    
    for product in products:
        # 제품 특성에 따른 가상 성분 분석
        beneficial_effects = []
        harmful_effects = []
        safety_warnings = []
        allergy_risks = []
        
        product_name = product.name.lower()
        product_tags = [tag.lower() for tag in (product.tags or [])]
        
        # 유익한 효과 생성
        if any(keyword in product_name for keyword in ["vitamin", "비타민", "hyaluronic", "히알루론"]):
            beneficial_effects.append(
                IngredientEffect(
                    ingredient_id=1,
                    ingredient_name="비타민C" if "vitamin" in product_name else "히알루론산",
                    effect_type=EffectType.BENEFICIAL,
                    effect_description="항산화 및 미백 효과" if "vitamin" in product_name else "강력한 보습 효과",
                    confidence_score=0.9,
                    safety_level=SafetyLevel.SAFE
                )
            )
        
        # 부작용 생성 (특정 성분 포함 시)
        if any(keyword in product_name for keyword in ["retinol", "레티놀", "acid", "산"]):
            harmful_effects.append(
                IngredientEffect(
                    ingredient_id=2,
                    ingredient_name="레티놀" if "retinol" in product_name else "산성분",
                    effect_type=EffectType.HARMFUL,
                    effect_description="초기 자극 가능성",
                    confidence_score=0.7,
                    safety_level=SafetyLevel.CAUTION
                )
            )
            safety_warnings.append("점진적 사용 권장")
        
        # 알레르기 위험 (향료 포함 추정)
        if "fragrance" in product_name or "향" in product_name:
            allergy_risks.append("향료 알레르기 주의")
        
        analyses[product.product_id] = ProductIngredientAnalysis(
            product_id=product.product_id,
            product_name=product.name,
            total_ingredients=15,  # 가상 값
            analyzed_ingredients=12,  # 가상 값
            beneficial_effects=beneficial_effects,
            harmful_effects=harmful_effects,
            safety_warnings=safety_warnings,
            allergy_risks=allergy_risks
        )
    
    return analyses

@router.get("/performance-analysis")
async def analyze_performance():
    """
    [개발자용] 성능 분석
    - 경로 A vs B 성능 비교 (레거시)
    - 현재는 경로 B가 기본
    """
    try:
        # 간단한 테스트 요청 생성
        from app.models.request import UserProfile
        
        test_request = RecommendationRequest(
            intent_tags=["보습", "미백"],
            top_n=5,
            user_profile=UserProfile(
                age_group="30s",
                skin_type="dry"
            )
        )
        
        # 제품 조회 (동일한 수로)
        product_service = ProductService()
        products = await product_service.get_candidate_products(test_request, limit=350)
        
        if not products:
            raise HTTPException(status_code=404, detail="비교할 제품이 없습니다")
        
        calculator = ScoreCalculator()
        
        # 경로 A 실행
        start_a = datetime.now()
        results_a = calculator.evaluate_products(products, test_request, "test")
        time_a = (datetime.now() - start_a).total_seconds()
        
        # 경로 B 실행
        profile_matches = _create_mock_profile_matches(products, test_request)
        ingredient_analyses = _create_mock_ingredient_analyses(products)
        
        start_b = datetime.now()
        results_b = await calculator.calculate_product_scores(
            products=products,
            intent_tags=test_request.intent_tags,
            profile_matches=profile_matches,
            ingredient_analyses=ingredient_analyses,
            user_profile={"age_group": "30s", "skin_type": "dry"}
        )
        time_b = (datetime.now() - start_b).total_seconds()
        
        # 결과 비교
        comparison = {
            "test_info": {
                "products_tested": len(products),
                "timestamp": datetime.now().isoformat()
            },
            "path_a_results": {
                "method": "evaluate_products",
                "execution_time_seconds": time_a,
                "results_count": len(results_a),
                "sample_scores": {
                    pid: {
                        "final_score": result["final_score"],
                        "intent_score": result["intent_match_score"],
                        "penalty_score": result["penalty_score"]
                    }
                    for pid, result in list(results_a.items())[:3]
                }
            },
            "path_b_results": {
                "method": "calculate_product_scores",
                "execution_time_seconds": time_b,
                "results_count": len(results_b),
                "sample_scores": {
                    pid: {
                        "final_score": result.final_score,
                        "intent_score": result.score_breakdown.intent_score,
                        "personalization_score": result.score_breakdown.personalization_score,
                        "safety_score": result.score_breakdown.safety_score
                    }
                    for pid, result in list(results_b.items())[:3]
                }
            },
            "performance_comparison": {
                "path_a_faster": time_a < time_b,
                "speed_difference_ms": abs(time_a - time_b) * 1000,
                "path_a_ms": time_a * 1000,
                "path_b_ms": time_b * 1000
            }
        }
        
        return comparison
        
    except Exception as e:
        logger.error(f"❌ 비교 테스트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"비교 테스트 실패: {str(e)}")

@router.post("/user-profile-analysis")
async def analyze_user_profile_matching(request: RecommendationRequest):
    """
    [개발자용] 사용자 프로필 매칭 분석
    - 실제 사용자 데이터 기반 매칭 테스트
    """
    try:
        logger.info("🧪 경로 B + 실제 사용자 데이터 테스트 시작")
        
        # 1. 실제 제품 데이터 조회
        product_service = ProductService()
        products = await product_service.get_candidate_products(request, limit=50)  # 적당한 수로 제한
        
        if not products:
            raise HTTPException(status_code=404, detail="테스트할 제품이 없습니다")
        
        # 2. 실제 사용자 프로필 데이터 조회
        user_service = UserProfileService()
        real_users = user_service.get_sample_users(limit=5)
        
        if not real_users:
            raise HTTPException(status_code=404, detail="사용자 데이터가 없습니다")
        
        logger.info(f"📦 테스트 제품 수: {len(products)}")
        logger.info(f"👥 실제 사용자 수: {len(real_users)}")
        
        # 3. 실제 사용자 데이터 기반 프로필 매칭 결과 생성
        profile_matches = user_service.create_profile_matches_from_users(
            real_users, products, request.intent_tags or []
        )
        
        # 4. 임시 성분 분석 결과 생성 (여전히 목업)
        ingredient_analyses = _create_mock_ingredient_analyses(products)
        
        # 5. 첫 번째 실제 사용자 프로필 사용
        primary_user = real_users[0]
        user_profile = {
            "age_group": primary_user.age_group,
            "skin_type": primary_user.skin_type,
            "skin_concerns": primary_user.skin_concerns,
            "allergies": primary_user.allergies
        }
        
        # 6. 사용자 선호도 기반 커스텀 가중치
        preferences = primary_user.preferences
        if preferences.get("anti_aging_focus"):
            custom_weights = {"intent": 40.0, "personalization": 35.0, "safety": 25.0}
        elif preferences.get("gentle_products"):
            custom_weights = {"intent": 25.0, "personalization": 25.0, "safety": 50.0}
        else:
            custom_weights = {"intent": 30.0, "personalization": 40.0, "safety": 30.0}
        
        # 7. ScoreCalculator 경로 B 실행
        calculator = ScoreCalculator()
        start_time = datetime.now()
        
        results = await calculator.calculate_product_scores(
            products=products,
            intent_tags=request.intent_tags or [],
            profile_matches=profile_matches,
            ingredient_analyses=ingredient_analyses,
            user_profile=user_profile,
            custom_weights=custom_weights
        )
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # 8. 결과 정리 (점수순 정렬)
        sorted_results = sorted(
            results.items(),
            key=lambda x: x[1].final_score,
            reverse=True
        )
        
        # 9. 응답 생성
        response_data = {
            "test_info": {
                "method": "calculate_product_scores (경로 B + 실제 사용자)",
                "execution_time_seconds": execution_time,
                "products_tested": len(products),
                "real_users_used": len(real_users),
                "weights_used": custom_weights,
                "timestamp": datetime.now().isoformat()
            },
            "user_data": {
                "primary_user_id": primary_user.user_id,
                "age_group": primary_user.age_group,
                "skin_type": primary_user.skin_type,
                "skin_concerns": primary_user.skin_concerns,
                "allergies": primary_user.allergies,
                "preferences": primary_user.preferences,
                "data_source": "supabase" if primary_user.user_id.startswith("mock_") == False else "fallback_mock"
            },
            "input_summary": {
                "intent_tags": request.intent_tags or [],
                "top_n": request.top_n
            },
            "results": []
        }
        
        # 상위 결과들 추가
        for rank, (product_id, score_result) in enumerate(sorted_results[:request.top_n], 1):
            product = next(p for p in products if p.product_id == product_id)
            
            result_item = {
                "rank": rank,
                "product_id": product_id,
                "product_name": product.name,
                "brand_name": product.brand_name,
                "category": product.category_name,
                "scores": {
                    "final_score": round(score_result.final_score, 2),
                    "normalized_score": round(score_result.normalized_score, 2),
                    "intent_score": round(score_result.score_breakdown.intent_score, 2),
                    "personalization_score": round(score_result.score_breakdown.personalization_score, 2),
                    "safety_score": round(score_result.score_breakdown.safety_score, 2)
                },
                "weights": {
                    "intent_weight": score_result.score_breakdown.intent_weight,
                    "personalization_weight": score_result.score_breakdown.personalization_weight,
                    "safety_weight": score_result.score_breakdown.safety_weight
                },
                "recommendation_reasons": score_result.recommendation_reasons[:3],
                "caution_notes": score_result.caution_notes[:2],
                "personalization_details": {
                    "age_match": profile_matches[product_id].age_match_score,
                    "skin_type_match": profile_matches[product_id].skin_type_match_score,
                    "preference_match": profile_matches[product_id].preference_match_score,
                    "match_reasons": profile_matches[product_id].match_reasons,
                    "mismatch_reasons": profile_matches[product_id].mismatch_reasons
                }
            }
            
            response_data["results"].append(result_item)
        
        # 통계 정보 추가
        all_scores = [r.final_score for r in results.values()]
        response_data["statistics"] = {
            "average_score": round(sum(all_scores) / len(all_scores), 2),
            "highest_score": round(max(all_scores), 2),
            "lowest_score": round(min(all_scores), 2),
            "score_range": round(max(all_scores) - min(all_scores), 2)
        }
        
        # 사용자 통계 추가
        user_stats = user_service.get_user_statistics()
        response_data["user_statistics"] = user_stats
        
        logger.info(f"✅ 경로 B + 실제 사용자 테스트 완료: {len(results)}개 제품 처리")
        return response_data
        
    except Exception as e:
        logger.error(f"❌ 경로 B + 실제 사용자 테스트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"테스트 실행 실패: {str(e)}")

@router.get("/user-profiles/sample")
async def get_sample_user_profiles():
    """
    샘플 사용자 프로필 조회 (Supabase 또는 목업)
    """
    try:
        user_service = UserProfileService()
        
        # 샘플 사용자들 조회
        users = user_service.get_sample_users(limit=10)
        
        # 사용자 통계
        stats = user_service.get_user_statistics()
        
        return {
            "user_statistics": stats,
            "sample_users": [
                {
                    "user_id": user.user_id,
                    "age_group": user.age_group,
                    "skin_type": user.skin_type,
                    "skin_concerns": user.skin_concerns,
                    "allergies": user.allergies,
                    "preferences": user.preferences,
                    "created_at": user.created_at,
                    "data_source": "supabase" if not user.user_id.startswith("mock_") else "fallback_mock"
                }
                for user in users
            ],
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"사용자 프로필 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"사용자 프로필 조회 실패: {str(e)}")

@router.post("/user-profiles/setup-mock-data")
async def setup_mock_user_data():
    """
    Supabase에 목업 사용자 데이터 추가
    """
    try:
        user_service = UserProfileService()
        
        # 1. 테이블 구조 확인
        table_info = user_service.check_user_table_structure()
        
        # 2. 테이블이 없으면 생성
        if not table_info.get("table_exists", False):
            logger.info("user_profiles 테이블이 없어서 생성합니다")
            create_result = user_service.create_user_profiles_table()
            if not create_result.get("success", False):
                raise HTTPException(status_code=500, detail=f"테이블 생성 실패: {create_result.get('error')}")
        
        # 3. 목업 데이터 추가
        insert_result = user_service.insert_mock_users_to_supabase()
        
        # 4. 결과 확인
        updated_stats = user_service.get_user_statistics()
        sample_users = user_service.get_sample_users(limit=5)
        
        return {
            "setup_info": {
                "table_existed": table_info.get("table_exists", False),
                "table_structure": table_info.get("columns", []),
                "insert_result": insert_result,
                "timestamp": datetime.now().isoformat()
            },
            "verification": {
                "user_statistics": updated_stats,
                "sample_users_count": len(sample_users),
                "sample_users": [
                    {
                        "user_id": user.user_id,
                        "age_group": user.age_group,
                        "skin_type": user.skin_type,
                        "skin_concerns": user.skin_concerns,
                        "data_source": "supabase" if not user.user_id.startswith("mock_") else "fallback"
                    }
                    for user in sample_users[:3]
                ]
            }
        }
        
    except Exception as e:
        logger.error(f"목업 데이터 설정 실패: {e}")
        raise HTTPException(status_code=500, detail=f"목업 데이터 설정 실패: {str(e)}")

@router.get("/user-profiles/table-info")
async def get_user_table_info():
    """
    사용자 프로필 테이블 정보 조회
    """
    try:
        user_service = UserProfileService()
        table_info = user_service.check_user_table_structure()
        
        return {
            "table_info": table_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"테이블 정보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"테이블 정보 조회 실패: {str(e)}")

@router.get("/ingredient-analysis/{product_id}")
async def test_ingredient_analysis(product_id: int):
    """
    특정 제품의 실제 성분 분석 테스트
    """
    try:
        from app.services.ingredient_service import IngredientService
        
        ingredient_service = IngredientService()
        
        # 실제 성분 안전성 정보 조회
        safety_info = ingredient_service.get_ingredient_safety_info(product_id)
        
        # 제품 기본 정보도 조회
        from app.services.product_service import ProductService
        product_service = ProductService()
        
        # 간단한 제품 정보 조회 (직접 DB 쿼리)
        from app.database.postgres_sync import get_postgres_sync_db
        db = get_postgres_sync_db()
        
        product_query = "SELECT product_id, name, brand_name, tags FROM products WHERE product_id = %s"
        product_rows = db._execute_sync(product_query, (product_id,))
        product_info = product_rows[0] if product_rows else None
        
        return {
            "product_info": product_info,
            "ingredient_safety_analysis": safety_info,
            "analysis_summary": {
                "total_ingredients": safety_info.get('total_ingredients', 0),
                "allergy_risk_count": safety_info.get('allergy_ingredients', 0),
                "twenty_risk_count": safety_info.get('twenty_ingredients', 0),
                "high_risk_count": len(safety_info.get('high_risk_ingredients', [])),
                "beneficial_count": len(safety_info.get('beneficial_ingredients', [])),
                "warnings_count": len(safety_info.get('warnings', []))
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"성분 분석 테스트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"성분 분석 테스트 실패: {str(e)}")

@router.get("/ingredient-tables/check")
async def check_ingredient_tables():
    """
    성분 관련 테이블 존재 여부 확인
    """
    try:
        from app.database.postgres_sync import get_postgres_sync_db
        db = get_postgres_sync_db()
        
        # 테이블 존재 여부 확인
        tables_query = """
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('ingredients', 'product_ingredients')
        ORDER BY table_name
        """
        
        tables = db._execute_sync(tables_query)
        
        result = {
            "existing_tables": [t['table_name'] for t in tables],
            "ingredients_table_exists": any(t['table_name'] == 'ingredients' for t in tables),
            "product_ingredients_table_exists": any(t['table_name'] == 'product_ingredients' for t in tables)
        }
        
        # 각 테이블의 샘플 데이터 확인
        if result["ingredients_table_exists"]:
            ingredients_sample = db._execute_sync("SELECT COUNT(*) as count FROM ingredients")
            result["ingredients_count"] = ingredients_sample[0]['count'] if ingredients_sample else 0
            
            if result["ingredients_count"] > 0:
                sample_ingredients = db._execute_sync("SELECT ingredient_id, korean, english, ewg_grade FROM ingredients LIMIT 3")
                result["ingredients_sample"] = sample_ingredients
        
        if result["product_ingredients_table_exists"]:
            product_ingredients_sample = db._execute_sync("SELECT COUNT(*) as count FROM product_ingredients")
            result["product_ingredients_count"] = product_ingredients_sample[0]['count'] if product_ingredients_sample else 0
            
            if result["product_ingredients_count"] > 0:
                sample_relations = db._execute_sync("SELECT product_id, ingredient_id FROM product_ingredients LIMIT 3")
                result["product_ingredients_sample"] = sample_relations
        
        return result
        
    except Exception as e:
        logger.error(f"성분 테이블 확인 실패: {e}")
        raise HTTPException(status_code=500, detail=f"성분 테이블 확인 실패: {str(e)}")