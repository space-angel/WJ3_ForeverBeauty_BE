"""
SQLite 데이터베이스 모델 정의
cosmetics.db의 테이블 구조를 반영한 데이터 모델
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import json

@dataclass
class Product:
    """제품 모델"""
    product_id: int
    name: str
    brand_name: str
    category_code: str
    category_name: str
    primary_attr: Optional[str] = None
    tags: List[str] = None
    image_url: Optional[str] = None
    sub_product_name: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """태그 JSON 파싱"""
        if isinstance(self.tags, str):
            try:
                self.tags = json.loads(self.tags)
            except (json.JSONDecodeError, TypeError):
                self.tags = []
        elif self.tags is None:
            self.tags = []

@dataclass
class Ingredient:
    """성분 모델"""
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
    purposes: List[str] = None
    tags: List[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """JSON 필드 파싱"""
        if isinstance(self.purposes, str):
            try:
                self.purposes = json.loads(self.purposes)
            except (json.JSONDecodeError, TypeError):
                self.purposes = []
        elif self.purposes is None:
            self.purposes = []
            
        if isinstance(self.tags, str):
            try:
                self.tags = json.loads(self.tags)
            except (json.JSONDecodeError, TypeError):
                self.tags = []
        elif self.tags is None:
            self.tags = []

@dataclass
class ProductIngredient:
    """제품-성분 관계 모델"""
    product_id: int
    ingredient_id: int
    ordinal: int

@dataclass
class ProductWithIngredients:
    """성분 정보를 포함한 제품 모델"""
    product: Product
    ingredients: List[Ingredient]
    
    @property
    def all_canonical_tags(self) -> List[str]:
        """모든 성분의 canonical tags 수집"""
        tags = []
        for ingredient in self.ingredients:
            if ingredient.tags:
                tags.extend(ingredient.tags)
        return list(set(tags))  # 중복 제거