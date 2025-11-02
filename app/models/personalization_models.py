"""
개인화 추천 엔진 핵심 데이터 모델
성분 분석, 프로필 매칭, 점수 계산 등의 결과를 담는 데이터 클래스들
"""

from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID
from enum import Enum

# === 열거형 정의 ===

class EffectType(Enum):
    """효과 유형"""
    BENEFICIAL = "beneficial"      # 유익한 효과
    HARMFUL = "harmful"           # 부작용
    NEUTRAL = "neutral"           # 중성

class SafetyLevel(Enum):
    """안전성 수준"""
    SAFE = "safe"                 # 안전
    CAUTION = "caution"          # 주의
    WARNING = "warning"          # 경고
    DANGER = "danger"            # 위험

class MatchLevel(Enum):
    """매칭 수준"""
    EXCELLENT = "excellent"      # 매우 적합 (90-100%)
    GOOD = "good"               # 적합 (70-89%)
    FAIR = "fair"               # 보통 (50-69%)
    POOR = "poor"               # 부적합 (0-49%)

# === 성분 분석 관련 모델 ===

@dataclass
class IngredientEffect:
    """개별 성분의 효과 분석 결과"""
    ingredient_id: int
    ingredient_name: str
    effect_type: EffectType
    effect_description: str
    confidence_score: float = 1.0  # 0.0-1.0
    safety_level: SafetyLevel = SafetyLevel.SAFE
    
    # 상세 정보
    ewg_grade: Optional[str] = None
    is_allergy_risk: bool = False
    is_age_restricted: bool = False
    skin_type_suitability: Dict[str, float] = field(default_factory=dict)  # 피부타입별 적합도
    
    @property
    def is_beneficial(self) -> bool:
        """유익한 효과인지 확인"""
        return self.effect_type == EffectType.BENEFICIAL
    
    @property
    def is_harmful(self) -> bool:
        """부작용인지 확인"""
        return self.effect_type == EffectType.HARMFUL
    
    @property
    def weighted_score(self) -> float:
        """가중치가 적용된 점수 (유익=양수, 부작용=음수)"""
        base_score = self.confidence_score * 100
        
        if self.effect_type == EffectType.BENEFICIAL:
            return base_score
        elif self.effect_type == EffectType.HARMFUL:
            return -base_score
        else:
            return 0.0

@dataclass
class ProductIngredientAnalysis:
    """제품의 전체 성분 분석 결과"""
    product_id: int
    product_name: str
    total_ingredients: int
    analyzed_ingredients: int
    
    # 성분 효과 분석
    beneficial_effects: List[IngredientEffect] = field(default_factory=list)
    harmful_effects: List[IngredientEffect] = field(default_factory=list)
    neutral_effects: List[IngredientEffect] = field(default_factory=list)
    
    # 안전성 분석
    safety_warnings: List[str] = field(default_factory=list)
    allergy_risks: List[str] = field(default_factory=list)
    age_restrictions: List[str] = field(default_factory=list)
    
    # 분석 메타데이터
    analysis_timestamp: datetime = field(default_factory=datetime.now)
    analysis_version: str = "1.0"
    
    @property
    def overall_safety_level(self) -> SafetyLevel:
        """전체 안전성 수준"""
        if self.safety_warnings or self.allergy_risks:
            if len(self.safety_warnings) >= 3 or any("위험" in w for w in self.safety_warnings):
                return SafetyLevel.DANGER
            elif len(self.safety_warnings) >= 2:
                return SafetyLevel.WARNING
            else:
                return SafetyLevel.CAUTION
        return SafetyLevel.SAFE
    
    @property
    def beneficial_score(self) -> float:
        """유익한 효과 총점"""
        return sum(effect.weighted_score for effect in self.beneficial_effects)
    
    @property
    def harmful_score(self) -> float:
        """부작용 총점 (음수)"""
        return sum(effect.weighted_score for effect in self.harmful_effects)
    
    @property
    def net_effect_score(self) -> float:
        """순 효과 점수 (유익 - 부작용)"""
        return self.beneficial_score + self.harmful_score  # harmful_score는 이미 음수
    
    @property
    def analysis_coverage(self) -> float:
        """분석 커버리지 (%)"""
        if self.total_ingredients == 0:
            return 0.0
        return (self.analyzed_ingredients / self.total_ingredients) * 100

