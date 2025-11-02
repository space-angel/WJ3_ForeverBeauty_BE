"""
정렬 서비스 (Ranking Service)
6단계 tie-break 알고리즘을 통한 제품 정렬 및 추천 결과 생성
"""
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import Counter, defaultdict
import logging
import time
from datetime import datetime

from app.services.product_service import ProductService
# ScoringResult 클래스가 없으므로 Dict 사용
from app.models.request import RecommendationRequest
from app.models.postgres_models import Product
from app.models.response import ProductRecommendation, RuleHit

logger = logging.getLogger(__name__)

@dataclass
class RankedProduct:
    """정렬된 제품"""
    product: Product
    rank: int
    final_score: int
    base_score: int = 100
    penalty_score: int = 0
    intent_match_score: int = 50
    reasons: List[str] = field(default_factory=list)
    rule_hits: List[RuleHit] = field(default_factory=list)
    excluded_by_rules: bool = False
    
    def __post_init__(self):
        """초기화 후 처리"""
        if not self.reasons:
            self.reasons = self._generate_default_reasons()
    
    def _generate_default_reasons(self) -> List[str]:
        """기본 추천 사유 생성"""
        reasons = []
        
        # 의도 일치도 기반 사유
        if self.intent_match_score >= 80:
            reasons.append("요청하신 의도와 매우 잘 맞는 제품입니다")
        elif self.intent_match_score >= 60:
            reasons.append("요청하신 의도와 잘 맞는 제품입니다")
        elif self.intent_match_score >= 40:
            reasons.append("요청하신 의도와 어느 정도 맞는 제품입니다")
        
        # 안전성 기반 사유
        if self.penalty_score == 0:
            reasons.append("안전성 우려가 없는 제품입니다")
        elif self.penalty_score <= 10:
            reasons.append("경미한 주의사항이 있지만 사용 가능한 제품입니다")
        elif self.penalty_score <= 25:
            reasons.append("일부 주의사항이 있으니 신중히 사용하세요")
        else:
            reasons.append("여러 주의사항이 있으니 전문가와 상담 후 사용하세요")
        
        # 브랜드/제품 특성 기반 사유
        if hasattr(self.product, 'brand_name') and self.product.brand_name:
            reasons.append(f"{self.product.brand_name} 브랜드의 신뢰할 수 있는 제품입니다")
        
        return reasons[:3]  # 최대 3개까지

