"""
의도 매칭 유틸리티 함수들
공통으로 사용되는 헬퍼 함수들
"""
from typing import List, Dict, Any, Optional
import json
import logging

from app.config.intent_config import IntentConfig, ScoringConfig

logger = logging.getLogger(__name__)

class IntentUtils:
    """의도 매칭 유틸리티"""
    
    @staticmethod
    def parse_product_tags(tags_data: Any) -> List[str]:
        """제품 태그 파싱"""
        if not tags_data:
            return []
        
        try:
            if isinstance(tags_data, str):
                parsed_tags = json.loads(tags_data)
            else:
                parsed_tags = tags_data
            
            if isinstance(parsed_tags, list):
                return [str(tag).strip() for tag in parsed_tags if tag]
            
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"태그 파싱 실패: {e}")
        
        return []
    
    @staticmethod
    def get_intent_keywords(intent_tag: str) -> List[str]:
        """의도 태그의 키워드 목록 조회"""
        return IntentConfig.INTENT_MAPPING.get(intent_tag, [])
    
    @staticmethod
    def get_category_bonus(category: str, intent_tag: str) -> float:
        """카테고리-의도 적합성 보너스 계산"""
        if not category:
            return 0.0
        
        suitable_categories = IntentConfig.CATEGORY_INTENT_MAP.get(intent_tag, [])
        
        for suitable_cat in suitable_categories:
            if suitable_cat in category:
                return ScoringConfig.BASE_SCORES['category_match']
        
        return 0.0
    
    @staticmethod
    def get_brand_expertise_bonus(brand: str, intent_tags: List[str]) -> float:
        """브랜드 전문성 보너스 계산"""
        if not brand or brand not in IntentConfig.BRAND_EXPERTISE:
            return 0.0
        
        brand_config = IntentConfig.BRAND_EXPERTISE[brand]
        total_bonus = 0.0
        
        for intent_tag in intent_tags:
            if intent_tag in brand_config:
                expertise_multiplier = brand_config[intent_tag]
                total_bonus += ScoringConfig.BASE_SCORES['brand_bonus'] * (expertise_multiplier - 1.0)
        
        return min(total_bonus, 15.0)  # 최대 15점
    
    @staticmethod
    def calculate_confidence_score(scores: Dict[str, float], keyword_count: int) -> float:
        """매칭 신뢰도 계산"""
        
        # 점수가 있는 항목들
        active_scores = [score for score in scores.values() if score > 0]
        
        if not active_scores:
            return 0.0
        
        # 평균 점수
        avg_score = sum(active_scores) / len(active_scores)
        
        # 다양성 (여러 방식으로 매칭될수록 신뢰도 높음)
        diversity = len(active_scores) / len(scores)
        
        # 키워드 매칭 수
        keyword_factor = min(keyword_count / 3.0, 1.0)
        
        # 최고 점수
        max_score = max(scores.values()) / 100.0
        
        confidence = (
            (avg_score / 100.0) * 0.4 +
            diversity * 0.3 +
            keyword_factor * 0.2 +
            max_score * 0.1
        )
        
        return min(confidence, 1.0)
    
    @staticmethod
    def normalize_score(score: float, max_score: float = 100.0) -> float:
        """점수 정규화"""
        return min(max(score, 0.0), max_score)
    
    @staticmethod
    def get_score_category(score: float) -> str:
        """점수 카테고리 분류"""
        thresholds = IntentConfig.SCORE_THRESHOLDS
        
        if score >= thresholds['high_confidence']:
            return 'high'
        elif score >= thresholds['medium_confidence']:
            return 'medium'
        elif score >= thresholds['low_confidence']:
            return 'low'
        else:
            return 'very_low'

class ProductUtils:
    """제품 관련 유틸리티"""
    
    @staticmethod
    def extract_product_features(product) -> Dict[str, Any]:
        """제품 특성 추출"""
        
        features = {
            'name': getattr(product, 'name', ''),
            'brand': getattr(product, 'brand_name', ''),
            'category': getattr(product, 'category_name', ''),
            'tags': IntentUtils.parse_product_tags(getattr(product, 'tags', None)),
            'product_id': getattr(product, 'product_id', 0)
        }
        
        return features
    
    @staticmethod
    def calculate_product_type_weight(category: str) -> float:
        """제품 타입별 가중치"""
        from app.config.intent_config import CategoryConfig
        
        for product_type, weight in CategoryConfig.CATEGORY_WEIGHTS.items():
            if product_type in category:
                return weight
        
        return 1.0
    
    @staticmethod
    def is_premium_brand(brand: str) -> bool:
        """프리미엄 브랜드 여부"""
        premium_brands = [
            '라로슈포제', '아벤느', '비쉬', '세타필', '유세린',
            'La Roche-Posay', 'Avene', 'Vichy', 'Cetaphil', 'Eucerin'
        ]
        
        return brand in premium_brands

class ValidationUtils:
    """검증 유틸리티"""
    
    @staticmethod
    def validate_intent_tags(intent_tags: List[str]) -> List[str]:
        """의도 태그 유효성 검증"""
        from app.config.intent_config import TagConfig
        
        if not intent_tags:
            raise ValueError("의도 태그가 필요합니다")
        
        # 지원하지 않는 태그 확인
        unsupported = [
            tag for tag in intent_tags 
            if tag not in TagConfig.SUPPORTED_INTENT_TAGS
        ]
        
        if unsupported:
            raise ValueError(f"지원하지 않는 의도 태그: {unsupported}")
        
        return intent_tags
    
    @staticmethod
    def validate_top_n(top_n: int) -> int:
        """추천 개수 유효성 검증"""
        if not isinstance(top_n, int) or top_n < 1 or top_n > 20:
            raise ValueError("추천 개수는 1-20 사이의 정수여야 합니다")
        
        return top_n