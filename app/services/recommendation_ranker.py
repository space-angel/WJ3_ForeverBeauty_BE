"""
추천 순위 결정 시스템
최종 점수를 기반으로 제품 순위를 결정하고 다양성을 확보하는 시스템
"""

from typing import List, Dict, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import logging
import random
from enum import Enum

from app.models.personalization_models import ProductScore, PersonalizedRecommendation
from app.models.postgres_models import Product

logger = logging.getLogger(__name__)

class TieBreakCriteria(Enum):
    """동점 처리 기준"""
    BRAND_PREFERENCE = "brand_preference"    # 브랜드 선호도
    SAFETY_SCORE = "safety_score"           # 안전성 점수
    PERSONALIZATION_SCORE = "personalization_score"  # 개인화 점수
    PRODUCT_ID = "product_id"               # 제품 ID (최종)

@dataclass
class RankingConfig:
    """순위 결정 설정"""
    max_recommendations: int = 10
    enable_diversity: bool = True
    max_same_brand: int = 3
    max_same_category: int = 4
    tie_break_criteria: List[TieBreakCriteria] = field(default_factory=lambda: [
        TieBreakCriteria.SAFETY_SCORE,
        TieBreakCriteria.PERSONALIZATION_SCORE,
        TieBreakCriteria.BRAND_PREFERENCE,
        TieBreakCriteria.PRODUCT_ID
    ])
    diversity_weight: float = 0.1  # 다양성 가중치 (0-1)
    min_score_threshold: float = 30.0  # 최소 점수 임계값

@dataclass
class RankingResult:
    """순위 결정 결과"""
    ranked_products: List[ProductScore]
    diversity_info: Dict[str, Any] = field(default_factory=dict)
    tie_break_applied: List[Tuple[int, int, str]] = field(default_factory=list)  # (product_id1, product_id2, criteria)
    filtered_count: int = 0
    total_candidates: int = 0

class BasicRanker:
    """기본 순위 결정기"""
    
    def __init__(self, config: Optional[RankingConfig] = None):
        self.config = config or RankingConfig()
    
    def rank_products(
        self,
        product_scores: Dict[int, ProductScore],
        products: Dict[int, Product],
        user_profile: Optional[Dict[str, Any]] = None
    ) -> RankingResult:
        """기본 순위 결정"""
        
        # 1. 최소 점수 임계값 필터링
        filtered_scores = self._filter_by_threshold(product_scores)
        
        # 2. 점수 기준 정렬
        sorted_scores = self._sort_by_score(filtered_scores, products, user_profile)
        
        # 3. 상위 N개 선별
        top_scores = sorted_scores[:self.config.max_recommendations]
        
        return RankingResult(
            ranked_products=top_scores,
            filtered_count=len(product_scores) - len(filtered_scores),
            total_candidates=len(product_scores)
        )
    
    def _filter_by_threshold(self, product_scores: Dict[int, ProductScore]) -> List[ProductScore]:
        """최소 점수 임계값 필터링"""
        return [
            score for score in product_scores.values()
            if score.final_score >= self.config.min_score_threshold
        ]
    
    def _sort_by_score(
        self,
        product_scores: List[ProductScore],
        products: Dict[int, Product],
        user_profile: Optional[Dict[str, Any]]
    ) -> List[ProductScore]:
        """점수 기준 정렬 (동점 처리 포함)"""
        
        def sort_key(score: ProductScore) -> Tuple:
            """정렬 키 생성"""
            keys = [-score.final_score]  # 점수는 내림차순 (음수로 변환)
            
            # 동점 처리 기준 적용
            for criteria in self.config.tie_break_criteria:
                if criteria == TieBreakCriteria.SAFETY_SCORE:
                    keys.append(-score.score_breakdown.safety_score)
                elif criteria == TieBreakCriteria.PERSONALIZATION_SCORE:
                    keys.append(-score.score_breakdown.personalization_score)
                elif criteria == TieBreakCriteria.BRAND_PREFERENCE:
                    brand_score = self._get_brand_preference_score(score, user_profile)
                    keys.append(-brand_score)
                elif criteria == TieBreakCriteria.PRODUCT_ID:
                    keys.append(score.product_id)  # ID는 오름차순
            
            return tuple(keys)
        
        return sorted(product_scores, key=sort_key)
    
    def _get_brand_preference_score(
        self,
        product_score: ProductScore,
        user_profile: Optional[Dict[str, Any]]
    ) -> float:
        """브랜드 선호도 점수 계산"""
        if not user_profile:
            return 0.0
        
        preferred_brands = user_profile.get('preferences', {}).get('preferred_brands', [])
        if product_score.brand_name in preferred_brands:
            return 10.0
        
        return 0.0

