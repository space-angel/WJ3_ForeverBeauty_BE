"""
의도 매칭 설정 관리
모든 하드코딩된 매핑 데이터를 중앙 집중 관리
"""
from typing import Dict, List, Any

class IntentConfig:
    """의도 매칭 설정"""
    
    # 영어-한국어 의도 태그 매핑
    INTENT_MAPPING = {
        'moisturizing': ['보습', '수분', '촉촉', '히알루론산', '글리세린'],
        'hydrating': ['수분', '보습', '히알루론산', '아쿠아', '워터'],
        'anti-aging': ['안티에이징', '주름', '탄력', '노화방지', '펩타이드', '콜라겐'],
        'cleansing': ['클렌징', '세정', '깨끗', '폼', '워시'],
        'brightening': ['미백', '브라이트닝', '화이트닝', '비타민C', '나이아신아마이드'],
        'acne-care': ['여드름', '트러블', '진정', '시카', '센텔라', 'AC', '약콩'],
        'sensitive-care': ['민감', '순한', '저자극', '베이비', '센시티브'],
        'soothing': ['진정', '수딩', '카밍', '알로에', '카모마일'],
        'firming': ['탄력', '리프팅', '퍼밍', '펩타이드'],
        'pore-care': ['모공', '포어', '블랙헤드', 'BHA', 'AHA']
    }
    
    # 카테고리-의도 적합성 매핑
    CATEGORY_INTENT_MAP = {
        'moisturizing': ['크림', '로션', '에센스', '세럼'],
        'anti-aging': ['크림', '세럼', '앰플', '아이크림'],
        'acne-care': ['세럼', '앰플', '토너', '클렌저'],
        'brightening': ['세럼', '앰플', '크림', '마스크'],
        'cleansing': ['클렌저', '폼', '워시'],
        'soothing': ['젤', '미스트', '마스크', '크림'],
        'pore-care': ['토너', '세럼', '마스크']
    }
    
    # 브랜드별 전문성 가중치
    BRAND_EXPERTISE = {
        '스킨1004': {'acne-care': 1.3, 'sensitive-care': 1.2},
        '라운드랩': {'acne-care': 1.2, 'sensitive-care': 1.1},
        '토리든': {'moisturizing': 1.2, 'anti-aging': 1.1},
        '웰라쥬': {'moisturizing': 1.3, 'soothing': 1.1},
        '이니스프리': {'brightening': 1.1, 'pore-care': 1.1}
    }
    
    # 매칭 점수 가중치
    MATCHING_WEIGHTS = {
        'tag_matching': 0.4,      # 태그 매칭 (40%)
        'name_matching': 0.3,     # 제품명 매칭 (30%)
        'category_matching': 0.15, # 카테고리 매칭 (15%)
        'semantic_matching': 0.15  # 의미적 매칭 (15%)
    }
    
    # 점수 임계값
    SCORE_THRESHOLDS = {
        'high_confidence': 80,
        'medium_confidence': 60,
        'low_confidence': 40,
        'minimum_score': 20
    }

class ScoringConfig:
    """점수 계산 설정"""
    
    # 기본 점수
    BASE_SCORES = {
        'tag_match': 25,
        'name_match': 20,
        'category_match': 10,
        'ingredient_match': 15,
        'brand_bonus': 5
    }
    
    # 가중치 배수
    WEIGHT_MULTIPLIERS = {
        'premium_brand': 1.2,
        'specialized_product': 1.3,
        'high_concentration': 1.4,
        'multi_benefit': 1.1
    }

class CategoryConfig:
    """카테고리 설정"""
    
    # 카테고리별 가중치
    CATEGORY_WEIGHTS = {
        '에센스/앰플/세럼': 1.2,
        '크림': 1.1,
        '로션/에멀젼': 1.0,
        '토너': 0.9,
        '마스크': 1.1,
        '클렌저': 0.8
    }
    
    # 지원 카테고리 목록
    SUPPORTED_CATEGORIES = [
        "클렌저", "토너", "에센스", "세럼", "모이스처라이저", 
        "크림", "아이크림", "선크림", "마스크팩", "오일",
        "미스트", "앰플", "젤", "로션", "밤", "스크럽"
    ]

class TagConfig:
    """태그 설정"""
    
    # 지원 의도 태그 목록
    SUPPORTED_INTENT_TAGS = [
        "moisturizing", "anti-aging", "cleansing", "brightening",
        "acne-care", "sensitive-care", "pore-care", "firming",
        "soothing", "exfoliating", "sun-protection", "oil-control",
        "hydrating", "nourishing", "repairing", "calming"
    ]
    
    # 태그 우선순위 (높을수록 중요)
    TAG_PRIORITY = {
        'moisturizing': 10,
        'anti-aging': 9,
        'acne-care': 8,
        'sensitive-care': 7,
        'brightening': 6,
        'pore-care': 5,
        'soothing': 4,
        'cleansing': 3,
        'firming': 2,
        'sun-protection': 1
    }