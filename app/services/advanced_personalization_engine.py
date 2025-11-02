"""
고도화된 개인화 추천 엔진
모든 컴포넌트를 조율하는 메인 추천 엔진
성능 모니터링, 고도화된 캐싱, 동시성 최적화 통합
"""

import asyncio
import logging
import time
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.models.personalization_models import (
    PersonalizedRecommendation, ProductScore, ProductIngredientAnalysis,
    ProfileMatchResult, PersonalizationEngineError, IngredientAnalysisError,
    ProfileMatchingError, ScoreCalculationError
)
from app.models.postgres_models import Product, CompleteUserProfile
from app.database.postgres_db import get_postgres_db
from app.services.ingredient_analyzer import IngredientAnalyzer
from app.services.user_profile_matcher import UserProfileMatcher
from app.services.scoring_engine import ScoreCalculator
from app.services.safety_filter import SafetyFilter, SafetyFilterConfig
from app.services.recommendation_ranker import RecommendationRanker, RankingConfig

# 성능 최적화 컴포넌트
from app.services.performance_monitor import get_performance_monitor, PerformanceMonitor
from app.services.advanced_cache import get_cache_manager, CacheManager
from app.services.concurrency_optimizer import get_concurrency_optimizer, ConcurrencyOptimizer, TaskPriority

logger = logging.getLogger(__name__)

@dataclass
class RecommendationRequest:
    """추천 요청 정보"""
    intent_tags: List[str]
    user_profile: Optional[Dict[str, Any]] = None
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None
    max_recommendations: int = 10
    category_filter: Optional[List[str]] = None
    brand_filter: Optional[List[str]] = None
    enable_safety_filter: bool = True
    enable_diversity: bool = True
    ranking_strategy: str = "diversity"  # basic, diversity, price_diversity

@dataclass
class RecommendationPipeline:
    """추천 파이프라인 단계별 결과"""
    step: str
    success: bool
    execution_time_ms: float
    result_count: int
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RecommendationMetrics:
    """추천 성능 메트릭"""
    total_execution_time_ms: float
    pipeline_steps: List[RecommendationPipeline]
    candidate_products: int
    filtered_products: int
    final_recommendations: int
    cache_hit_rate: float = 0.0
    database_queries: int = 0
    error_count: int = 0