# === 사용자 프로필 매칭 관련 모델 ===

@dataclass
class ProfileMatchResult:
    """사용자 프로필과 제품의 매칭 결과"""
    user_id: Optional[UUID]
    product_id: int
    
    # 매칭 점수 (0-100)
    age_match_score: float = 0.0
    skin_type_match_score: float = 0.0
    preference_match_score: float = 0.0
    overall_match_score: float = 0.0
    
    # 매칭 수준
    age_match_level: MatchLevel = MatchLevel.FAIR
    skin_type_match_level: MatchLevel = MatchLevel.FAIR
    preference_match_level: MatchLevel = MatchLevel.FAIR
    overall_match_level: MatchLevel = MatchLevel.FAIR
    
    # 매칭 근거
    match_reasons: List[str] = field(default_factory=list)
    mismatch_reasons: List[str] = field(default_factory=list)
    
    # 가중치 (합계 100%)
    age_weight: float = 50.0
    skin_type_weight: float = 30.0
    preference_weight: float = 20.0
    
    def calculate_overall_score(self) -> float:
        """전체 매칭 점수 계산"""
        total_weight = self.age_weight + self.skin_type_weight + self.preference_weight
        
        if total_weight == 0:
            return 0.0
        
        weighted_score = (
            (self.age_match_score * self.age_weight) +
            (self.skin_type_match_score * self.skin_type_weight) +
            (self.preference_match_score * self.preference_weight)
        ) / total_weight
        
        self.overall_match_score = weighted_score
        self.overall_match_level = self._score_to_match_level(weighted_score)
        
        return weighted_score
    
    def _score_to_match_level(self, score: float) -> MatchLevel:
        """점수를 매칭 수준으로 변환"""
        if score >= 90:
            return MatchLevel.EXCELLENT
        elif score >= 70:
            return MatchLevel.GOOD
        elif score >= 50:
            return MatchLevel.FAIR
        else:
            return MatchLevel.POOR

# === 점수 계산 관련 모델 ===

@dataclass
class ScoreBreakdown:
    """점수 상세 분석"""
    intent_score: float = 0.0          # 의도 매칭 점수
    personalization_score: float = 0.0  # 개인화 점수
    safety_score: float = 0.0          # 안전성 점수
    
    # 가중치
    intent_weight: float = 30.0
    personalization_weight: float = 40.0
    safety_weight: float = 30.0
    
    # 상세 점수
    ingredient_effect_score: float = 0.0
    profile_match_score: float = 0.0
    preference_bonus: float = 0.0
    safety_penalty: float = 0.0
    
    @property
    def final_score(self) -> float:
        """최종 점수 계산"""
        total_weight = self.intent_weight + self.personalization_weight + self.safety_weight
        
        if total_weight == 0:
            return 0.0
        
        return (
            (self.intent_score * self.intent_weight) +
            (self.personalization_score * self.personalization_weight) +
            (self.safety_score * self.safety_weight)
        ) / total_weight

@dataclass
class ProductScore:
    """제품의 종합 점수 및 분석 결과"""
    product_id: int
    product_name: str
    brand_name: str
    
    # 종합 점수
    final_score: float = 0.0
    normalized_score: float = 0.0  # 0-100 정규화
    
    # 점수 상세 분석
    score_breakdown: ScoreBreakdown = field(default_factory=ScoreBreakdown)
    
    # 분석 결과
    ingredient_analysis: Optional[ProductIngredientAnalysis] = None
    profile_match: Optional[ProfileMatchResult] = None
    
    # 추천 근거
    recommendation_reasons: List[str] = field(default_factory=list)
    caution_notes: List[str] = field(default_factory=list)
    
    # 메타데이터
    calculation_timestamp: datetime = field(default_factory=datetime.now)
    calculation_version: str = "1.0"
    
    @property
    def is_recommended(self) -> bool:
        """추천 가능한 제품인지 확인"""
        return (
            self.final_score >= 50.0 and
            (not self.ingredient_analysis or 
             self.ingredient_analysis.overall_safety_level in [SafetyLevel.SAFE, SafetyLevel.CAUTION])
        )
    
    @property
    def recommendation_confidence(self) -> float:
        """추천 신뢰도 (0-1)"""
        confidence_factors = []
        
        # 점수 기반 신뢰도
        confidence_factors.append(min(self.final_score / 100.0, 1.0))
        
        # 분석 커버리지 기반 신뢰도
        if self.ingredient_analysis:
            coverage = self.ingredient_analysis.analysis_coverage / 100.0
            confidence_factors.append(coverage)
        
        # 프로필 매칭 기반 신뢰도
        if self.profile_match:
            match_confidence = self.profile_match.overall_match_score / 100.0
            confidence_factors.append(match_confidence)
        
        return sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.0