class DiversityRanker:
    """다양성 확보 순위 결정기"""
    
    def __init__(self, config: Optional[RankingConfig] = None):
        self.config = config or RankingConfig()
        self.basic_ranker = BasicRanker(config)
    
    def rank_with_diversity(
        self,
        product_scores: Dict[int, ProductScore],
        products: Dict[int, Product],
        user_profile: Optional[Dict[str, Any]] = None
    ) -> RankingResult:
        """다양성을 고려한 순위 결정"""
        
        # 1. 기본 순위 결정
        basic_result = self.basic_ranker.rank_products(product_scores, products, user_profile)
        
        if not self.config.enable_diversity:
            return basic_result
        
        # 2. 다양성 확보 적용
        diversified_products = self._apply_diversity_constraints(
            basic_result.ranked_products, products
        )
        
        # 3. 다양성 정보 수집
        diversity_info = self._analyze_diversity(diversified_products, products)
        
        return RankingResult(
            ranked_products=diversified_products,
            diversity_info=diversity_info,
            tie_break_applied=basic_result.tie_break_applied,
            filtered_count=basic_result.filtered_count,
            total_candidates=basic_result.total_candidates
        )
    
    def _apply_diversity_constraints(
        self,
        ranked_products: List[ProductScore],
        products: Dict[int, Product]
    ) -> List[ProductScore]:
        """다양성 제약 조건 적용"""
        
        selected_products = []
        brand_count = defaultdict(int)
        category_count = defaultdict(int)
        
        for product_score in ranked_products:
            product = products.get(product_score.product_id)
            if not product:
                continue
            
            # 브랜드 다양성 검사
            if brand_count[product.brand_name] >= self.config.max_same_brand:
                continue
            
            # 카테고리 다양성 검사
            if category_count[product.category_name] >= self.config.max_same_category:
                continue
            
            # 선택
            selected_products.append(product_score)
            brand_count[product.brand_name] += 1
            category_count[product.category_name] += 1
            
            # 최대 추천 수 도달 시 종료
            if len(selected_products) >= self.config.max_recommendations:
                break
        
        return selected_products
    
    def _analyze_diversity(
        self,
        products: List[ProductScore],
        product_details: Dict[int, Product]
    ) -> Dict[str, Any]:
        """다양성 분석"""
        
        brands = []
        categories = []
        
        for product_score in products:
            product = product_details.get(product_score.product_id)
            if product:
                brands.append(product.brand_name)
                categories.append(product.category_name)
        
        brand_distribution = dict(Counter(brands))
        category_distribution = dict(Counter(categories))
        
        return {
            "total_products": len(products),
            "unique_brands": len(set(brands)),
            "unique_categories": len(set(categories)),
            "brand_distribution": brand_distribution,
            "category_distribution": category_distribution,
            "diversity_score": self._calculate_diversity_score(brand_distribution, category_distribution)
        }
    
    def _calculate_diversity_score(
        self,
        brand_distribution: Dict[str, int],
        category_distribution: Dict[str, int]
    ) -> float:
        """다양성 점수 계산 (0-1, 높을수록 다양함)"""
        
        if not brand_distribution or not category_distribution:
            return 0.0
        
        # 브랜드 다양성 (Shannon Entropy 기반)
        total_brands = sum(brand_distribution.values())
        brand_entropy = 0.0
        for count in brand_distribution.values():
            if count > 0:
                p = count / total_brands
                brand_entropy -= p * (p ** 0.5)  # 간단한 다양성 지수
        
        # 카테고리 다양성
        total_categories = sum(category_distribution.values())
        category_entropy = 0.0
        for count in category_distribution.values():
            if count > 0:
                p = count / total_categories
                category_entropy -= p * (p ** 0.5)
        
        # 정규화 (0-1 범위)
        max_brand_entropy = len(brand_distribution) ** 0.5
        max_category_entropy = len(category_distribution) ** 0.5
        
        brand_diversity = brand_entropy / max_brand_entropy if max_brand_entropy > 0 else 0
        category_diversity = category_entropy / max_category_entropy if max_category_entropy > 0 else 0
        
        # 가중 평균 (브랜드 60%, 카테고리 40%)
        return (brand_diversity * 0.6) + (category_diversity * 0.4)