class RankingService:
    """
    정렬 서비스
    
    6단계 tie-break 알고리즘을 사용하여 제품을 정렬하고
    최종 추천 결과를 생성하는 서비스
    """
    
    def __init__(self):
        """정렬 서비스 초기화"""
        try:
            self.product_service = ProductService()
            
            # 정렬 가중치 설정
            self.tie_break_weights = {
                'final_score': 1000,      # 1순위: 최종 점수
                'intent_match': 100,      # 2순위: 의도 일치도
                'penalty_count': -10,     # 3순위: 감점 룰 수 (적을수록 좋음)
                'brand_preference': 5,    # 4순위: 브랜드 선호도
                'product_id': -1          # 5순위: 제품 ID (최신순)
            }
            
            # 성능 모니터링
            self._ranking_count = 0
            self._total_ranking_time = 0.0
            
            # RankingService 초기화 완료
            
        except Exception as e:
            logger.error(f"RankingService 초기화 실패: {e}")
            raise RuntimeError(f"정렬 서비스 초기화 실패: {e}")
    
    def rank_products(
        self,
        products: List[Product],
        scoring_results: Dict[int, Dict[str, Any]],
        request: RecommendationRequest,
        excluded_products: Set[int] = None
    ) -> List[RankedProduct]:
        """
        제품 정렬 수행
        
        Args:
            products: 정렬할 제품 목록
            scoring_results: 감점 평가 결과
            request: 추천 요청
            excluded_products: 배제된 제품 ID 집합
            
        Returns:
            List[RankedProduct]: 정렬된 제품 목록
        """
        start_time = time.time()
        
        # 입력 유효성 검증
        if not products:
            logger.warning("정렬할 제품이 없습니다")
            return []
        
        if not request:
            raise ValueError("추천 요청이 없습니다")
        
        excluded_products = excluded_products or set()
        
        try:
            # 정렬 가능한 제품만 필터링
            valid_products = [
                p for p in products 
                if p.product_id not in excluded_products
            ]
            
            if not valid_products:
                logger.warning("정렬 가능한 제품이 없습니다 (모두 배제됨)")
                return []
            
            # RankedProduct 객체 생성
            ranked_products = []
            
            for product in valid_products:
                scoring_result = scoring_results.get(product.product_id)
                
                # 의도 일치도 계산
                intent_match_score = self.product_service.calculate_intent_match_score(
                    product, request.intent_tags or []
                )
                
                # RankedProduct 생성
                ranked_product = RankedProduct(
                    product=product,
                    rank=0,  # 나중에 설정
                    final_score=scoring_result['final_score'] if scoring_result else 100,
                    base_score=scoring_result['base_score'] if scoring_result else 100,
                    penalty_score=scoring_result['penalty_score'] if scoring_result else 0,
                    intent_match_score=intent_match_score,
                    rule_hits=scoring_result['rule_hits'] if scoring_result else []
                )
                
                # 추천 사유 생성
                ranked_product.reasons = self._generate_recommendation_reasons(
                    ranked_product, request
                )
                
                ranked_products.append(ranked_product)
            
            # 6단계 tie-break 정렬 수행
            sorted_products = self._apply_tie_break_sorting(ranked_products, request)
            
            # 순위 할당
            for i, product in enumerate(sorted_products):
                product.rank = i + 1
            
            # 성능 통계 업데이트
            ranking_time = (time.time() - start_time) * 1000
            self._ranking_count += 1
            self._total_ranking_time += ranking_time
            
            # 제품 정렬 완료
            
            return sorted_products
            
        except Exception as e:
            logger.error(f"제품 정렬 중 오류: {e}")
            # 오류 발생 시 기본 정렬 (제품 ID 순)
            fallback_products = []
            for i, product in enumerate(valid_products):
                ranked_product = RankedProduct(
                    product=product,
                    rank=i + 1,
                    final_score=100,
                    intent_match_score=50,
                    reasons=["기본 추천"]
                )
                fallback_products.append(ranked_product)
            
            return fallback_products
    
    def _apply_tie_break_sorting(
        self, 
        products: List[RankedProduct], 
        request: RecommendationRequest
    ) -> List[RankedProduct]:
        """
        6단계 tie-break 정렬 알고리즘 적용
        
        1순위: 최종 점수 (높을수록 좋음)
        2순위: 의도 일치도 (높을수록 좋음)
        3순위: 감점 룰 수 (적을수록 좋음)
        4순위: 브랜드 선호도 (높을수록 좋음)
        5순위: 카테고리 일치도 (높을수록 좋음)
        6순위: 제품 ID (높을수록 좋음, 최신순)
        """
        
        def sort_key(ranked_product: RankedProduct) -> Tuple:
            product = ranked_product.product
            
            # 1순위: 최종 점수
            final_score = ranked_product.final_score
            
            # 2순위: 의도 일치도
            intent_match = ranked_product.intent_match_score
            
            # 3순위: 감점 룰 수 (적을수록 좋음)
            penalty_count = len(ranked_product.rule_hits)
            
            # 4순위: 브랜드 선호도
            brand_preference = self._calculate_brand_preference(
                getattr(product, 'brand_name', ''), request
            )
            
            # 5순위: 카테고리 일치도
            category_match = self._calculate_category_match(
                getattr(product, 'category_name', ''), request
            )
            
            # 6순위: 제품 ID (최신순)
            product_id = product.product_id
            
            return (
                -final_score,        # 높을수록 좋음 (음수로 변환)
                -intent_match,       # 높을수록 좋음 (음수로 변환)
                penalty_count,       # 적을수록 좋음
                -brand_preference,   # 높을수록 좋음 (음수로 변환)
                -category_match,     # 높을수록 좋음 (음수로 변환)
                -product_id          # 높을수록 좋음 (음수로 변환)
            )
        
        try:
            sorted_products = sorted(products, key=sort_key)
            
            logger.debug(f"tie-break 정렬 완료: {len(sorted_products)}개 제품")
            return sorted_products
            
        except Exception as e:
            logger.error(f"tie-break 정렬 오류: {e}")
            # 오류 시 기본 정렬
            return sorted(products, key=lambda p: (-p.final_score, -p.intent_match_score))
    
    def _calculate_brand_preference(self, brand_name: str, request: RecommendationRequest) -> int:
        """브랜드 선호도 계산"""
        if not brand_name:
            return 0
        
        # 간단한 브랜드 선호도 매핑 (실제로는 더 복잡한 로직 필요)
        premium_brands = {
            '라로슈포제', '아벤느', '비쉬', '세타필', '유세린',
            'La Roche-Posay', 'Avene', 'Vichy', 'Cetaphil', 'Eucerin'
        }
        
        popular_brands = {
            '이니스프리', '에뛰드하우스', '더페이스샵', '토니앤가이',
            'Innisfree', 'Etude House', 'The Face Shop'
        }
        
        brand_lower = brand_name.lower()
        
        for premium in premium_brands:
            if premium.lower() in brand_lower:
                return 10
        
        for popular in popular_brands:
            if popular.lower() in brand_lower:
                return 5
        
        return 1  # 기본 점수
    
    def _calculate_category_match(self, category_name: str, request: RecommendationRequest) -> int:
        """카테고리 일치도 계산"""
        if not category_name or not request.category_like:
            return 0
        
        category_lower = category_name.lower()
        request_category_lower = request.category_like.lower()
        
        # 완전 일치
        if request_category_lower in category_lower:
            return 10
        
        # 부분 일치
        if any(word in category_lower for word in request_category_lower.split()):
            return 5
        
        return 0
    
    def _generate_recommendation_reasons(
        self, 
        ranked_product: RankedProduct, 
        request: RecommendationRequest
    ) -> List[str]:
        """추천 사유 생성"""
        reasons = []
        product = ranked_product.product
        
        # 의도 일치 기반 사유
        if ranked_product.intent_match_score >= 80:
            intent_tags = ', '.join(request.intent_tags[:2]) if request.intent_tags else '요청 의도'
            reasons.append(f"{intent_tags}에 매우 적합한 제품입니다")
        elif ranked_product.intent_match_score >= 60:
            reasons.append("요청하신 용도에 적합한 제품입니다")
        
        # 안전성 기반 사유
        if ranked_product.penalty_score == 0:
            reasons.append("안전성 우려가 없어 안심하고 사용할 수 있습니다")
        elif ranked_product.penalty_score <= 15:
            reasons.append("경미한 주의사항이 있지만 일반적으로 안전합니다")
        
        # 브랜드 기반 사유
        brand_name = getattr(product, 'brand_name', '')
        if brand_name:
            brand_pref = self._calculate_brand_preference(brand_name, request)
            if brand_pref >= 10:
                reasons.append(f"{brand_name}는 전문가들이 신뢰하는 브랜드입니다")
            elif brand_pref >= 5:
                reasons.append(f"{brand_name}는 인기 있는 브랜드입니다")
        
        # 카테고리 일치 기반 사유
        if request.category_like:
            category_match = self._calculate_category_match(
                getattr(product, 'category_name', ''), request
            )
            if category_match >= 10:
                reasons.append(f"요청하신 {request.category_like} 카테고리에 정확히 맞습니다")
        
        # 감점 관련 경고
        if ranked_product.penalty_score > 25:
            reasons.append("일부 주의사항이 있으니 사용 전 확인해주세요")
        
        # 최소 1개 사유는 보장
        if not reasons:
            reasons.append("종합적으로 추천할 만한 제품입니다")
        
        return reasons[:3]  # 최대 3개까지
    
    def get_ranking_statistics(self, ranked_products: List[RankedProduct]) -> Dict[str, Any]:
        """정렬 통계 정보"""
        if not ranked_products:
            return {
                'total_products': 0,
                'average_final_score': 0,
                'score_distribution': {},
                'intent_match_distribution': {},
                'top_brands': [],
                'penalty_distribution': {}
            }
        
        total_products = len(ranked_products)
        
        # 평균 점수
        avg_final_score = sum(p.final_score for p in ranked_products) / total_products
        avg_intent_match = sum(p.intent_match_score for p in ranked_products) / total_products
        
        # 점수 분포
        score_ranges = {
            '90-100점': 0,
            '80-89점': 0,
            '70-79점': 0,
            '60-69점': 0,
            '60점 미만': 0
        }
        
        for product in ranked_products:
            score = product.final_score
            if score >= 90:
                score_ranges['90-100점'] += 1
            elif score >= 80:
                score_ranges['80-89점'] += 1
            elif score >= 70:
                score_ranges['70-79점'] += 1
            elif score >= 60:
                score_ranges['60-69점'] += 1
            else:
                score_ranges['60점 미만'] += 1
        
        # 의도 일치도 분포
        intent_ranges = {
            '80점 이상': 0,
            '60-79점': 0,
            '40-59점': 0,
            '40점 미만': 0
        }
        
        for product in ranked_products:
            intent = product.intent_match_score
            if intent >= 80:
                intent_ranges['80점 이상'] += 1
            elif intent >= 60:
                intent_ranges['60-79점'] += 1
            elif intent >= 40:
                intent_ranges['40-59점'] += 1
            else:
                intent_ranges['40점 미만'] += 1
        
        # 상위 브랜드
        brand_counts = Counter()
        for product in ranked_products:
            brand = getattr(product.product, 'brand_name', 'Unknown')
            if brand:
                brand_counts[brand] += 1
        
        top_brands = [
            {'brand': brand, 'count': count}
            for brand, count in brand_counts.most_common(5)
        ]
        
        # 감점 분포
        penalty_ranges = {
            '감점 없음': 0,
            '1-10점': 0,
            '11-25점': 0,
            '26점 이상': 0
        }
        
        for product in ranked_products:
            penalty = product.penalty_score
            if penalty == 0:
                penalty_ranges['감점 없음'] += 1
            elif penalty <= 10:
                penalty_ranges['1-10점'] += 1
            elif penalty <= 25:
                penalty_ranges['11-25점'] += 1
            else:
                penalty_ranges['26점 이상'] += 1
        
        return {
            'total_products': total_products,
            'average_final_score': round(avg_final_score, 1),
            'average_intent_match': round(avg_intent_match, 1),
            'score_distribution': score_ranges,
            'intent_match_distribution': intent_ranges,
            'top_brands': top_brands,
            'penalty_distribution': penalty_ranges
        }
    
    def convert_to_recommendation_response(
        self, 
        ranked_products: List[RankedProduct], 
        top_n: int = 10
    ) -> List[ProductRecommendation]:
        """RankedProduct를 ProductRecommendation으로 변환"""
        recommendations = []
        
        for ranked_product in ranked_products[:top_n]:
            product = ranked_product.product
            
            recommendation = ProductRecommendation(
                rank=ranked_product.rank,
                product_id=product.product_id,
                product_name=product.name,
                brand_name=getattr(product, 'brand_name', 'Unknown'),
                category=getattr(product, 'category_name', 'Unknown'),
                final_score=ranked_product.final_score,
                base_score=ranked_product.base_score,
                penalty_score=ranked_product.penalty_score,
                intent_match_score=ranked_product.intent_match_score,
                reasons=ranked_product.reasons,
                rule_hits=ranked_product.rule_hits
            )
            
            recommendations.append(recommendation)
        
        return recommendations
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회"""
        return {
            'total_rankings': self._ranking_count,
            'total_ranking_time_ms': self._total_ranking_time,
            'avg_ranking_time_ms': self._total_ranking_time / max(self._ranking_count, 1)
        }
    
    def clear_cache(self):
        """캐시 초기화 (현재는 캐시 없음)"""
        # 정렬 서비스 캐시 초기화
    
    def close(self):
        """리소스 정리"""
        try:
            # 성능 통계 로깅
            if self._ranking_count > 0:
                avg_time = self._total_ranking_time / self._ranking_count
                # RankingService 종료 통계
            
        except Exception as e:
            logger.error(f"RankingService 리소스 정리 오류: {e}")
        
        # RankingService 종료 완료