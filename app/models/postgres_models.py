"""
PostgreSQL 데이터베이스 모델 정의
UUID 기반 사용자 모델 및 JSONB 최적화 모델
"""

from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID
import json

@dataclass
class Product:
    """제품 모델 (PostgreSQL 최적화)"""
    product_id: int
    name: str
    brand_name: str
    category_code: str
    category_name: str
    primary_attr: Optional[str] = None
    tags: List[str] = field(default_factory=list)  # JSONB 필드
    image_url: Optional[str] = None
    sub_product_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Product':
        """데이터베이스 행에서 Product 객체 생성"""
        # 태그 파싱 처리
        raw_tags = row.get('tags', [])
        if isinstance(raw_tags, str):
            try:
                # JSON 문자열인 경우 파싱
                parsed_tags = json.loads(raw_tags)
                if isinstance(parsed_tags, list):
                    tags = [str(tag).strip() for tag in parsed_tags if tag]
                else:
                    tags = []
            except json.JSONDecodeError:
                # JSON이 아닌 경우 빈 리스트
                tags = []
        elif isinstance(raw_tags, list):
            # 이미 리스트인 경우
            tags = [str(tag).strip() for tag in raw_tags if tag]
        else:
            tags = []
        
        return cls(
            product_id=row['product_id'],
            name=row['name'],
            brand_name=row['brand_name'],
            category_code=row['category_code'],
            category_name=row['category_name'],
            primary_attr=row.get('primary_attr'),
            tags=tags,  # 파싱된 태그 사용
            image_url=row.get('image_url'),
            sub_product_name=row.get('sub_product_name'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )

@dataclass
class Ingredient:
    """성분 모델 (PostgreSQL 최적화)"""
    ingredient_id: int
    korean: str
    english: Optional[str] = None
    ewg_grade: Optional[str] = None
    is_allergy: bool = False
    is_twenty: bool = False
    skin_type_code: Optional[str] = None
    skin_good: Optional[str] = None
    skin_bad: Optional[str] = None
    limitation: Optional[str] = None
    forbidden: Optional[str] = None
    purposes: List[Dict[str, Any]] = field(default_factory=list)  # JSONB 필드
    tags: List[str] = field(default_factory=list)  # JSONB 필드
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Ingredient':
        """데이터베이스 행에서 Ingredient 객체 생성"""
        return cls(
            ingredient_id=row['ingredient_id'],
            korean=row['korean'],
            english=row.get('english'),
            ewg_grade=row.get('ewg_grade'),
            is_allergy=bool(row.get('is_allergy', False)),
            is_twenty=bool(row.get('is_twenty', False)),
            skin_type_code=row.get('skin_type_code'),
            skin_good=row.get('skin_good'),
            skin_bad=row.get('skin_bad'),
            limitation=row.get('limitation'),
            forbidden=row.get('forbidden'),
            purposes=row.get('purposes', []),  # JSONB는 자동으로 파싱됨
            tags=row.get('tags', []),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )

@dataclass
class ProductIngredient:
    """제품-성분 관계 모델"""
    product_id: int
    ingredient_id: int
    ordinal: int
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'ProductIngredient':
        return cls(
            product_id=row['product_id'],
            ingredient_id=row['ingredient_id'],
            ordinal=row['ordinal']
        )

@dataclass
class User:
    """사용자 기본 정보 (UUID 기반)"""
    user_id: UUID
    email: Optional[str] = None
    name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'User':
        return cls(
            user_id=row['user_id'],
            email=row.get('email'),
            name=row.get('name'),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )

@dataclass
class UserProfile:
    """사용자 개인화 프로필"""
    user_id: UUID
    age_group: Optional[str] = None  # '10s', '20s', '30s', '40s', '50s'
    skin_type: Optional[str] = None  # 'dry', 'oily', 'sensitive', 'combination'
    gender: Optional[str] = None     # 'male', 'female', 'other'
    skin_concerns: List[str] = field(default_factory=list)  # JSONB 필드
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'UserProfile':
        return cls(
            user_id=row['user_id'],
            age_group=row.get('age_group'),
            skin_type=row.get('skin_type'),
            gender=row.get('gender'),
            skin_concerns=row.get('skin_concerns', []),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )

@dataclass
class UserPreference:
    """사용자 선호도"""
    user_id: UUID
    preference_type: str  # 'brand', 'ingredient', 'category'
    preference_value: str
    is_preferred: bool = True
    confidence_score: float = 1.0
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'UserPreference':
        return cls(
            user_id=row['user_id'],
            preference_type=row['preference_type'],
            preference_value=row['preference_value'],
            is_preferred=bool(row.get('is_preferred', True)),
            confidence_score=float(row.get('confidence_score', 1.0)),
            created_at=row.get('created_at')
        )

@dataclass
class RecommendationHistory:
    """추천 이력"""
    id: int
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None
    intent_tags: List[str] = field(default_factory=list)  # JSONB 필드
    recommended_products: List[Dict[str, Any]] = field(default_factory=list)  # JSONB 필드
    execution_time_ms: Optional[float] = None
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'RecommendationHistory':
        return cls(
            id=row['id'],
            user_id=row.get('user_id'),
            session_id=row.get('session_id'),
            intent_tags=row.get('intent_tags', []),
            recommended_products=row.get('recommended_products', []),
            execution_time_ms=row.get('execution_time_ms'),
            created_at=row.get('created_at')
        )

@dataclass
class UserFeedback:
    """사용자 피드백"""
    id: int
    user_id: UUID
    product_id: int
    feedback_type: str  # 'like', 'dislike', 'purchase', 'view'
    rating: Optional[int] = None  # 1-5
    created_at: Optional[datetime] = None
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'UserFeedback':
        return cls(
            id=row['id'],
            user_id=row['user_id'],
            product_id=row['product_id'],
            feedback_type=row['feedback_type'],
            rating=row.get('rating'),
            created_at=row.get('created_at')
        )

@dataclass
class CompleteUserProfile:
    """사용자 완전 프로필 (조인된 데이터)"""
    user: User
    profile: Optional[UserProfile] = None
    preferences: List[UserPreference] = field(default_factory=list)
    
    @property
    def preferred_brands(self) -> List[str]:
        """선호 브랜드 목록"""
        return [
            pref.preference_value for pref in self.preferences
            if pref.preference_type == 'brand' and pref.is_preferred
        ]
    
    @property
    def avoided_ingredients(self) -> List[str]:
        """기피 성분 목록"""
        return [
            pref.preference_value for pref in self.preferences
            if pref.preference_type == 'ingredient' and not pref.is_preferred
        ]
    
    @property
    def preferred_categories(self) -> List[str]:
        """선호 카테고리 목록"""
        return [
            pref.preference_value for pref in self.preferences
            if pref.preference_type == 'category' and pref.is_preferred
        ]

@dataclass
class ProductWithIngredients:
    """성분 정보를 포함한 제품 모델 (PostgreSQL 최적화)"""
    product: Product
    ingredients: List[Ingredient] = field(default_factory=list)
    
    @property
    def key_ingredients(self) -> List[Ingredient]:
        """주요 성분 (상위 5개)"""
        return self.ingredients[:5]
    
    @property
    def all_beneficial_effects(self) -> List[str]:
        """모든 유익한 효과 수집"""
        effects = []
        for ingredient in self.ingredients:
            if ingredient.skin_good:
                # skin_good 필드를 파싱하여 효과 추출
                effects.extend(self._parse_effects(ingredient.skin_good))
        return list(set(effects))  # 중복 제거
    
    @property
    def all_harmful_effects(self) -> List[str]:
        """모든 부작용 수집"""
        effects = []
        for ingredient in self.ingredients:
            if ingredient.skin_bad:
                effects.extend(self._parse_effects(ingredient.skin_bad))
        return list(set(effects))
    
    @property
    def safety_score(self) -> float:
        """안전성 점수 (EWG 등급 기반)"""
        if not self.ingredients:
            return 50.0
        
        total_score = 0
        count = 0
        
        for ingredient in self.ingredients:
            if ingredient.ewg_grade and ingredient.ewg_grade != 'unknown':
                # EWG 등급을 점수로 변환 (1=100점, 10=0점)
                try:
                    grade = float(ingredient.ewg_grade.replace('_', '.'))
                    score = max(0, 100 - (grade - 1) * 11.11)  # 1-10 → 100-0
                    total_score += score
                    count += 1
                except ValueError:
                    continue
        
        return total_score / count if count > 0 else 50.0
    
    def _parse_effects(self, effects_text: str) -> List[str]:
        """효과 텍스트를 파싱하여 개별 효과 추출"""
        if not effects_text:
            return []
        
        # 쉼표, 세미콜론, 줄바꿈으로 분리
        effects = []
        for separator in [',', ';', '\n']:
            effects_text = effects_text.replace(separator, '|')
        
        parsed_effects = [
            effect.strip() 
            for effect in effects_text.split('|') 
            if effect.strip()
        ]
        
        return parsed_effects

@dataclass
class Rule:
    """룰 모델 (PostgreSQL)"""
    rule_id: str
    rule_type: str  # 'eligibility' or 'scoring'
    medication_codes: List[str] = field(default_factory=list)  # JSONB 필드
    ingredient_tag: Optional[str] = None
    conditions: Dict[str, Any] = field(default_factory=dict)  # JSONB 필드
    action: str = 'exclude'  # 'exclude' or 'penalty'
    penalty_score: Optional[float] = None
    reason: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @classmethod
    def from_db_row(cls, row: Dict[str, Any]) -> 'Rule':
        """데이터베이스 행에서 Rule 객체 생성"""
        return cls(
            rule_id=row['rule_id'],
            rule_type=row['rule_type'],
            medication_codes=row.get('medication_codes', []),
            ingredient_tag=row.get('ingredient_tag'),
            conditions=row.get('conditions', {}),
            action=row.get('action', 'exclude'),
            penalty_score=row.get('penalty_score'),
            reason=row.get('reason'),
            is_active=bool(row.get('is_active', True)),
            created_at=row.get('created_at'),
            updated_at=row.get('updated_at')
        )

# 데이터베이스 헬스체크 모델
@dataclass
class DatabaseHealth:
    """데이터베이스 헬스체크 결과"""
    status: str
    database: str
    host: str
    port: int
    version: Optional[str] = None
    current_time: Optional[datetime] = None
    response_time_ms: Optional[float] = None
    pool_info: Optional[Dict[str, int]] = None
    error: Optional[str] = None