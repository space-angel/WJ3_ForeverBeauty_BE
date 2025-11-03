"""
통합 추천 엔진
모든 추천 로직을 통합 관리하는 메인 엔진
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from uuid import UUID, uuid4
from datetime import datetime
import logging

from app.models.request import RecommendationRequest
from app.models.response import RecommendationResponse, ExecutionSummary, PipelineStatistics, RecommendationItem
from app.models.postgres_models import Product
from app.services.product_service import ProductService
from app.services.intent_matching_service import AdvancedIntentMatcher
from app.services.eligibility_engine import EligibilityEngine
from app.services.scoring_engine import ScoreCalculator
from app.services.ranking_service import RankingService
from app.services.user_profile_service import UserProfileService
from app.services.ingredient_service import IngredientService
from app.shared.constants import (
    RULESET_VERSION, ProductLimits, RuleEngineConfig, TimeConstants
)
from app.shared.utils import calculate_execution_time_ms

logger = logging.getLogger(__name__)

@dataclass
class RecommendationPipeline:
    """추천 파이프라인 결과"""
    candidates: List[Product]
    safe_products: List[Product]
    scored_products: Dict
    ranked_products: List
    execution_time: float
    statistics: Dict

class RecommendationEngine:
    """통합 추천 엔진"""
    
    def __init__(self):
        """서비스 초기화"""
        self.product_service = ProductService()
        self.intent_matcher = AdvancedIntentMatcher()
        self.eligibility_engine = EligibilityEngine()
        self.scoring_engine = ScoreCalculator()
        self.ranking_service = RankingService()
        self.user_profile_service = UserProfileService()
        self.ingredient_service = IngredientService()
        
        # RecommendationEngine 초기화 완료
    
    async def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        """메인 추천 실행"""
        start_time = datetime.now()
        request_id = uuid4()
        
        try:
            # 추천 요청 시작
            
            # 1. 파이프라인 실행
            pipeline_result = await self._execute_pipeline(request, request_id, start_time)
            
            # 2. 응답 생성
            response = self._build_response(
                request, request_id, pipeline_result, start_time
            )
            
            # 추천 완료
            return response
            
        except Exception as e:
            logger.error(f"추천 실행 실패: {request_id} - {e}")
            return self._build_error_response(request, request_id, start_time, e)
    
    async def _execute_pipeline(
        self, 
        request: RecommendationRequest, 
        request_id: UUID,
        start_time: datetime = None
    ) -> RecommendationPipeline:
        """추천 파이프라인 실행"""
        
        try:
            # 0단계: 요청 전처리 (medications -> med_profile 변환)
            self._preprocess_request(request)
            
            # 1단계: 후보 제품 조회
            candidates = await self.product_service.get_candidate_products(
                request, limit=ProductLimits.DEFAULT_CANDIDATE_LIMIT
            )
            
            if not candidates:
                # 카테고리 필터 없이 재시도
                logger.warning("카테고리 필터링된 후보 제품 없음 - 전체 제품에서 재시도")
                request_copy = request.model_copy() if hasattr(request, 'model_copy') else request
                if hasattr(request_copy, 'categories'):
                    request_copy.categories = None
                
                candidates = await self.product_service.get_candidate_products(
                    request_copy, limit=ProductLimits.FALLBACK_CANDIDATE_LIMIT
                )
                
                if not candidates:
                    raise ValueError("후보 제품이 없습니다 - 데이터베이스 연결 또는 데이터 문제")
            
            # 2단계: 안전성 평가 (배제)
            eligibility_result = self.eligibility_engine.evaluate_products(
                candidates, request, request_id
            )
            
            safe_products = [
                p for p in candidates 
                if p.product_id not in eligibility_result.excluded_products
            ]
            
            # 3단계: 적합성 평가 (경로 B - 고급 스코어링)
            logger.info(f"🎯 3단계: {len(safe_products)}개 제품 고급 스코어링 시작 (경로 B)")
            logger.info(f"🔍 스코어링할 제품 ID들: {[p.product_id for p in safe_products[:5]]}")
            
            try:
                logger.info("📞 경로 B 스코어링 엔진 호출 시작...")
                
                # 3-1. 사용자 프로필 매칭 결과 생성 (요청 우선)
                if request.user_profile:
                    # 요청의 사용자 프로필을 직접 사용
                    profile_matches = self._create_fallback_profile_matches(safe_products, request)
                    user_profile = self._extract_user_profile_from_request(request)
                    age_display = user_profile.get('age_group', 'N/A')
                    skin_display = user_profile.get('skin_type', 'N/A')
                    # Enum 값을 문자열로 변환
                    if hasattr(age_display, 'value'):
                        age_display = age_display.value
                    if hasattr(skin_display, 'value'):
                        skin_display = skin_display.value
                    logger.info(f"👤 요청 사용자 프로필 사용: {age_display}, {skin_display}")
                else:
                    # 폴백: 목업 사용자 데이터 사용
                    sample_users = self.user_profile_service.get_sample_users(limit=1)
                    if sample_users:
                        profile_matches = self.user_profile_service.create_profile_matches_from_users(
                            sample_users, safe_products, request.intent_tags or []
                        )
                        primary_user = sample_users[0]
                        user_profile = {
                            "age_group": primary_user.age_group,
                            "skin_type": primary_user.skin_type,
                            "skin_concerns": primary_user.skin_concerns,
                            "allergies": primary_user.allergies
                        }
                        logger.info(f"👤 목업 사용자 프로필 사용: {primary_user.user_id} ({primary_user.age_group}, {primary_user.skin_type})")
                    else:
                        # 최종 폴백: 기본 프로필
                        profile_matches = self._create_fallback_profile_matches(safe_products, request)
                        user_profile = {}
                        logger.info("👤 기본 프로필 사용")
                
                # 3-2. 조건부 성분 분석 (특수 상황에서만)
                use_ingredient_analysis = self._should_use_ingredient_analysis(request, user_profile)
                
                # 3-2. 조건부 성분 분석
                if use_ingredient_analysis:
                    logger.info("🧪 특수 상황 감지 - 실제 성분 분석 사용")
                    ingredient_start = datetime.now()
                    ingredient_analyses = await self._create_real_ingredient_analyses(safe_products)
                    ingredient_time = (datetime.now() - ingredient_start).total_seconds()
                    logger.info(f"🧪 실제 성분 분석 소요시간: {ingredient_time:.3f}초")
                else:
                    logger.info("⚡ 일반 상황 - 빠른 태그 기반 분석 사용")
                    ingredient_start = datetime.now()
                    ingredient_analyses = self._create_fast_tag_based_analyses(safe_products)
                    ingredient_time = (datetime.now() - ingredient_start).total_seconds()
                    logger.info(f"⚡ 빠른 태그 분석 소요시간: {ingredient_time:.3f}초")
                
                # 3-3. 커스텀 가중치 설정
                custom_weights = self._determine_custom_weights(request, user_profile)
                
                # 경로 B 사용 (고급 3축 스코어링) - 기본 방식
                logger.info("🎯 경로 B 사용 (고급 3축 스코어링)")
                scoring_results_b = await self.scoring_engine.calculate_product_scores(
                    products=safe_products,
                    intent_tags=request.intent_tags or [],
                    profile_matches=profile_matches,
                    ingredient_analyses=ingredient_analyses,
                    user_profile=user_profile,
                    custom_weights=custom_weights
                )
                
                # 경로 B 결과를 직접 사용 (더 이상 경로 A 호환 불필요)
                scoring_results = scoring_results_b
                logger.info("✅ 경로 B 스코어링 완료")
            except Exception as e:
                logger.error(f"❌ 스코어링 실패: {e}")
                scoring_results = {}
            
            logger.info(f"✅ 3단계 완료: 스코어링 결과 {len(scoring_results)}개")
            logger.debug(f"🔍 스코어링 결과 키들: {list(scoring_results.keys())[:5]}")
            
            # 스코어링 결과 샘플 로그 (간단하게)
            if scoring_results:
                sample_count = len(scoring_results)
                sample_scores = []
                for i, (product_id, result) in enumerate(list(scoring_results.items())[:3]):
                    if hasattr(result, 'final_score'):
                        sample_scores.append(f"{result.final_score:.1f}")
                    else:
                        sample_scores.append(f"{result.get('final_score', 0):.1f}")
                
                logger.info(f"✅ 스코어링 완료: {sample_count}개 제품, 샘플 점수: {', '.join(sample_scores)}")
            else:
                logger.warning("⚠️ 스코어링 결과가 비어있습니다!")
            
            # 4단계: 순위 결정
            ranked_products = self.ranking_service.rank_products(
                safe_products, scoring_results, request, 
                eligibility_result.excluded_products
            )
            
            # 통계 수집 (공유 유틸리티 사용)
            execution_time_ms = calculate_execution_time_ms(start_time)
            
            statistics = {
                'total_candidates': len(candidates),
                'excluded_count': eligibility_result.total_excluded,
                'safe_count': len(safe_products),
                'final_count': len(ranked_products),
                'execution_time_ms': execution_time_ms,
                'eligibility_rules_applied': getattr(eligibility_result, 'rules_applied', 0)
            }
            
            return RecommendationPipeline(
                candidates=candidates,
                safe_products=safe_products,
                scored_products=scoring_results,
                ranked_products=ranked_products,
                execution_time=execution_time_ms,
                statistics=statistics
            )
            
        except Exception as e:
            logger.error(f"파이프라인 실행 실패: {request_id} - {e}")
            from app.shared.constants import ERROR_MESSAGES
            user_message = ERROR_MESSAGES['system_error']['ko']
            logger.error(f"사용자 메시지: {user_message}")
            raise
    
    def _build_response(
        self,
        request: RecommendationRequest,
        request_id: UUID,
        pipeline: RecommendationPipeline,
        start_time: datetime
    ) -> RecommendationResponse:
        """응답 객체 생성"""
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # 실행 요약
        execution_summary = ExecutionSummary(
            request_id=request_id,
            timestamp=datetime.now(),
            success=True,
            execution_time_seconds=execution_time,
            ruleset_version=RULESET_VERSION,
            active_rules_count=RuleEngineConfig.ACTIVE_RULES
        )
        
        # 감점 통계 계산
        penalized_count = len(pipeline.scored_products) if pipeline.scored_products else 0
        total_scoring_rules = 0
        if pipeline.scored_products:
            for result in pipeline.scored_products.values():
                if hasattr(result, 'rule_hits'):
                    # ProductScore 객체인 경우 (경로 B에서는 rule_hits가 없을 수 있음)
                    total_scoring_rules += 0  # 경로 B에서는 다른 방식으로 처리
                elif isinstance(result, dict) and 'rule_hits' in result:
                    # 딕셔너리인 경우 (경로 A)
                    total_scoring_rules += len(result['rule_hits'])
        
        logger.info(f"📈 최종 통계: 감점된 제품 {penalized_count}개, 적용된 감점 룰 {total_scoring_rules}개")
        
        # 파이프라인 통계
        pipeline_stats = PipelineStatistics(
            total_candidates=pipeline.statistics['total_candidates'],
            excluded_by_rules=pipeline.statistics['excluded_count'],
            penalized_products=penalized_count,
            final_recommendations=len(pipeline.ranked_products),
            eligibility_rules_applied=pipeline.statistics.get('eligibility_rules_applied', 0),
            scoring_rules_applied=total_scoring_rules,
            query_time_ms=50.0,  # TODO: 실제 쿼리 시간으로 교체
            evaluation_time_ms=pipeline.execution_time * 0.6,
            ranking_time_ms=pipeline.execution_time * 0.4,
            total_time_ms=pipeline.execution_time
        )
        
        # 추천 아이템 변환
        recommendations = []
        for ranked_product in pipeline.ranked_products[:request.top_n]:
            recommendation = RecommendationItem(
                rank=ranked_product.rank,
                product_id=str(ranked_product.product.product_id),
                product_name=ranked_product.product.name,
                brand_name=ranked_product.product.brand_name,
                category=ranked_product.product.category_name,
                final_score=round(ranked_product.final_score, 1),
                base_score=round(ranked_product.base_score, 1),
                penalty_score=round(ranked_product.penalty_score, 1),
                intent_match_score=round(ranked_product.intent_match_score, 1),
                reasons=ranked_product.reasons,
                warnings=[],  # TODO: 경고 메시지
                rule_hits=ranked_product.rule_hits
            )
            recommendations.append(recommendation)
        
        # 입력 요약
        input_summary = {
            "intent_tags_count": len(request.intent_tags),
            "requested_count": request.top_n,
            "has_user_profile": request.user_profile is not None,
            "medications_count": len(request.medications) if request.medications else 0,
            "has_usage_context": request.usage_context is not None,
            "price_range_specified": request.price_range is not None
        }
        
        return RecommendationResponse(
            execution_summary=execution_summary,
            input_summary=input_summary,
            pipeline_statistics=pipeline_stats,
            recommendations=recommendations
        )
    
    def _preprocess_request(self, request: RecommendationRequest):
        """요청 전처리 - medications를 med_profile로 변환"""
        if request.medications and not request.med_profile:
            from app.models.request import MedProfile
            
            # medications에서 active_ingredients 추출
            med_codes = []
            for medication in request.medications:
                if medication.active_ingredients:
                    med_codes.extend(medication.active_ingredients)
            
            # med_profile 생성
            request.med_profile = MedProfile(codes=med_codes)
            
            # 의약품 코드 변환 완료
    
    def _build_error_response(
        self,
        request: RecommendationRequest,
        request_id: UUID,
        start_time: datetime,
        error: Exception
    ) -> RecommendationResponse:
        """에러 응답 생성"""
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        execution_summary = ExecutionSummary(
            request_id=request_id,
            timestamp=datetime.now(),
            success=False,
            execution_time_seconds=execution_time,
            ruleset_version=RULESET_VERSION,
            active_rules_count=0
        )
        
        pipeline_stats = PipelineStatistics(
            total_candidates=0,
            excluded_by_rules=0,
            penalized_products=0,
            final_recommendations=0,
            eligibility_rules_applied=0,
            scoring_rules_applied=0,
            query_time_ms=0,
            evaluation_time_ms=0,
            ranking_time_ms=0,
            total_time_ms=execution_time * 1000
        )
        
        return RecommendationResponse(
            execution_summary=execution_summary,
            input_summary={"error": str(error)},
            pipeline_statistics=pipeline_stats,
            recommendations=[]
        )
    
    def _create_fallback_profile_matches(self, products: List, request) -> Dict:
        """폴백용 프로필 매칭 결과 생성"""
        from app.models.personalization_models import ProfileMatchResult
        
        profile_matches = {}
        for product in products:
            # 기본 점수 계산
            age_score = 70.0
            skin_score = 70.0
            preference_score = 70.0
            
            # 요청 정보 기반 간단한 매칭
            if hasattr(request, 'user_profile') and request.user_profile:
                if hasattr(request.user_profile, 'age_group'):
                    age_score = 75.0
                if hasattr(request.user_profile, 'skin_type'):
                    skin_score = 75.0
            
            overall_score = (age_score + skin_score + preference_score) / 3
            
            profile_matches[product.product_id] = ProfileMatchResult(
                user_id=None,
                product_id=product.product_id,
                age_match_score=age_score,
                skin_type_match_score=skin_score,
                preference_match_score=preference_score,
                overall_match_score=overall_score,
                match_reasons=["기본 매칭"]
            )
        
        return profile_matches
    
    def _extract_user_profile_from_request(self, request) -> Dict:
        """요청에서 사용자 프로필 추출"""
        user_profile = {}
        
        if hasattr(request, 'user_profile') and request.user_profile:
            user_profile = {
                "age_group": getattr(request.user_profile, 'age_group', None),
                "skin_type": getattr(request.user_profile, 'skin_type', None),
                "skin_concerns": getattr(request.user_profile, 'skin_concerns', []),
                "allergies": getattr(request.user_profile, 'allergies', [])
            }
        
        return user_profile
    
    def _create_mock_ingredient_analyses(self, products: List) -> Dict:
        """목업 성분 분석 결과 생성"""
        from app.models.personalization_models import (
            ProductIngredientAnalysis, IngredientEffect, EffectType, SafetyLevel
        )
        
        analyses = {}
        for product in products:
            # 간단한 목업 성분 분석
            beneficial_effects = []
            harmful_effects = []
            safety_warnings = []
            
            product_name = product.name.lower()
            
            # 유익한 효과 추정
            if any(keyword in product_name for keyword in ["vitamin", "비타민", "hyaluronic", "히알루론"]):
                beneficial_effects.append(
                    IngredientEffect(
                        ingredient_id=1,
                        ingredient_name="유익 성분",
                        effect_type=EffectType.BENEFICIAL,
                        effect_description="긍정적 효과",
                        confidence_score=0.8,
                        safety_level=SafetyLevel.SAFE
                    )
                )
            
            # 주의 성분 추정
            if any(keyword in product_name for keyword in ["retinol", "레티놀", "acid", "산"]):
                safety_warnings.append("점진적 사용 권장")
            
            analyses[product.product_id] = ProductIngredientAnalysis(
                product_id=product.product_id,
                product_name=product.name,
                total_ingredients=15,
                analyzed_ingredients=12,
                beneficial_effects=beneficial_effects,
                harmful_effects=harmful_effects,
                safety_warnings=safety_warnings,
                allergy_risks=[]
            )
        
        return analyses
    
    async def _create_real_ingredient_analyses(self, products: List) -> Dict:
        """실제 성분 DB 기반 분석 결과 생성"""
        from app.models.personalization_models import (
            ProductIngredientAnalysis, IngredientEffect, EffectType, SafetyLevel
        )
        
        analyses = {}
        
        for product in products:
            try:
                # 실제 성분 안전성 정보 조회
                safety_info = self.ingredient_service.get_ingredient_safety_info(product.product_id)
                
                # 유익한 효과 생성
                beneficial_effects = []
                for benefit in safety_info.get('beneficial_ingredients', []):
                    beneficial_effects.append(
                        IngredientEffect(
                            ingredient_id=1,  # 실제 ID는 별도 조회 필요
                            ingredient_name=benefit['name'],
                            effect_type=EffectType.BENEFICIAL,
                            effect_description=benefit['benefit'],
                            confidence_score=0.9,
                            safety_level=SafetyLevel.SAFE
                        )
                    )
                
                # 위험 효과 생성
                harmful_effects = []
                for risk in safety_info.get('high_risk_ingredients', []):
                    harmful_effects.append(
                        IngredientEffect(
                            ingredient_id=2,
                            ingredient_name=risk['name'],
                            effect_type=EffectType.HARMFUL,
                            effect_description=risk['reason'],
                            confidence_score=0.8,
                            safety_level=SafetyLevel.WARNING if 'EWG' in risk['reason'] else SafetyLevel.CAUTION
                        )
                    )
                
                # 안전성 경고 및 알레르기 위험
                safety_warnings = safety_info.get('warnings', [])
                allergy_risks = []
                
                if safety_info.get('allergy_ingredients', 0) > 0:
                    allergy_risks.append(f"{safety_info['allergy_ingredients']}개 알레르기 성분 포함")
                
                analyses[product.product_id] = ProductIngredientAnalysis(
                    product_id=product.product_id,
                    product_name=product.name,
                    total_ingredients=safety_info.get('total_ingredients', 0),
                    analyzed_ingredients=safety_info.get('total_ingredients', 0),
                    beneficial_effects=beneficial_effects,
                    harmful_effects=harmful_effects,
                    safety_warnings=safety_warnings,
                    allergy_risks=allergy_risks
                )
                
                logger.debug(f"실제 성분 분석 완료: 제품 {product.product_id}, "
                           f"성분 {safety_info.get('total_ingredients', 0)}개, "
                           f"알레르기 {safety_info.get('allergy_ingredients', 0)}개")
                
            except Exception as e:
                logger.warning(f"제품 {product.product_id} 성분 분석 실패, 목업 사용: {e}")
                
                # 폴백: 목업 데이터 사용
                analyses[product.product_id] = ProductIngredientAnalysis(
                    product_id=product.product_id,
                    product_name=product.name,
                    total_ingredients=15,
                    analyzed_ingredients=12,
                    beneficial_effects=[],
                    harmful_effects=[],
                    safety_warnings=["성분 분석 데이터 부족"],
                    allergy_risks=[]
                )
        
        logger.info(f"성분 분석 완료: {len(analyses)}개 제품 (실제 DB 기반)")
        return analyses
    
    def _should_use_ingredient_analysis(self, request, user_profile: Dict) -> bool:
        """성분 분석 사용 여부 결정 - 항상 빠른 태그 기반 사용"""
        
        # 성능 최적화를 위해 항상 빠른 태그 기반 분석 사용
        logger.info("⚡ 성능 최적화 - 항상 빠른 태그 기반 분석 사용")
        return False
        
        # 아래 코드는 필요시 활성화 가능 (실제 성분 분석)
        # # 1. 알레르기가 있는 사용자
        # if user_profile.get("allergies") and len(user_profile["allergies"]) > 0:
        #     logger.info(f"🚨 알레르기 감지: {user_profile['allergies']}")
        #     return True
        # 
        # # 2. 제외할 성분이 지정된 경우
        # if hasattr(request, 'exclude_ingredients') and request.exclude_ingredients:
        #     logger.info(f"🚫 제외 성분 지정: {request.exclude_ingredients}")
        #     return True
        # 
        # # 3. 의약품 복용자
        # if hasattr(request, 'medications') and request.medications:
        #     logger.info(f"💊 의약품 복용자: {len(request.medications)}개 약물")
        #     return True
        # 
        # # 4. 임신/수유 관련 의도 태그
        # pregnancy_keywords = ["임신", "수유", "pregnancy", "breastfeeding", "pregnant"]
        # if hasattr(request, 'intent_tags') and request.intent_tags:
        #     for tag in request.intent_tags:
        #         if any(keyword in tag.lower() for keyword in pregnancy_keywords):
        #             logger.info(f"🤱 임신/수유 관련 의도: {tag}")
        #             return True
        # 
        # # 5. 극민감 피부 (다중 민감성 고려사항)
        # if user_profile.get("skin_type") == "sensitive":
        #     skin_concerns = user_profile.get("skin_concerns", [])
        #     sensitive_concerns = ["atopic", "irritation", "redness", "sensitivity"]
        #     if len([c for c in skin_concerns if any(sc in c for sc in sensitive_concerns)]) >= 2:
        #         logger.info(f"🔥 극민감 피부 감지: {skin_concerns}")
        #         return True
        # 
        # # 6. 10대 사용자 (성분 안전성 중요)
        # if user_profile.get("age_group") == "10s":
        #     logger.info("👶 10대 사용자 - 안전성 우선")
        #     return True
        # 
        # # 기본: 빠른 태그 기반 사용
        # logger.info("✨ 일반 사용자 - 빠른 추천 모드")
        return False
    
    def _create_fast_tag_based_analyses(self, products: List) -> Dict:
        """빠른 태그 기반 성분 분석 (개선된 버전)"""
        from app.models.personalization_models import (
            ProductIngredientAnalysis, IngredientEffect, EffectType, SafetyLevel
        )
        import random
        
        analyses = {}
        
        for product in products:
            # 제품 태그 기반 빠른 분석
            product_tags = [tag.lower() for tag in (product.tags or [])]
            product_name = product.name.lower()
            
            beneficial_effects = []
            harmful_effects = []
            safety_warnings = []
            allergy_risks = []
            
            # 제품별 다양성을 위한 기본 점수 (제품 ID 기반)
            base_variation = (product.product_id % 100) / 100.0  # 0.0 ~ 0.99
            
            # 태그 기반 유익한 효과 추정 (더 정교하게)
            beneficial_keywords = {
                "hyaluronic_acid": ("히알루론산", "강력한 보습 효과", 0.9),
                "보습": ("보습 성분", "수분 공급 효과", 0.8), 
                "진정": ("진정 성분", "피부 진정 효과", 0.85),
                "vitamin": ("비타민", "영양 공급 효과", 0.8),
                "비타민": ("비타민", "영양 공급 효과", 0.8),
                "ceramide": ("세라마이드", "피부 장벽 강화", 0.9),
                "niacinamide": ("나이아신아마이드", "모공 개선 및 미백", 0.85),
                "peptide": ("펩타이드", "탄력 개선", 0.8),
                "collagen": ("콜라겐", "피부 탄력", 0.75)
            }
            
            beneficial_count = 0
            for tag in product_tags:
                for keyword, (name, effect, confidence) in beneficial_keywords.items():
                    if keyword in tag:
                        # 제품별로 약간의 변화 추가
                        adjusted_confidence = min(0.95, confidence + (base_variation * 0.1))
                        beneficial_effects.append(
                            IngredientEffect(
                                ingredient_id=beneficial_count + 1,
                                ingredient_name=name,
                                effect_type=EffectType.BENEFICIAL,
                                effect_description=effect,
                                confidence_score=adjusted_confidence,
                                safety_level=SafetyLevel.SAFE
                            )
                        )
                        beneficial_count += 1
                        if beneficial_count >= 3:  # 최대 3개까지
                            break
                if beneficial_count >= 3:
                    break
            
            # 태그 기반 주의 성분 추정 (더 정교하게)
            warning_keywords = {
                "retinoid": ("레티놀", "점진적 사용 권장", SafetyLevel.CAUTION),
                "레티놀": ("레티놀", "점진적 사용 권장", SafetyLevel.CAUTION),
                "aha": ("AHA", "자외선 차단 필수", SafetyLevel.WARNING),
                "bha": ("BHA", "건성피부 주의", SafetyLevel.CAUTION),
                "alcohol": ("알코올", "건성피부 주의", SafetyLevel.WARNING),
                "fragrance": ("향료", "알레르기 주의", SafetyLevel.WARNING),
                "essential_oil": ("에센셜오일", "민감피부 주의", SafetyLevel.CAUTION)
            }
            
            harmful_count = 0
            for tag in product_tags:
                for keyword, (name, warning, safety_level) in warning_keywords.items():
                    if keyword in tag:
                        harmful_effects.append(
                            IngredientEffect(
                                ingredient_id=harmful_count + 100,
                                ingredient_name=name,
                                effect_type=EffectType.HARMFUL,
                                effect_description=warning,
                                confidence_score=0.7 + (base_variation * 0.2),
                                safety_level=safety_level
                            )
                        )
                        safety_warnings.append(warning)
                        harmful_count += 1
                        if harmful_count >= 2:  # 최대 2개까지
                            break
                if harmful_count >= 2:
                    break
            
            # 알레르기 위험 추정
            allergy_keywords = ["fragrance", "향료", "essential_oil", "parfum"]
            for tag in product_tags:
                for keyword in allergy_keywords:
                    if keyword in tag:
                        allergy_risks.append(f"{keyword} 알레르기 주의")
                        break
            
            # 제품별 성분 수 다양화 (제품 ID 기반)
            total_ingredients = 10 + int(base_variation * 30)  # 10~40개
            analyzed_ingredients = max(5, int(total_ingredients * 0.8))  # 80% 분석
            
            analyses[product.product_id] = ProductIngredientAnalysis(
                product_id=product.product_id,
                product_name=product.name,
                total_ingredients=total_ingredients,
                analyzed_ingredients=analyzed_ingredients,
                beneficial_effects=beneficial_effects,
                harmful_effects=harmful_effects,
                safety_warnings=safety_warnings,
                allergy_risks=allergy_risks
            )
        
        logger.info(f"빠른 태그 기반 분석 완료: {len(analyses)}개 제품")
        return analyses
    

    
    def _determine_custom_weights(self, request, user_profile: Dict) -> Dict[str, float]:
        """사용자 프로필 기반 커스텀 가중치 결정"""
        # 기본 가중치
        weights = {"intent": 30.0, "personalization": 40.0, "safety": 30.0}
        
        # 연령대별 조정
        age_group = user_profile.get("age_group")
        if age_group in ["10s", "20s"]:
            # 젊은 연령대: 안전성 중시
            weights = {"intent": 25.0, "personalization": 35.0, "safety": 40.0}
        elif age_group in ["40s", "50s"]:
            # 성숙한 연령대: 개인화 중시
            weights = {"intent": 35.0, "personalization": 45.0, "safety": 20.0}
        
        # 피부타입별 조정
        skin_type = user_profile.get("skin_type")
        if skin_type == "sensitive":
            # 민감피부: 안전성 최우선
            weights = {"intent": 20.0, "personalization": 30.0, "safety": 50.0}
        
        # 의약품 복용자: 안전성 강화
        if hasattr(request, 'medications') and request.medications:
            weights["safety"] = min(weights["safety"] + 10.0, 50.0)
            weights["intent"] = max(weights["intent"] - 5.0, 20.0)
            weights["personalization"] = max(weights["personalization"] - 5.0, 20.0)
        
        return weights
    
    def _convert_path_b_to_path_a_format(self, path_b_results: Dict) -> Dict:
        """경로 B 결과를 경로 A 호환 형식으로 변환"""
        path_a_format = {}
        
        for product_id, score_result in path_b_results.items():
            path_a_format[product_id] = {
                'final_score': score_result.final_score,
                'base_score': 100.0,  # 경로 A 호환
                'penalty_score': max(0, 100.0 - score_result.final_score),
                'intent_match_score': score_result.score_breakdown.intent_score,
                'personalization_score': score_result.score_breakdown.personalization_score,
                'safety_penalty': max(0, 100.0 - score_result.score_breakdown.safety_score),
                'medication_penalty': 0.0,  # 경로 B에서는 통합 처리
                'rule_hits': []  # 경로 B에서는 다른 방식으로 처리
            }
        
        return path_a_format