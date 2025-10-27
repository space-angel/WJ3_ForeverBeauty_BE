"""
요청 모델 정의
"""
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from enum import Enum

class GenderType(str, Enum):
    """성별 타입"""
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

class SkinType(str, Enum):
    """피부 타입"""
    DRY = "dry"
    OILY = "oily"
    COMBINATION = "combination"
    SENSITIVE = "sensitive"
    NORMAL = "normal"

class AgeGroup(str, Enum):
    """연령대"""
    TEENS = "10s"
    TWENTIES = "20s"
    THIRTIES = "30s"
    FORTIES = "40s"
    FIFTIES = "50s"
    SIXTIES_PLUS = "60s+"

class UsageContext(BaseModel):
    """사용 맥락"""
    season: Optional[str] = Field(None, description="계절 (spring, summer, autumn, winter)")
    time_of_day: Optional[str] = Field(None, description="사용 시간 (morning, afternoon, evening, night)")
    occasion: Optional[str] = Field(None, description="사용 상황 (daily, special, work, date)")
    climate: Optional[str] = Field(None, description="기후 (humid, dry, hot, cold)")

class UserProfile(BaseModel):
    """사용자 프로필"""
    age_group: Optional[AgeGroup] = Field(None, description="연령대")
    gender: Optional[GenderType] = Field(None, description="성별")
    skin_type: Optional[SkinType] = Field(None, description="피부 타입")
    skin_concerns: Optional[List[str]] = Field(default_factory=list, description="피부 고민 (acne, wrinkles, dryness, etc.)")
    allergies: Optional[List[str]] = Field(default_factory=list, description="알레르기 성분")

class MedicationInfo(BaseModel):
    """의약품 정보"""
    name: str = Field(..., description="의약품명")
    active_ingredients: Optional[List[str]] = Field(default_factory=list, description="주성분")
    usage_frequency: Optional[str] = Field(None, description="복용 빈도")
    dosage: Optional[str] = Field(None, description="용량")

class RecommendationRequest(BaseModel):
    """추천 요청"""
    intent_tags: List[str] = Field(..., min_items=1, description="의도 태그 (moisturizing, anti-aging, cleansing, etc.)")
    user_profile: Optional[UserProfile] = Field(None, description="사용자 프로필")
    medications: Optional[List[MedicationInfo]] = Field(default_factory=list, description="복용 중인 의약품")
    usage_context: Optional[UsageContext] = Field(None, description="사용 맥락")
    price_range: Optional[Dict[str, float]] = Field(None, description="가격 범위 {'min': 10000, 'max': 50000}")
    categories: Optional[List[str]] = Field(default_factory=list, description="원하는 카테고리")
    brands: Optional[List[str]] = Field(default_factory=list, description="선호 브랜드")
    exclude_ingredients: Optional[List[str]] = Field(default_factory=list, description="제외할 성분")
    top_n: int = Field(5, ge=1, le=20, description="추천 개수 (1-20)")
    include_reasoning: bool = Field(True, description="추천 근거 포함 여부")
    
    # 추가 속성 (기존 서비스와의 호환성)
    category_like: Optional[str] = Field(None, description="카테고리 필터 (호환성용)")
    
    @property
    def price(self) -> Optional[Dict[str, float]]:
        """가격 범위를 price 속성으로 접근"""
        return self.price_range
    
    @validator('intent_tags')
    def validate_intent_tags(cls, v):
        if not v:
            raise ValueError('최소 하나의 의도 태그가 필요합니다')
        return v
    
    @validator('top_n')
    def validate_top_n(cls, v):
        if v < 1 or v > 20:
            raise ValueError('추천 개수는 1-20 사이여야 합니다')
        return v

class PriceRange(BaseModel):
    """가격 범위"""
    min_price: Optional[float] = Field(None, description="최소 가격")
    max_price: Optional[float] = Field(None, description="최대 가격")

class HealthCheckRequest(BaseModel):
    """헬스체크 요청"""
    include_detailed_stats: bool = Field(False, description="상세 통계 포함 여부")
    check_database_connections: bool = Field(True, description="데이터베이스 연결 확인 여부")