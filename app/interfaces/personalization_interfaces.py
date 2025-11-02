"""
개인화 추천 엔진 컴포넌트 인터페이스
각 컴포넌트 간의 표준 인터페이스 정의
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Tuple
from uuid import UUID

from app.models.personalization_models import (
    IngredientEffect, ProductIngredientAnalysis, ProfileMatchResult,
    ProductScore, PersonalizedRecommendation, ScoreBreakdown
)
from app.models.postgres_models import Product, Ingredient, CompleteUserProfile

# === 성분 분석 인터페이스 ===

class IIngredientAnalyzer(ABC):
    """성분 분석기 인터페이스"""
    
    @abstractmethod
    async def analyze_product_ingredients(
        self, 
        product: Product, 
        ingredients: List[Ingredient],
        user_profile: Optional[CompleteUserProfile] = None
    ) -> ProductIngredientAnalysis:
        """
        제품의 성분을 분석하여 효능과 부작용을 평가
        
        Args:
            product: 분석할 제품
            ingredients: 제품에 포함된 성분 목록
            user_profile: 사용자 프로필 (개인화 분석용)
            
        Returns:
            ProductIngredientAnalysis: 성분 분석 결과
        """
        pass
    
    @abstractmethod
    async def analyze_single_ingredient(
        self,
        ingredient: Ingredient,
        user_profile: Optional[CompleteUserProfile] = None
    ) -> IngredientEffect:
        """
        개별 성분 분석
        
        Args:
            ingredient: 분석할 성분
            user_profile: 사용자 프로필
            
        Returns:
            IngredientEffect: 성분 효과 분석 결과
        """
        pass
    
    @abstractmethod
    async def get_ingredient_interactions(
        self,
        ingredients: List[Ingredient]
    ) -> List[Dict[str, Any]]:
        """
        성분 간 상호작용 분석
        
        Args:
            ingredients: 분석할 성분 목록
            
        Returns:
            List[Dict]: 상호작용 정보 목록
        """
        pass

# === 사용자 프로필 매칭 인터페이스 ===

class IUserProfileMatcher(ABC):
    """사용자 프로필 매칭기 인터페이스"""
    
    @abstractmethod
    async def match_product_to_profile(
        self,
        product: Product,
        user_profile: CompleteUserProfile,
        ingredient_analysis: Optional[ProductIngredientAnalysis] = None
    ) -> ProfileMatchResult:
        """
        제품과 사용자 프로필 매칭
        
        Args:
            product: 매칭할 제품
            user_profile: 사용자 프로필
            ingredient_analysis: 성분 분석 결과 (선택사항)
            
        Returns:
            ProfileMatchResult: 매칭 결과
        """
        pass
    
    @abstractmethod
    async def calculate_age_compatibility(
        self,
        product: Product,
        age_group: str,
        ingredient_analysis: Optional[ProductIngredientAnalysis] = None
    ) -> Tuple[float, List[str]]:
        """
        연령 적합성 계산
        
        Args:
            product: 제품
            age_group: 연령대
            ingredient_analysis: 성분 분석 결과
            
        Returns:
            Tuple[float, List[str]]: (적합성 점수, 근거 목록)
        """
        pass
    
    @abstractmethod
    async def calculate_skin_type_compatibility(
        self,
        product: Product,
        skin_type: str,
        ingredient_analysis: Optional[ProductIngredientAnalysis] = None
    ) -> Tuple[float, List[str]]:
        """
        피부타입 적합성 계산
        
        Args:
            product: 제품
            skin_type: 피부타입
            ingredient_analysis: 성분 분석 결과
            
        Returns:
            Tuple[float, List[str]]: (적합성 점수, 근거 목록)
        """
        pass
    
    @abstractmethod
    async def calculate_preference_match(
        self,
        product: Product,
        user_profile: CompleteUserProfile
    ) -> Tuple[float, List[str]]:
        """
        사용자 선호도 매칭 계산
        
        Args:
            product: 제품
            user_profile: 사용자 프로필
            
        Returns:
            Tuple[float, List[str]]: (선호도 점수, 근거 목록)
        """
        pass

# === 점수 계산 인터페이스 ===

class IScoreCalculator(ABC):
    """점수 계산기 인터페이스"""
    
    @abstractmethod
    async def calculate_product_score(
        self,
        product: Product,
        intent_tags: List[str],
        user_profile: Optional[CompleteUserProfile] = None,
        ingredient_analysis: Optional[ProductIngredientAnalysis] = None,
        profile_match: Optional[ProfileMatchResult] = None
    ) -> ProductScore:
        """
        제품의 종합 점수 계산
        
        Args:
            product: 점수를 계산할 제품
            intent_tags: 사용자 의도 태그
            user_profile: 사용자 프로필
            ingredient_analysis: 성분 분석 결과
            profile_match: 프로필 매칭 결과
            
        Returns:
            ProductScore: 종합 점수 및 분석 결과
        """
        pass
    
    @abstractmethod
    async def calculate_intent_score(
        self,
        product: Product,
        intent_tags: List[str]
    ) -> Tuple[float, List[str]]:
        """
        의도 매칭 점수 계산
        
        Args:
            product: 제품
            intent_tags: 의도 태그 목록
            
        Returns:
            Tuple[float, List[str]]: (의도 점수, 매칭 근거)
        """
        pass
    
    @abstractmethod
    async def calculate_safety_score(
        self,
        product: Product,
        ingredient_analysis: ProductIngredientAnalysis,
        user_profile: Optional[CompleteUserProfile] = None
    ) -> Tuple[float, List[str]]:
        """
        안전성 점수 계산
        
        Args:
            product: 제품
            ingredient_analysis: 성분 분석 결과
            user_profile: 사용자 프로필
            
        Returns:
            Tuple[float, List[str]]: (안전성 점수, 안전성 근거)
        """
        pass
    
    @abstractmethod
    async def normalize_scores(
        self,
        product_scores: List[ProductScore]
    ) -> List[ProductScore]:
        """
        점수 정규화 (0-100 범위)
        
        Args:
            product_scores: 정규화할 제품 점수 목록
            
        Returns:
            List[ProductScore]: 정규화된 점수 목록
        """
        pass

# === 안전성 필터링 인터페이스 ===

class ISafetyFilter(ABC):
    """안전성 필터링 인터페이스"""
    
    @abstractmethod
    async def filter_unsafe_products(
        self,
        products: List[Product],
        user_profile: Optional[CompleteUserProfile] = None,
        ingredient_analyses: Optional[Dict[int, ProductIngredientAnalysis]] = None
    ) -> Tuple[List[Product], List[Dict[str, Any]]]:
        """
        안전하지 않은 제품 필터링
        
        Args:
            products: 필터링할 제품 목록
            user_profile: 사용자 프로필
            ingredient_analyses: 성분 분석 결과 (제품 ID별)
            
        Returns:
            Tuple[List[Product], List[Dict]]: (안전한 제품 목록, 필터링 사유)
        """
        pass
    
    @abstractmethod
    async def check_age_restrictions(
        self,
        product: Product,
        age_group: str,
        ingredient_analysis: Optional[ProductIngredientAnalysis] = None
    ) -> Tuple[bool, List[str]]:
        """
        연령 제한 확인
        
        Args:
            product: 제품
            age_group: 연령대
            ingredient_analysis: 성분 분석 결과
            
        Returns:
            Tuple[bool, List[str]]: (사용 가능 여부, 제한 사유)
        """
        pass
    
    @abstractmethod
    async def check_skin_type_safety(
        self,
        product: Product,
        skin_type: str,
        ingredient_analysis: Optional[ProductIngredientAnalysis] = None
    ) -> Tuple[bool, List[str]]:
        """
        피부타입별 안전성 확인
        
        Args:
            product: 제품
            skin_type: 피부타입
            ingredient_analysis: 성분 분석 결과
            
        Returns:
            Tuple[bool, List[str]]: (안전 여부, 주의사항)
        """
        pass
    
    @abstractmethod
    async def generate_safety_warnings(
        self,
        product: Product,
        ingredient_analysis: ProductIngredientAnalysis,
        user_profile: Optional[CompleteUserProfile] = None
    ) -> List[str]:
        """
        안전성 경고 메시지 생성
        
        Args:
            product: 제품
            ingredient_analysis: 성분 분석 결과
            user_profile: 사용자 프로필
            
        Returns:
            List[str]: 경고 메시지 목록
        """
        pass

# === 추천 순위 결정 인터페이스 ===

class IRecommendationRanker(ABC):
    """추천 순위 결정 인터페이스"""
    
    @abstractmethod
    async def rank_products(
        self,
        product_scores: List[ProductScore],
        diversification_enabled: bool = True
    ) -> List[ProductScore]:
        """
        제품 순위 결정
        
        Args:
            product_scores: 점수가 계산된 제품 목록
            diversification_enabled: 다양성 확보 여부
            
        Returns:
            List[ProductScore]: 순위가 결정된 제품 목록
        """
        pass
    
    @abstractmethod
    async def apply_tie_breaking(
        self,
        tied_products: List[ProductScore]
    ) -> List[ProductScore]:
        """
        동점 처리 (tie-breaking)
        
        Args:
            tied_products: 동점인 제품 목록
            
        Returns:
            List[ProductScore]: tie-break이 적용된 제품 목록
        """
        pass
    
    @abstractmethod
    async def ensure_diversity(
        self,
        ranked_products: List[ProductScore],
        max_same_brand: int = 2,
        max_same_category: int = 3
    ) -> List[ProductScore]:
        """
        추천 다양성 확보
        
        Args:
            ranked_products: 순위가 결정된 제품 목록
            max_same_brand: 동일 브랜드 최대 개수
            max_same_category: 동일 카테고리 최대 개수
            
        Returns:
            List[ProductScore]: 다양성이 확보된 제품 목록
        """
        pass

# === 메인 추천 엔진 인터페이스 ===

class IPersonalizationEngine(ABC):
    """개인화 추천 엔진 메인 인터페이스"""
    
    @abstractmethod
    async def get_personalized_recommendations(
        self,
        intent_tags: List[str],
        user_profile: Optional[CompleteUserProfile] = None,
        session_id: Optional[str] = None,
        top_n: int = 10,
        include_analysis: bool = True
    ) -> PersonalizedRecommendation:
        """
        개인화된 제품 추천
        
        Args:
            intent_tags: 사용자 의도 태그
            user_profile: 사용자 프로필
            session_id: 세션 ID
            top_n: 추천할 제품 수
            include_analysis: 상세 분석 포함 여부
            
        Returns:
            PersonalizedRecommendation: 개인화된 추천 결과
        """
        pass
    
    @abstractmethod
    async def analyze_single_product(
        self,
        product_id: int,
        user_profile: Optional[CompleteUserProfile] = None,
        intent_tags: Optional[List[str]] = None
    ) -> ProductScore:
        """
        단일 제품 상세 분석
        
        Args:
            product_id: 제품 ID
            user_profile: 사용자 프로필
            intent_tags: 의도 태그 (선택사항)
            
        Returns:
            ProductScore: 제품 분석 결과
        """
        pass
    
    @abstractmethod
    async def get_similar_products(
        self,
        reference_product_id: int,
        user_profile: Optional[CompleteUserProfile] = None,
        top_n: int = 5
    ) -> List[ProductScore]:
        """
        유사 제품 추천
        
        Args:
            reference_product_id: 기준 제품 ID
            user_profile: 사용자 프로필
            top_n: 추천할 제품 수
            
        Returns:
            List[ProductScore]: 유사 제품 목록
        """
        pass
    
    @abstractmethod
    async def explain_recommendation(
        self,
        product_score: ProductScore,
        user_profile: Optional[CompleteUserProfile] = None
    ) -> Dict[str, Any]:
        """
        추천 근거 상세 설명
        
        Args:
            product_score: 설명할 제품 점수
            user_profile: 사용자 프로필
            
        Returns:
            Dict[str, Any]: 상세 설명 정보
        """
        pass

# === 데이터 접근 인터페이스 ===

class IProductRepository(ABC):
    """제품 데이터 저장소 인터페이스"""
    
    @abstractmethod
    async def get_products_by_intent_tags(
        self,
        intent_tags: List[str],
        limit: Optional[int] = None
    ) -> List[Product]:
        """의도 태그로 제품 조회"""
        pass
    
    @abstractmethod
    async def get_product_with_ingredients(
        self,
        product_id: int
    ) -> Tuple[Optional[Product], List[Ingredient]]:
        """제품과 성분 정보 함께 조회"""
        pass
    
    @abstractmethod
    async def get_products_by_category(
        self,
        category_code: str,
        limit: Optional[int] = None
    ) -> List[Product]:
        """카테고리별 제품 조회"""
        pass

class IUserRepository(ABC):
    """사용자 데이터 저장소 인터페이스"""
    
    @abstractmethod
    async def get_complete_user_profile(
        self,
        user_id: UUID
    ) -> Optional[CompleteUserProfile]:
        """완전한 사용자 프로필 조회"""
        pass
    
    @abstractmethod
    async def save_recommendation_history(
        self,
        recommendation: PersonalizedRecommendation
    ) -> Optional[int]:
        """추천 이력 저장"""
        pass
    
    @abstractmethod
    async def update_user_preferences(
        self,
        user_id: UUID,
        preferences: List[Dict[str, Any]]
    ) -> bool:
        """사용자 선호도 업데이트"""
        pass

# === 캐싱 인터페이스 ===

class ICacheManager(ABC):
    """캐시 관리 인터페이스"""
    
    @abstractmethod
    async def get_cached_analysis(
        self,
        cache_key: str
    ) -> Optional[Any]:
        """캐시된 분석 결과 조회"""
        pass
    
    @abstractmethod
    async def cache_analysis(
        self,
        cache_key: str,
        analysis_result: Any,
        ttl_seconds: int = 3600
    ) -> bool:
        """분석 결과 캐싱"""
        pass
    
    @abstractmethod
    async def invalidate_cache(
        self,
        pattern: str
    ) -> int:
        """캐시 무효화"""
        pass