# === 추천 결과 관련 모델 ===

@dataclass
class PersonalizedRecommendation:
    """개인화된 추천 결과"""
    user_id: Optional[UUID]
    session_id: Optional[str]
    
    # 요청 정보
    intent_tags: List[str] = field(default_factory=list)
    user_profile_summary: Dict[str, Any] = field(default_factory=dict)
    
    # 추천 결과
    recommended_products: List[ProductScore] = field(default_factory=list)
    total_candidates: int = 0
    filtered_count: int = 0
    
    # 실행 정보
    execution_time_ms: float = 0.0
    algorithm_version: str = "1.0"
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 전체 분석
    overall_insights: List[str] = field(default_factory=list)
    personalization_notes: List[str] = field(default_factory=list)
    
    @property
    def top_recommendation(self) -> Optional[ProductScore]:
        """최고 추천 제품"""
        return self.recommended_products[0] if self.recommended_products else None
    
    @property
    def average_score(self) -> float:
        """평균 추천 점수"""
        if not self.recommended_products:
            return 0.0
        return sum(p.final_score for p in self.recommended_products) / len(self.recommended_products)
    
    @property
    def recommendation_quality(self) -> str:
        """추천 품질 평가"""
        if not self.recommended_products:
            return "no_recommendations"
        
        avg_score = self.average_score
        if avg_score >= 80:
            return "excellent"
        elif avg_score >= 65:
            return "good"
        elif avg_score >= 50:
            return "fair"
        else:
            return "poor"

# === 예외 클래스 ===

class PersonalizationEngineError(Exception):
    """개인화 엔진 기본 예외"""
    pass

class IngredientAnalysisError(PersonalizationEngineError):
    """성분 분석 오류"""
    pass

class ProfileMatchingError(PersonalizationEngineError):
    """프로필 매칭 오류"""
    pass

class ScoreCalculationError(PersonalizationEngineError):
    """점수 계산 오류"""
    pass

# === 유틸리티 함수 ===

def create_empty_product_score(product_id: int, product_name: str, brand_name: str) -> ProductScore:
    """빈 ProductScore 객체 생성"""
    return ProductScore(
        product_id=product_id,
        product_name=product_name,
        brand_name=brand_name,
        final_score=0.0,
        score_breakdown=ScoreBreakdown()
    )

def merge_ingredient_effects(effects: List[IngredientEffect]) -> Dict[EffectType, List[IngredientEffect]]:
    """성분 효과를 타입별로 그룹화"""
    grouped = {
        EffectType.BENEFICIAL: [],
        EffectType.HARMFUL: [],
        EffectType.NEUTRAL: []
    }
    
    for effect in effects:
        grouped[effect.effect_type].append(effect)
    
    return grouped

def calculate_safety_score(analysis: ProductIngredientAnalysis) -> float:
    """성분 분석 결과를 바탕으로 안전성 점수 계산"""
    base_score = 100.0
    
    # 안전성 경고에 따른 감점
    warning_penalty = len(analysis.safety_warnings) * 10
    allergy_penalty = len(analysis.allergy_risks) * 15
    age_penalty = len(analysis.age_restrictions) * 5
    
    # 부작용 효과에 따른 감점
    harmful_penalty = sum(abs(effect.weighted_score) for effect in analysis.harmful_effects) * 0.1
    
    final_score = base_score - warning_penalty - allergy_penalty - age_penalty - harmful_penalty
    
    return max(0.0, min(100.0, final_score))