class PriceBasedRanker:
    """가격대별 다양성 순위 결정기 (선택사항)"""
    
    def __init__(self, config: Optional[RankingConfig] = None):
        self.config = config or RankingConfig()
        self.diversity_ranker = DiversityRanker(config)
    
    def rank_with_price_diversity(
        self,
        product_scores: Dict[int, ProductScore],
        products: Dict[int, Product],
        user_profile: Optional[Dict[str, Any]] = None,
        price_ranges: Optional[List[Tuple[float, float]]] = None
    ) -> RankingResult:
        """가격대별 다양성을 고려한 순위 결정"""
        
        # 기본 다양성 순위 결정
        result = self.diversity_ranker.rank_with_diversity(product_scores, products, user_profile)
        
        if not price_ranges:
            return result
        
        # 가격대별 분산 적용
        price_diversified = self._apply_price_diversity(
            result.ranked_products, products, price_ranges
        )
        
        # 가격 다양성 정보 추가
        price_info = self._analyze_price_diversity(price_diversified, products)
        result.diversity_info.update(price_info)
        result.ranked_products = price_diversified
        
        return result
    
    def _apply_price_diversity(
        self,
        ranked_products: List[ProductScore],
        products: Dict[int, Product],
        price_ranges: List[Tuple[float, float]]
    ) -> List[ProductScore]:
        """가격대별 다양성 적용"""
        
        # 가격 정보가 없는 경우 기존 순위 유지
        return ranked_products
    
    def _analyze_price_diversity(
        self,
        products: List[ProductScore],
        product_details: Dict[int, Product]
    ) -> Dict[str, Any]:
        """가격 다양성 분석"""
        
        return {
            "price_diversity_applied": False,
            "price_ranges_covered": 0
        }