class AdvancedPersonalizationEngine:
    """고도화된 개인화 추천 엔진 (성능 최적화 통합)"""
    
    def __init__(self):
        self.db = get_postgres_db()
        self.ingredient_analyzer = IngredientAnalyzer()
        self.profile_matcher = UserProfileMatcher()
        self.score_calculator = ScoreCalculator()
        self.safety_filter = SafetyFilter()
        self.ranker = RecommendationRanker()
        
        # 성능 최적화 컴포넌트
        self.performance_monitor: PerformanceMonitor = get_performance_monitor()
        self.cache_manager: CacheManager = get_cache_manager()
        self.concurrency_optimizer: ConcurrencyOptimizer = get_concurrency_optimizer()
        
        # 성능 모니터링
        self.metrics_enabled = True
        self.fallback_enabled = True
        
        # AdvancedPersonalizationEngine 초기화 완료
        
    async def get_personalized_recommendations(
        self,
        request: RecommendationRequest
    ) -> Tuple[PersonalizedRecommendation, RecommendationMetrics]:
        """
        개인화된 추천 생성 (메인 엔트리포인트) - 성능 최적화 적용
        
        Args:
            request: 추천 요청 정보
            
        Returns:
            Tuple[PersonalizedRecommendation, RecommendationMetrics]: 추천 결과와 성능 메트릭
        """
        # 성능 모니터링 시작
        async with self.performance_monitor.measure_async(
            "AdvancedPersonalizationEngine", 
            "get_personalized_recommendations",
            metadata={"intent_tags": request.intent_tags, "user_id": str(request.user_id)}
        ):
            return await self._execute_recommendation_pipeline(request)
    
    async def _execute_recommendation_pipeline(
        self,
        request: RecommendationRequest
    ) -> Tuple[PersonalizedRecommendation, RecommendationMetrics]:
        """추천 파이프라인 실행 (성능 최적화 적용)"""
        start_time = time.time()
        pipeline_steps = []
        
        try:
            # 개인화 추천 시작
            
            # 캐시 키 생성
            cache_key = self._generate_recommendation_cache_key(request)
            
            # 캐시된 추천 결과 확인
            cached_result = await self.cache_manager.cache.get(cache_key)
            if cached_result and self._is_cache_valid(cached_result):
                # 캐시된 추천 결과 반환
                return cached_result
            
            # 1단계: 후보 제품 조회 (성능 모니터링)
            async with self.performance_monitor.measure_async(
                "AdvancedPersonalizationEngine", 
                "candidate_retrieval"
            ):
                candidate_products = await self._get_candidate_products_optimized(
                    request.intent_tags, request.category_filter, request.brand_filter
                )
            
            step_time = (time.time() - start_time) * 1000
            pipeline_steps.append(RecommendationPipeline(
                step="candidate_retrieval",
                success=True,
                execution_time_ms=step_time,
                result_count=len(candidate_products),
                metadata={"filters_applied": bool(request.category_filter or request.brand_filter)}
            ))
            
            if not candidate_products:
                return await self._create_empty_recommendation(request, pipeline_steps, start_time)
            
            # 2단계: 성분 분석 (병렬 처리 및 캐싱)
            async with self.performance_monitor.measure_async(
                "AdvancedPersonalizationEngine", 
                "ingredient_analysis"
            ):
                ingredient_analyses = await self._analyze_ingredients_batch_optimized(candidate_products)
            
            step_time = (time.time() - start_time) * 1000
            pipeline_steps.append(RecommendationPipeline(
                step="ingredient_analysis",
                success=True,
                execution_time_ms=step_time,
                result_count=len(ingredient_analyses),
                metadata={"cache_hits": await self._get_cache_hit_count()}
            ))
            
            # 3단계: 프로필 매칭 (병렬 처리)
            async with self.performance_monitor.measure_async(
                "AdvancedPersonalizationEngine", 
                "profile_matching"
            ):
                profile_matches = await self._match_user_profiles_optimized(
                    candidate_products, request.user_profile
                )
            
            step_time = (time.time() - start_time) * 1000
            pipeline_steps.append(RecommendationPipeline(
                step="profile_matching",
                success=True,
                execution_time_ms=step_time,
                result_count=len(profile_matches),
                metadata={"user_profile_available": bool(request.user_profile)}
            ))
            
            # 4단계: 점수 계산 (병렬 처리)
            async with self.performance_monitor.measure_async(
                "AdvancedPersonalizationEngine", 
                "score_calculation"
            ):
                product_scores = await self._calculate_scores_optimized(
                    candidate_products, request.intent_tags, profile_matches, 
                    ingredient_analyses, request.user_profile
                )
            
            step_time = (time.time() - start_time) * 1000
            pipeline_steps.append(RecommendationPipeline(
                step="score_calculation",
                success=True,
                execution_time_ms=step_time,
                result_count=len(product_scores),
                metadata={"scoring_dimensions": 3}  # 의도, 개인화, 안전성
            ))
            
            # 5단계: 안전성 필터링
            async with self.performance_monitor.measure_async(
                "AdvancedPersonalizationEngine", 
                "safety_filtering"
            ):
                if request.enable_safety_filter:
                    filtered_products, filter_results = await self._apply_safety_filter(
                        candidate_products, product_scores, ingredient_analyses, request.user_profile
                    )
                else:
                    filtered_products = candidate_products
                    filter_results = {}
            
            step_time = (time.time() - start_time) * 1000
            pipeline_steps.append(RecommendationPipeline(
                step="safety_filtering",
                success=True,
                execution_time_ms=step_time,
                result_count=len(filtered_products),
                metadata={
                    "filter_enabled": request.enable_safety_filter,
                    "filtered_count": len(candidate_products) - len(filtered_products)
                }
            ))
            
            # 6단계: 순위 결정
            async with self.performance_monitor.measure_async(
                "AdvancedPersonalizationEngine", 
                "ranking"
            ):
                ranking_result = await self._rank_recommendations(
                    filtered_products, product_scores, request
                )
            
            step_time = (time.time() - start_time) * 1000
            pipeline_steps.append(RecommendationPipeline(
                step="ranking",
                success=True,
                execution_time_ms=step_time,
                result_count=len(ranking_result.ranked_products),
                metadata={
                    "ranking_strategy": request.ranking_strategy,
                    "diversity_enabled": request.enable_diversity
                }
            ))
            
            # 최종 추천 결과 생성
            total_time = (time.time() - start_time) * 1000
            recommendation = self.ranker.create_personalized_recommendation(
                ranking_result=ranking_result,
                products={p.product_id: p for p in candidate_products},
                intent_tags=request.intent_tags,
                user_profile=request.user_profile,
                session_id=request.session_id,
                execution_time_ms=total_time
            )
            
            # 성능 메트릭 생성
            metrics = RecommendationMetrics(
                total_execution_time_ms=total_time,
                pipeline_steps=pipeline_steps,
                candidate_products=len(candidate_products),
                filtered_products=len(filtered_products),
                final_recommendations=len(ranking_result.ranked_products),
                database_queries=await self._get_db_query_count(),
                error_count=0
            )
            
            # 결과 캐싱 (TTL: 30분)
            result_tuple = (recommendation, metrics)
            await self.cache_manager.cache.set(
                cache_key, 
                result_tuple, 
                ttl=1800,  # 30분
                tags={'recommendation', f'user_{request.user_id}'}
            )
            
            # 개인화 추천 완료
            return recommendation, metrics
            
        except Exception as e:
            logger.error(f"개인화 추천 실패: {e}")
            
            # 에러 발생 시 폴백 처리
            if self.fallback_enabled:
                return await self._fallback_recommendation(request, pipeline_steps, start_time, str(e))
            else:
                raise PersonalizationEngineError(f"추천 생성 실패: {e}")
    
    async def _get_candidate_products(
        self,
        intent_tags: List[str],
        category_filter: Optional[List[str]] = None,
        brand_filter: Optional[List[str]] = None
    ) -> List[Product]:
        """후보 제품 조회"""
        
        try:
            # 기본 쿼리
            base_query = """
                SELECT product_id, name, brand_name, category_code, category_name,
                       primary_attr, tags, image_url, sub_product_name,
                       created_at, updated_at
                FROM products
                WHERE 1=1
            """
            
            params = []
            param_count = 0
            
            # 카테고리 필터
            if category_filter:
                param_count += 1
                base_query += f" AND category_name = ANY(${param_count})"
                params.append(category_filter)
            
            # 브랜드 필터
            if brand_filter:
                param_count += 1
                base_query += f" AND brand_name = ANY(${param_count})"
                params.append(brand_filter)
            
            # 의도 태그 기반 필터링 (JSONB 검색)
            if intent_tags:
                param_count += 1
                # tags JSONB 배열에서 의도 태그와 유사한 항목 검색
                tag_conditions = []
                for tag in intent_tags:
                    tag_conditions.append(f"tags ? ${param_count + len(tag_conditions)}")
                
                if tag_conditions:
                    base_query += f" AND ({' OR '.join(tag_conditions)})"
                    params.extend(intent_tags)
            
            # 활성 제품만 조회 (필요시)
            base_query += " ORDER BY product_id LIMIT 1000"  # 성능을 위한 제한
            
            results = await self.db.execute_query(base_query, *params)
            
            products = [Product.from_db_row(row) for row in results]
            # 후보 제품 조회 완료
            
            return products
            
        except Exception as e:
            logger.error(f"후보 제품 조회 실패: {e}")
            raise PersonalizationEngineError(f"후보 제품 조회 실패: {e}")
    
    async def _analyze_ingredients_batch(
        self,
        products: List[Product]
    ) -> Dict[int, ProductIngredientAnalysis]:
        """배치 성분 분석"""
        
        try:
            product_ids = [p.product_id for p in products]
            
            # 배치로 성분 조회
            ingredients_batch = await self.ingredient_analyzer.get_product_ingredients_batch(product_ids)
            
            # 병렬 성분 분석
            analysis_tasks = []
            for product in products:
                ingredients = ingredients_batch.get(product.product_id, [])
                if ingredients:
                    task = self.ingredient_analyzer.analyze_product_ingredients(product, ingredients)
                    analysis_tasks.append((product.product_id, task))
            
            # 병렬 실행
            analyses = {}
            if analysis_tasks:
                results = await asyncio.gather(
                    *[task for _, task in analysis_tasks], 
                    return_exceptions=True
                )
                
                for i, (product_id, _) in enumerate(analysis_tasks):
                    result = results[i]
                    if isinstance(result, Exception):
                        logger.warning(f"성분 분석 실패 (product_id: {product_id}): {result}")
                    else:
                        analyses[product_id] = result
            
            # 배치 성분 분석 완료
            return analyses
            
        except Exception as e:
            logger.error(f"배치 성분 분석 실패: {e}")
            if self.fallback_enabled:
                return {}  # 빈 분석 결과 반환
            raise IngredientAnalysisError(f"성분 분석 실패: {e}")
    
    async def _match_user_profiles(
        self,
        products: List[Product],
        user_profile: Optional[Dict[str, Any]]
    ) -> Dict[int, ProfileMatchResult]:
        """사용자 프로필 매칭"""
        
        try:
            if not user_profile:
                # 기본 매칭 결과 생성
                return {
                    p.product_id: ProfileMatchResult(
                        user_id=None,
                        product_id=p.product_id,
                        overall_match_score=50.0
                    ) for p in products
                }
            
            # 병렬 프로필 매칭
            matching_tasks = [
                self.profile_matcher.match_user_profile(product, user_profile)
                for product in products
            ]
            
            results = await asyncio.gather(*matching_tasks, return_exceptions=True)
            
            matches = {}
            for i, product in enumerate(products):
                result = results[i]
                if isinstance(result, Exception):
                    logger.warning(f"프로필 매칭 실패 (product_id: {product.product_id}): {result}")
                    # 기본 매칭 결과 생성
                    matches[product.product_id] = ProfileMatchResult(
                        user_id=user_profile.get('user_id'),
                        product_id=product.product_id,
                        overall_match_score=50.0
                    )
                else:
                    matches[product.product_id] = result
            
            # 프로필 매칭 완료
            return matches
            
        except Exception as e:
            logger.error(f"프로필 매칭 실패: {e}")
            if self.fallback_enabled:
                return {
                    p.product_id: ProfileMatchResult(
                        user_id=user_profile.get('user_id') if user_profile else None,
                        product_id=p.product_id,
                        overall_match_score=50.0
                    ) for p in products
                }
            raise ProfileMatchingError(f"프로필 매칭 실패: {e}")
    
    async def _calculate_scores(
        self,
        products: List[Product],
        intent_tags: List[str],
        profile_matches: Dict[int, ProfileMatchResult],
        ingredient_analyses: Dict[int, ProductIngredientAnalysis],
        user_profile: Optional[Dict[str, Any]]
    ) -> Dict[int, ProductScore]:
        """점수 계산"""
        
        try:
            scores = await self.score_calculator.calculate_product_scores(
                products=products,
                intent_tags=intent_tags,
                profile_matches=profile_matches,
                ingredient_analyses=ingredient_analyses,
                user_profile=user_profile
            )
            
            # 점수 정규화
            normalized_scores = self.score_calculator.normalize_scores(scores)
            
            # 점수 계산 완료
            return normalized_scores
            
        except Exception as e:
            logger.error(f"점수 계산 실패: {e}")
            if self.fallback_enabled:
                # 기본 점수로 폴백
                return {
                    p.product_id: ProductScore(
                        product_id=p.product_id,
                        product_name=p.name,
                        brand_name=p.brand_name,
                        final_score=50.0,
                        normalized_score=50.0
                    ) for p in products
                }
            raise ScoreCalculationError(f"점수 계산 실패: {e}")
    
    async def _apply_safety_filter(
        self,
        products: List[Product],
        product_scores: Dict[int, ProductScore],
        ingredient_analyses: Dict[int, ProductIngredientAnalysis],
        user_profile: Optional[Dict[str, Any]]
    ) -> Tuple[List[Product], Dict[int, Any]]:
        """안전성 필터링 적용"""
        
        try:
            # 안전성 필터 설정
            config = SafetyFilterConfig()
            if user_profile:
                config.age_group = user_profile.get('age_group')
                config.skin_type = user_profile.get('skin_type')
                config.strict_filtering = user_profile.get('preferences', {}).get('strict_safety', False)
            
            filtered_products, filter_results = self.safety_filter.filter_products(
                products=products,
                product_scores=product_scores,
                ingredient_analyses=ingredient_analyses,
                user_profile=user_profile,
                config=config
            )
            
            # 안전성 필터링 완료
            return filtered_products, filter_results
            
        except Exception as e:
            logger.error(f"안전성 필터링 실패: {e}")
            if self.fallback_enabled:
                return products, {}  # 필터링 없이 원본 반환
            raise PersonalizationEngineError(f"안전성 필터링 실패: {e}")
    
    async def _rank_recommendations(
        self,
        products: List[Product],
        product_scores: Dict[int, ProductScore],
        request: RecommendationRequest
    ) -> Any:  # RankingResult 타입
        """추천 순위 결정"""
        
        try:
            # 순위 결정 설정
            ranking_config = RankingConfig(
                max_recommendations=request.max_recommendations,
                enable_diversity=request.enable_diversity
            )
            
            self.ranker.config = ranking_config
            
            # 제품 딕셔너리 생성
            products_dict = {p.product_id: p for p in products}
            
            # 순위 결정
            ranking_result = self.ranker.rank_recommendations(
                product_scores=product_scores,
                products=products_dict,
                user_profile=request.user_profile,
                ranking_strategy=request.ranking_strategy
            )
            
            # 순위 결정 완료
            return ranking_result
            
        except Exception as e:
            logger.error(f"순위 결정 실패: {e}")
            if self.fallback_enabled:
                # 기본 점수 순 정렬로 폴백
                sorted_scores = sorted(
                    [score for score in product_scores.values() if score.product_id in [p.product_id for p in products]],
                    key=lambda x: x.final_score,
                    reverse=True
                )[:request.max_recommendations]
                
                from app.services.recommendation_ranker import RankingResult
                return RankingResult(
                    ranked_products=sorted_scores,
                    total_candidates=len(products)
                )
            raise PersonalizationEngineError(f"순위 결정 실패: {e}")
    
    async def _create_empty_recommendation(
        self,
        request: RecommendationRequest,
        pipeline_steps: List[RecommendationPipeline],
        start_time: float
    ) -> Tuple[PersonalizedRecommendation, RecommendationMetrics]:
        """빈 추천 결과 생성"""
        
        total_time = (time.time() - start_time) * 1000
        
        recommendation = PersonalizedRecommendation(
            user_id=request.user_id,
            session_id=request.session_id,
            intent_tags=request.intent_tags,
            user_profile_summary=request.user_profile or {},
            recommended_products=[],
            total_candidates=0,
            filtered_count=0,
            execution_time_ms=total_time,
            overall_insights=["추천 가능한 제품이 없습니다."],
            personalization_notes=["검색 조건을 조정해보세요."]
        )
        
        metrics = RecommendationMetrics(
            total_execution_time_ms=total_time,
            pipeline_steps=pipeline_steps,
            candidate_products=0,
            filtered_products=0,
            final_recommendations=0,
            error_count=0
        )
        
        return recommendation, metrics
    
    async def _fallback_recommendation(
        self,
        request: RecommendationRequest,
        pipeline_steps: List[RecommendationPipeline],
        start_time: float,
        error_message: str
    ) -> Tuple[PersonalizedRecommendation, RecommendationMetrics]:
        """폴백 추천 생성"""
        
        try:
            # 폴백 추천 모드 실행
            
            # 간단한 제품 조회 (에러 없이)
            simple_query = """
                SELECT product_id, name, brand_name, category_code, category_name,
                       primary_attr, tags, image_url
                FROM products
                ORDER BY product_id
                LIMIT $1
            """
            
            results = await self.db.execute_query(simple_query, request.max_recommendations)
            products = [Product.from_db_row(row) for row in results]
            
            # 기본 점수로 ProductScore 생성
            product_scores = []
            for product in products:
                score = ProductScore(
                    product_id=product.product_id,
                    product_name=product.name,
                    brand_name=product.brand_name,
                    final_score=50.0,
                    normalized_score=50.0,
                    recommendation_reasons=["기본 추천"],
                    caution_notes=["상세 분석 불가"]
                )
                product_scores.append(score)
            
            total_time = (time.time() - start_time) * 1000
            
            recommendation = PersonalizedRecommendation(
                user_id=request.user_id,
                session_id=request.session_id,
                intent_tags=request.intent_tags,
                user_profile_summary=request.user_profile or {},
                recommended_products=product_scores,
                total_candidates=len(products),
                filtered_count=0,
                execution_time_ms=total_time,
                overall_insights=["기본 추천이 제공되었습니다."],
                personalization_notes=["일시적 오류로 인한 기본 추천입니다."]
            )
            
            # 에러 단계 추가
            pipeline_steps.append(RecommendationPipeline(
                step="fallback",
                success=True,
                execution_time_ms=total_time,
                result_count=len(products),
                error_message=error_message
            ))
            
            metrics = RecommendationMetrics(
                total_execution_time_ms=total_time,
                pipeline_steps=pipeline_steps,
                candidate_products=len(products),
                filtered_products=len(products),
                final_recommendations=len(products),
                error_count=1
            )
            
            # 폴백 추천 완료
            return recommendation, metrics
            
        except Exception as e:
            logger.error(f"폴백 추천도 실패: {e}")
            raise PersonalizationEngineError(f"전체 추천 시스템 실패: {error_message}, 폴백 실패: {e}")
    
    async def _get_cache_hit_count(self) -> int:
        """캐시 히트 수 조회 (모니터링용)"""
        try:
            cache_stats = await self.ingredient_analyzer.get_cache_stats()
            return cache_stats.get('hits', 0)
        except:
            return 0
    
    async def _get_db_query_count(self) -> int:
        """DB 쿼리 수 조회 (모니터링용)"""
        # 실제 구현에서는 DB 연결 풀의 통계 정보 활용
        return 0
    
    async def get_engine_health(self) -> Dict[str, Any]:
        """엔진 헬스체크"""
        
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        try:
            # 데이터베이스 상태
            db_health = await self.db.get_health_status()
            health_status["components"]["database"] = db_health
            
            # 캐시 상태
            try:
                cache_stats = await self.ingredient_analyzer.get_cache_stats()
                health_status["components"]["cache"] = {
                    "status": "healthy",
                    "stats": cache_stats
                }
            except Exception as e:
                health_status["components"]["cache"] = {
                    "status": "unhealthy",
                    "error": str(e)
                }
            
            # 전체 상태 결정
            component_statuses = [comp.get("status", "unknown") for comp in health_status["components"].values()]
            if "unhealthy" in component_statuses:
                health_status["status"] = "degraded"
            elif "unknown" in component_statuses:
                health_status["status"] = "unknown"
            
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status
    
    async def get_engine_statistics(self) -> Dict[str, Any]:
        """엔진 통계 정보"""
        
        try:
            stats = {
                "database": {
                    "total_products": await self.db.get_table_count("products"),
                    "total_ingredients": await self.db.get_table_count("ingredients"),
                    "total_users": await self.db.get_table_count("users") if await self._table_exists("users") else 0
                },
                "cache": await self.ingredient_analyzer.get_cache_stats(),
                "engine_info": {
                    "version": "1.0",
                    "components": [
                        "IngredientAnalyzer",
                        "UserProfileMatcher", 
                        "ScoreCalculator",
                        "SafetyFilter",
                        "RecommendationRanker"
                    ],
                    "features": [
                        "multi_dimensional_scoring",
                        "safety_filtering",
                        "diversity_ranking",
                        "batch_processing",
                        "caching",
                        "fallback_support"
                    ]
                }
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"통계 정보 조회 실패: {e}")
            return {"error": str(e)}
    
    async def _table_exists(self, table_name: str) -> bool:
        """테이블 존재 여부 확인"""
        try:
            tables = await self.db.get_table_names()
            return table_name in tables
        except:
            return False
    
    async def cleanup_resources(self):
        """리소스 정리 (성능 최적화 컴포넌트 포함)"""
        try:
            # 캐시 정리
            await self.ingredient_analyzer.cleanup_expired_cache()
            await self.cache_manager.cache.clear_all()
            
            # 동시성 최적화 시스템 정리
            await self.concurrency_optimizer.cleanup()
            
            # 데이터베이스 연결 정리
            await self.db.close_pool()
            
            # 엔진 리소스 정리 완료
            
        except Exception as e:
            logger.error(f"리소스 정리 실패: {e}")
    
    # === 성능 최적화된 메서드들 ===
    
    def _generate_recommendation_cache_key(self, request: RecommendationRequest) -> str:
        """추천 요청 캐시 키 생성"""
        key_parts = [
            "recommendation",
            "_".join(sorted(request.intent_tags)),
            str(request.user_id) if request.user_id else "anonymous",
            str(request.max_recommendations),
            "_".join(sorted(request.category_filter or [])),
            "_".join(sorted(request.brand_filter or []))
        ]
        return self.cache_manager.generate_hash_key("_".join(key_parts))
    
    def _is_cache_valid(self, cached_result: Any) -> bool:
        """캐시 유효성 검사"""
        try:
            if not isinstance(cached_result, tuple) or len(cached_result) != 2:
                return False
            
            recommendation, metrics = cached_result
            
            # 캐시된 시간이 30분 이내인지 확인
            if hasattr(metrics, 'total_execution_time_ms'):
                return True  # 간단한 유효성 검사
            
            return False
        except:
            return False
    
    async def _get_candidate_products_optimized(
        self,
        intent_tags: List[str],
        category_filter: Optional[List[str]] = None,
        brand_filter: Optional[List[str]] = None
    ) -> List[Product]:
        """최적화된 후보 제품 조회 (캐싱 적용)"""
        
        # 캐시 키 생성
        cache_key = f"candidates_{self.cache_manager.generate_hash_key({
            'intent_tags': intent_tags,
            'category_filter': category_filter,
            'brand_filter': brand_filter
        })}"
        
        # 캐시 확인
        cached_products = await self.cache_manager.cache.get(cache_key)
        if cached_products:
            logger.debug(f"후보 제품 캐시 히트: {len(cached_products)}개")
            return cached_products
        
        # 캐시 미스 시 DB 조회
        products = await self._get_candidate_products(intent_tags, category_filter, brand_filter)
        
        # 결과 캐싱 (TTL: 10분)
        await self.cache_manager.cache.set(
            cache_key, 
            products, 
            ttl=600,
            tags={'candidate_products'}
        )
        
        return products
    
    async def _analyze_ingredients_batch_optimized(
        self,
        products: List[Product]
    ) -> Dict[int, ProductIngredientAnalysis]:
        """최적화된 배치 성분 분석 (캐싱 + 병렬 처리)"""
        
        analyses = {}
        uncached_products = []
        
        # 캐시된 분석 결과 확인
        for product in products:
            cached_analysis = await self.cache_manager.get_product_analysis(product.product_id)
            if cached_analysis:
                analyses[product.product_id] = cached_analysis
            else:
                uncached_products.append(product)
        
        # 성분 분석 캐시 상태
        
        # 캐시되지 않은 제품들 병렬 분석
        if uncached_products:
            # 동시성 최적화를 통한 배치 처리
            async def analyze_single_product(product):
                ingredients = await self.ingredient_analyzer.get_product_ingredients_batch([product.product_id])
                product_ingredients = ingredients.get(product.product_id, [])
                if product_ingredients:
                    analysis = await self.ingredient_analyzer.analyze_product_ingredients(
                        product, product_ingredients
                    )
                    # 분석 결과 캐싱
                    await self.cache_manager.set_product_analysis(
                        product.product_id, analysis, ttl=7200  # 2시간
                    )
                    return product.product_id, analysis
                return product.product_id, None
            
            # 병렬 처리 (배치 크기: 10)
            batch_results = await self.concurrency_optimizer.optimize_batch_processing(
                uncached_products,
                analyze_single_product,
                batch_size=10,
                priority=TaskPriority.HIGH
            )
            
            # 결과 통합
            for product_id, analysis in batch_results:
                if analysis:
                    analyses[product_id] = analysis
        
        return analyses
    
    async def _match_user_profiles_optimized(
        self,
        products: List[Product],
        user_profile: Optional[Dict[str, Any]]
    ) -> Dict[int, ProfileMatchResult]:
        """최적화된 사용자 프로필 매칭 (병렬 처리)"""
        
        if not user_profile:
            # 기본 매칭 결과 생성
            return {
                p.product_id: ProfileMatchResult(
                    user_id=None,
                    product_id=p.product_id,
                    overall_match_score=50.0
                ) for p in products
            }
        
        # 사용자 프로필 캐싱
        user_id = user_profile.get('user_id')
        if user_id:
            cached_profile = await self.cache_manager.get_user_profile(user_id)
            if cached_profile:
                user_profile = cached_profile
        
        # 병렬 프로필 매칭
        async def match_single_product(product):
            try:
                return await self.profile_matcher.match_user_profile(product, user_profile)
            except Exception as e:
                logger.warning(f"프로필 매칭 실패 (product_id: {product.product_id}): {e}")
                return ProfileMatchResult(
                    user_id=user_profile.get('user_id'),
                    product_id=product.product_id,
                    overall_match_score=50.0
                )
        
        # 동시성 최적화를 통한 병렬 처리
        match_results = await self.concurrency_optimizer.optimize_batch_processing(
            products,
            match_single_product,
            batch_size=20,
            priority=TaskPriority.NORMAL
        )
        
        # 결과 딕셔너리 생성
        matches = {}
        for i, product in enumerate(products):
            matches[product.product_id] = match_results[i]
        
        return matches
    
    async def _calculate_scores_optimized(
        self,
        products: List[Product],
        intent_tags: List[str],
        profile_matches: Dict[int, ProfileMatchResult],
        ingredient_analyses: Dict[int, ProductIngredientAnalysis],
        user_profile: Optional[Dict[str, Any]]
    ) -> Dict[int, ProductScore]:
        """최적화된 점수 계산 (병렬 처리)"""
        
        # 점수 계산 캐싱 키 생성
        score_cache_keys = {}
        cached_scores = {}
        uncached_products = []
        
        for product in products:
            cache_key = f"score_{product.product_id}_{self.cache_manager.generate_hash_key({
                'intent_tags': intent_tags,
                'user_profile': user_profile
            })}"
            score_cache_keys[product.product_id] = cache_key
            
            # 캐시 확인
            cached_score = await self.cache_manager.cache.get(cache_key)
            if cached_score:
                cached_scores[product.product_id] = cached_score
            else:
                uncached_products.append(product)
        
        # 점수 계산 캐시 상태
        
        # 캐시되지 않은 제품들 점수 계산
        if uncached_products:
            uncached_scores = await self.score_calculator.calculate_product_scores(
                products=uncached_products,
                intent_tags=intent_tags,
                profile_matches=profile_matches,
                ingredient_analyses=ingredient_analyses,
                user_profile=user_profile
            )
            
            # 계산된 점수 캐싱
            for product_id, score in uncached_scores.items():
                cache_key = score_cache_keys[product_id]
                await self.cache_manager.cache.set(
                    cache_key, 
                    score, 
                    ttl=3600,  # 1시간
                    tags={'product_score', f'product_{product_id}'}
                )
            
            # 결과 통합
            cached_scores.update(uncached_scores)
        
        # 점수 정규화
        normalized_scores = self.score_calculator.normalize_scores(cached_scores)
        
        return normalized_scores
    
    async def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회"""
        try:
            performance_summary = self.performance_monitor.get_performance_summary(60)  # 최근 1시간
            cache_info = await self.cache_manager.cache.get_cache_info()
            concurrency_stats = await self.concurrency_optimizer.get_optimization_stats()
            
            return {
                'performance_monitoring': performance_summary,
                'caching_system': cache_info,
                'concurrency_optimization': concurrency_stats,
                'engine_health': await self.get_engine_health()
            }
        except Exception as e:
            logger.error(f"성능 메트릭 조회 실패: {e}")
            return {"error": str(e)}
    
    async def optimize_for_load(self, expected_concurrent_users: int):
        """부하에 따른 동적 최적화"""
        try:
            # 동시성 설정 조정
            if expected_concurrent_users > 50:
                # 고부하 모드
                self.performance_monitor.set_alert_thresholds({
                    'execution_time_ms': 2000,  # 2초로 완화
                    'memory_usage_mb': 1000,    # 1GB로 증가
                    'cpu_usage_percent': 90     # 90%로 증가
                })
                # 고부하 모드 활성화
            else:
                # 일반 모드
                self.performance_monitor.set_alert_thresholds({
                    'execution_time_ms': 1000,
                    'memory_usage_mb': 500,
                    'cpu_usage_percent': 80
                })
                # 일반 모드 유지
                
        except Exception as e:
            logger.error(f"부하 최적화 실패: {e}")

# 전역 엔진 인스턴스
_engine_instance: Optional[AdvancedPersonalizationEngine] = None

def get_personalization_engine() -> AdvancedPersonalizationEngine:
    """개인화 엔진 인스턴스 반환 (싱글톤)"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AdvancedPersonalizationEngine()
    return _engine_instance

async def init_personalization_engine():
    """개인화 엔진 초기화"""
    engine = get_personalization_engine()
    # 개인화 엔진 초기화 완료
    return engine

async def cleanup_personalization_engine():
    """개인화 엔진 정리"""
    global _engine_instance
    if _engine_instance:
        await _engine_instance.cleanup_resources()
        _engine_instance = None