class RecommendationRanker:
    """통합 추천 순위 결정 시스템"""
    
    def __init__(self, config: Optional[RankingConfig] = None):
        self.config = config or RankingConfig()
        self.basic_ranker = BasicRanker(config)
        self.diversity_ranker = DiversityRanker(config)
        self.price_ranker = PriceBasedRanker(config)
    
    def rank_recommendations(
        self,
        product_scores: Dict[int, ProductScore],
        products: Dict[int, Product],
        user_profile: Optional[Dict[str, Any]] = None,
        ranking_strategy: str = "diversity"
    ) -> RankingResult:
        """추천 순위 결정"""
        
        try:
            if ranking_strategy == "basic":
                return self.basic_ranker.rank_products(product_scores, products, user_profile)
            elif ranking_strategy == "diversity":
                return self.diversity_ranker.rank_with_diversity(product_scores, products, user_profile)
            elif ranking_strategy == "price_diversity":
                return self.price_ranker.rank_with_price_diversity(product_scores, products, user_profile)
            else:
                logger.warning(f"알 수 없는 순위 전략: {ranking_strategy}, 기본 전략 사용")
                return self.basic_ranker.rank_products(product_scores, products, user_profile)
                
        except Exception as e:
            logger.error(f"순위 결정 실패: {e}")
            # 폴백: 점수 순 정렬
            return self._fallback_ranking(product_scores)
    
    def _fallback_ranking(self, product_scores: Dict[int, ProductScore]) -> RankingResult:
        """폴백 순위 결정 (단순 점수 순)"""
        sorted_scores = sorted(
            product_scores.values(),
            key=lambda x: x.final_score,
            reverse=True
        )
        
        return RankingResult(
            ranked_products=sorted_scores[:self.config.max_recommendations],
            total_candidates=len(product_scores)
        )
    
    def create_personalized_recommendation(
        self,
        ranking_result: RankingResult,
        products: Dict[int, Product],
        intent_tags: List[str],
        user_profile: Optional[Dict[str, Any]] = None,
        session_id: Optional[str] = None,
        execution_time_ms: float = 0.0
    ) -> PersonalizedRecommendation:
        """PersonalizedRecommendation 객체 생성"""
        
        # 사용자 프로필 요약
        profile_summary = {}
        if user_profile:
            profile_summary = {
                "age_group": user_profile.get('age_group'),
                "skin_type": user_profile.get('skin_type'),
                "gender": user_profile.get('gender'),
                "preferences_count": len(user_profile.get('preferences', {}))
            }
        
        # 전체 인사이트 생성
        insights = self._generate_insights(ranking_result, products)
        
        # 개인화 노트 생성
        personalization_notes = self._generate_personalization_notes(
            ranking_result, user_profile
        )
        
        return PersonalizedRecommendation(
            user_id=user_profile.get('user_id') if user_profile else None,
            session_id=session_id,
            intent_tags=intent_tags,
            user_profile_summary=profile_summary,
            recommended_products=ranking_result.ranked_products,
            total_candidates=ranking_result.total_candidates,
            filtered_count=ranking_result.filtered_count,
            execution_time_ms=execution_time_ms,
            overall_insights=insights,
            personalization_notes=personalization_notes
        )
    
    def _generate_insights(
        self,
        ranking_result: RankingResult,
        products: Dict[int, Product]
    ) -> List[str]:
        """전체 분석 인사이트 생성"""
        insights = []
        
        if not ranking_result.ranked_products:
            insights.append("추천 가능한 제품이 없습니다.")
            return insights
        
        # 점수 분포 분석
        scores = [p.final_score for p in ranking_result.ranked_products]
        avg_score = sum(scores) / len(scores)
        max_score = max(scores)
        
        if avg_score >= 80:
            insights.append(f"매우 적합한 제품들이 추천되었습니다 (평균 점수: {avg_score:.1f})")
        elif avg_score >= 65:
            insights.append(f"적합한 제품들이 추천되었습니다 (평균 점수: {avg_score:.1f})")
        else:
            insights.append(f"부분적으로 적합한 제품들이 추천되었습니다 (평균 점수: {avg_score:.1f})")
        
        # 다양성 분석
        if ranking_result.diversity_info:
            diversity_score = ranking_result.diversity_info.get('diversity_score', 0)
            unique_brands = ranking_result.diversity_info.get('unique_brands', 0)
            
            if diversity_score >= 0.7:
                insights.append(f"다양한 브랜드({unique_brands}개)의 제품이 균형있게 추천되었습니다")
            elif unique_brands > 1:
                insights.append(f"{unique_brands}개 브랜드의 제품이 추천되었습니다")
        
        # 필터링 정보
        if ranking_result.filtered_count > 0:
            insights.append(f"안전성 기준에 따라 {ranking_result.filtered_count}개 제품이 제외되었습니다")
        
        return insights
    
    def _generate_personalization_notes(
        self,
        ranking_result: RankingResult,
        user_profile: Optional[Dict[str, Any]]
    ) -> List[str]:
        """개인화 노트 생성"""
        notes = []
        
        if not user_profile:
            notes.append("사용자 프로필 정보가 없어 일반적인 추천을 제공합니다")
            return notes
        
        age_group = user_profile.get('age_group')
        skin_type = user_profile.get('skin_type')
        
        if age_group:
            notes.append(f"{age_group} 연령대에 적합한 제품들로 선별되었습니다")
        
        if skin_type:
            notes.append(f"{skin_type} 피부타입에 맞는 성분들이 고려되었습니다")
        
        # 선호도 반영
        preferences = user_profile.get('preferences', {})
        if preferences.get('preferred_brands'):
            notes.append("선호 브랜드가 우선적으로 고려되었습니다")
        
        if preferences.get('avoided_ingredients'):
            notes.append("기피 성분이 포함된 제품은 제외되었습니다")
        
        return notes
    
    def get_ranking_statistics(self, ranking_result: RankingResult) -> Dict[str, Any]:
        """순위 결정 통계 정보"""
        
        if not ranking_result.ranked_products:
            return {"status": "no_recommendations"}
        
        scores = [p.final_score for p in ranking_result.ranked_products]
        
        stats = {
            "total_recommendations": len(ranking_result.ranked_products),
            "score_statistics": {
                "average": sum(scores) / len(scores),
                "maximum": max(scores),
                "minimum": min(scores),
                "range": max(scores) - min(scores)
            },
            "filtering_info": {
                "total_candidates": ranking_result.total_candidates,
                "filtered_count": ranking_result.filtered_count,
                "selection_rate": len(ranking_result.ranked_products) / ranking_result.total_candidates if ranking_result.total_candidates > 0 else 0
            }
        }
        
        # 다양성 정보 추가
        if ranking_result.diversity_info:
            stats["diversity_info"] = ranking_result.diversity_info
        
        # 동점 처리 정보 추가
        if ranking_result.tie_break_applied:
            stats["tie_breaks_applied"] = len(ranking_result.tie_break_applied)
        
        return stats