"""
고도화된 제품명 매칭 서비스
NLP 기반 형태소 분석, 동의어 확장, 패턴 매칭
"""
from typing import List, Dict, Set, Tuple, Optional
import re
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class NameMatchResult:
    """제품명 매칭 결과"""
    match_score: float
    matched_keywords: List[str]
    matched_patterns: List[str]
    semantic_matches: List[str]
    confidence: float
    match_details: Dict[str, float]

class EnhancedNameMatcher:
    """고도화된 제품명 매칭 엔진"""
    
    def __init__(self):
        """초기화"""
        
        # 1. 화장품 도메인 특화 패턴 사전
        self.cosmetic_patterns = {
            # 보습 관련 패턴
            'moisturizing': {
                'direct': ['보습', '수분', '촉촉', '모이스처', '히드라'],
                'compound': ['수분크림', '보습에센스', '히드라젤', '아쿠아세럼'],
                'ingredients': ['히알루론산', '글리세린', '세라마이드', '스쿠알란'],
                'effects': ['건조완화', '수분공급', '수분충전', '촉촉함'],
                'regex_patterns': [
                    r'(?:수분|보습|히드라|아쿠아|워터)(?:크림|로션|에센스|세럼|젤|마스크)',
                    r'히알루론산?\s*(?:크림|세럼|앰플)',
                    r'(?:모이스처|moisture)(?:라이저|라이징|크림)'
                ]
            },
            
            # 안티에이징 관련 패턴
            'anti-aging': {
                'direct': ['안티에이징', '주름', '탄력', '리프팅', '퍼밍'],
                'compound': ['주름크림', '탄력세럼', '리프팅마스크', '안티링클'],
                'ingredients': ['펩타이드', '콜라겐', '레티놀', '아데노신'],
                'effects': ['주름개선', '탄력증진', '노화방지', '리프팅효과'],
                'regex_patterns': [
                    r'(?:주름|링클|wrinkle)(?:케어|크림|세럼)',
                    r'(?:탄력|리프팅|퍼밍|firming)(?:크림|세럼|마스크)',
                    r'(?:펩타이드|콜라겐|peptide|collagen)(?:크림|세럼|앰플)',
                    r'안티(?:에이징|aging|링클)'
                ]
            },
            
            # 여드름 케어 관련 패턴
            'acne-care': {
                'direct': ['여드름', '트러블', '아크네', 'AC', '시카'],
                'compound': ['여드름크림', '트러블케어', 'AC케어', '시카크림'],
                'ingredients': ['시카', '센텔라', '살리실산', '티트리', '약콩'],
                'effects': ['트러블진정', '여드름완화', '피지조절', '염증완화'],
                'regex_patterns': [
                    r'(?:여드름|트러블|아크네|acne)(?:케어|크림|세럼|젤)',
                    r'(?:시카|센텔라|cica|centella)(?:크림|세럼|앰플|젤)',
                    r'AC(?:케어|크림|세럼)',
                    r'(?:약콩|티트리|tea\s*tree)(?:크림|세럼|토너)'
                ]
            },
            
            # 미백 관련 패턴
            'brightening': {
                'direct': ['미백', '브라이트닝', '화이트닝', '톤업'],
                'compound': ['미백크림', '브라이트닝세럼', '화이트닝마스크'],
                'ingredients': ['비타민C', '나이아신아마이드', '알부틴', '코직산'],
                'effects': ['잡티개선', '색소완화', '톤업효과', '광채'],
                'regex_patterns': [
                    r'(?:미백|화이트닝|whitening)(?:크림|세럼|마스크)',
                    r'(?:브라이트닝|brightening)(?:세럼|앰플|크림)',
                    r'(?:비타민c|vitamin\s*c)(?:세럼|앰플|크림)',
                    r'(?:톤업|tone\s*up)(?:크림|베이스)'
                ]
            },
            
            # 민감성 케어 관련 패턴
            'sensitive-care': {
                'direct': ['민감', '순한', '저자극', '베이비', '센시티브'],
                'compound': ['민감크림', '순한세럼', '저자극토너'],
                'ingredients': ['알로에', '카모마일', '센텔라', '판테놀'],
                'effects': ['진정', '자극완화', '편안함', '보호'],
                'regex_patterns': [
                    r'(?:민감|sensitive)(?:크림|로션|세럼)',
                    r'(?:순한|마일드|mild)(?:클렌저|크림|로션)',
                    r'(?:저자극|gentle)(?:크림|세럼|토너)',
                    r'(?:베이비|baby)(?:크림|로션|오일)'
                ]
            },
            
            # 모공 케어 관련 패턴
            'pore-care': {
                'direct': ['모공', '포어', '블랙헤드', '각질'],
                'compound': ['모공케어', '포어토너', '각질제거'],
                'ingredients': ['BHA', 'AHA', '살리실산', '글리콜산'],
                'effects': ['모공축소', '각질제거', '피지조절', '깔끔함'],
                'regex_patterns': [
                    r'(?:모공|포어|pore)(?:케어|토너|세럼)',
                    r'(?:각질|필링|peeling)(?:제거|케어|젤)',
                    r'(?:BHA|AHA|살리실산)(?:토너|세럼|크림)',
                    r'(?:블랙헤드|blackhead)(?:제거|케어)'
                ]
            }
        }
        
        # 2. 브랜드별 특화 키워드
        self.brand_keywords = {
            '스킨1004': ['마다가스카르', '센텔라', '시카', '진정'],
            '라운드랩': ['자작나무', '독도', '1025', '약콩'],
            '토리든': ['다이브인', '저분자', '콜라겐', '히알루론산'],
            '웰라쥬': ['하이퍼', '펩타이드', '콜라겐', '부스터'],
            '이니스프리': ['제주', '그린티', '비자', '올리브'],
            '에뛰드하우스': ['순정', '원더', '미라클', '픽스'],
            '더페이스샵': ['라이스', '쌀', '허니', '올리브']
        }
        
        # 3. 제품 타입별 키워드 가중치
        self.product_type_weights = {
            '에센스': 1.3, '세럼': 1.4, '앰플': 1.5,
            '크림': 1.2, '로션': 1.0, '토너': 0.9,
            '마스크': 1.3, '젤': 1.1, '오일': 1.0
        }
        
        # 4. 성분 중요도 가중치
        self.ingredient_importance = {
            '히알루론산': 1.5, '펩타이드': 1.4, '콜라겐': 1.3,
            '비타민C': 1.4, '레티놀': 1.5, '나이아신아마이드': 1.3,
            '시카': 1.4, '센텔라': 1.4, '살리실산': 1.3,
            'BHA': 1.3, 'AHA': 1.3, '알로에': 1.1
        }
        
        logger.info("EnhancedNameMatcher 초기화 완료")
    
    def calculate_name_match_score(
        self, 
        product_name: str, 
        intent_tags: List[str],
        brand_name: str = None,
        category: str = None
    ) -> NameMatchResult:
        """고도화된 제품명 매칭 점수 계산"""
        
        if not product_name or not intent_tags:
            return NameMatchResult(0.0, [], [], [], 0.0, {})
        
        # 1. 제품명 전처리
        normalized_name = self._normalize_product_name(product_name)
        
        # 2. 다층 매칭 수행
        direct_matches = self._find_direct_matches(normalized_name, intent_tags)
        pattern_matches = self._find_pattern_matches(normalized_name, intent_tags)
        semantic_matches = self._find_semantic_matches(normalized_name, intent_tags)
        ingredient_matches = self._find_ingredient_matches(normalized_name, intent_tags)
        brand_matches = self._find_brand_specific_matches(normalized_name, brand_name, intent_tags)
        
        # 3. 점수 계산 (가중 평균)
        match_details = {
            'direct_score': direct_matches['score'],
            'pattern_score': pattern_matches['score'],
            'semantic_score': semantic_matches['score'],
            'ingredient_score': ingredient_matches['score'],
            'brand_score': brand_matches['score']
        }
        
        # 가중치 적용
        total_score = (
            direct_matches['score'] * 0.3 +      # 직접 매칭 (30%)
            pattern_matches['score'] * 0.25 +    # 패턴 매칭 (25%)
            semantic_matches['score'] * 0.2 +    # 의미적 매칭 (20%)
            ingredient_matches['score'] * 0.15 + # 성분 매칭 (15%)
            brand_matches['score'] * 0.1         # 브랜드 매칭 (10%)
        )
        
        # 4. 제품 타입 가중치 적용
        type_weight = self._get_product_type_weight(category)
        final_score = total_score * type_weight
        
        # 5. 매칭된 키워드 통합
        all_matched_keywords = (
            direct_matches['keywords'] + 
            pattern_matches['keywords'] + 
            ingredient_matches['keywords'] +
            brand_matches['keywords']
        )
        
        # 6. 신뢰도 계산
        confidence = self._calculate_name_confidence(match_details, len(all_matched_keywords))
        
        return NameMatchResult(
            match_score=min(final_score, 100.0),
            matched_keywords=list(set(all_matched_keywords)),
            matched_patterns=pattern_matches['patterns'],
            semantic_matches=semantic_matches['matches'],
            confidence=confidence,
            match_details=match_details
        )
    
    def _normalize_product_name(self, name: str) -> str:
        """제품명 정규화"""
        if not name:
            return ""
        
        # 1. 기본 정규화
        normalized = name.lower().strip()
        
        # 2. 특수 문자 및 괄호 내용 제거
        normalized = re.sub(r'\[.*?\]', '', normalized)  # [SPF50+/PA++++] 제거
        normalized = re.sub(r'\(.*?\)', '', normalized)  # (용량) 제거
        normalized = re.sub(r'[^\w\s가-힣]', ' ', normalized)  # 특수문자 제거
        
        # 3. 용량 정보 제거
        normalized = re.sub(r'\d+(?:ml|g|oz|개입)', '', normalized)
        
        # 4. 연속 공백 제거
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _find_direct_matches(self, name: str, intent_tags: List[str]) -> Dict:
        """직접 키워드 매칭"""
        score = 0.0
        matched_keywords = []
        
        for intent_tag in intent_tags:
            if intent_tag in self.cosmetic_patterns:
                pattern_config = self.cosmetic_patterns[intent_tag]
                
                # Direct 키워드 매칭
                for keyword in pattern_config['direct']:
                    if keyword in name:
                        score += 25.0
                        matched_keywords.append(keyword)
                
                # Compound 키워드 매칭 (더 높은 점수)
                for compound in pattern_config['compound']:
                    if compound in name:
                        score += 35.0
                        matched_keywords.append(compound)
        
        return {'score': min(score, 100.0), 'keywords': matched_keywords}
    
    def _find_pattern_matches(self, name: str, intent_tags: List[str]) -> Dict:
        """정규식 패턴 매칭"""
        score = 0.0
        matched_patterns = []
        matched_keywords = []
        
        for intent_tag in intent_tags:
            if intent_tag in self.cosmetic_patterns:
                pattern_config = self.cosmetic_patterns[intent_tag]
                
                for pattern in pattern_config.get('regex_patterns', []):
                    matches = re.findall(pattern, name)
                    if matches:
                        # 패턴 복잡도에 따른 점수 (긴 패턴일수록 높은 점수)
                        pattern_score = min(len(pattern) / 10, 3.0) * 15
                        score += pattern_score
                        matched_patterns.append(pattern)
                        matched_keywords.extend(matches if isinstance(matches[0], str) else [m for match in matches for m in match])
        
        return {
            'score': min(score, 100.0), 
            'keywords': matched_keywords,
            'patterns': matched_patterns
        }
    
    def _find_semantic_matches(self, name: str, intent_tags: List[str]) -> Dict:
        """의미적 매칭 (동의어, 유사어)"""
        score = 0.0
        semantic_matches = []
        
        # 간단한 동의어 매칭 (향후 Word2Vec 등으로 확장 가능)
        semantic_map = {
            'moisturizing': ['수분감', '촉촉함', '부드러움', '윤기'],
            'anti-aging': ['젊음', '생기', '활력', '재생'],
            'acne-care': ['깔끔함', '맑음', '순수', '클리어'],
            'brightening': ['광채', '투명감', '화사함', '맑음'],
            'sensitive-care': ['편안함', '안전함', '부드러움', '온화함']
        }
        
        for intent_tag in intent_tags:
            if intent_tag in semantic_map:
                for semantic_word in semantic_map[intent_tag]:
                    if semantic_word in name:
                        score += 15.0
                        semantic_matches.append(semantic_word)
        
        return {'score': min(score, 100.0), 'matches': semantic_matches}
    
    def _find_ingredient_matches(self, name: str, intent_tags: List[str]) -> Dict:
        """성분 기반 매칭"""
        score = 0.0
        matched_keywords = []
        
        for intent_tag in intent_tags:
            if intent_tag in self.cosmetic_patterns:
                pattern_config = self.cosmetic_patterns[intent_tag]
                
                for ingredient in pattern_config.get('ingredients', []):
                    if ingredient in name:
                        # 성분 중요도에 따른 가중치 적용
                        importance_weight = self.ingredient_importance.get(ingredient, 1.0)
                        ingredient_score = 20.0 * importance_weight
                        score += ingredient_score
                        matched_keywords.append(ingredient)
        
        return {'score': min(score, 100.0), 'keywords': matched_keywords}
    
    def _find_brand_specific_matches(self, name: str, brand_name: str, intent_tags: List[str]) -> Dict:
        """브랜드별 특화 매칭"""
        score = 0.0
        matched_keywords = []
        
        if not brand_name or brand_name not in self.brand_keywords:
            return {'score': 0.0, 'keywords': []}
        
        brand_specific_keywords = self.brand_keywords[brand_name]
        
        for keyword in brand_specific_keywords:
            if keyword in name:
                # 브랜드 특화 키워드는 보너스 점수
                score += 10.0
                matched_keywords.append(f"{brand_name}_{keyword}")
        
        return {'score': min(score, 100.0), 'keywords': matched_keywords}
    
    def _get_product_type_weight(self, category: str) -> float:
        """제품 타입별 가중치"""
        if not category:
            return 1.0
        
        for product_type, weight in self.product_type_weights.items():
            if product_type in category:
                return weight
        
        return 1.0
    
    def _calculate_name_confidence(self, match_details: Dict[str, float], keyword_count: int) -> float:
        """제품명 매칭 신뢰도"""
        
        # 여러 매칭 방식의 일관성
        scores = [score for score in match_details.values() if score > 0]
        if not scores:
            return 0.0
        
        # 점수 분산이 낮을수록 일관성 높음
        avg_score = sum(scores) / len(scores)
        variance = sum((score - avg_score) ** 2 for score in scores) / len(scores)
        consistency = 1.0 / (1.0 + variance / 100)  # 정규화
        
        # 매칭 방식의 다양성
        active_methods = sum(1 for score in match_details.values() if score > 0)
        diversity = active_methods / len(match_details)
        
        # 키워드 매칭 수
        keyword_factor = min(keyword_count / 3.0, 1.0)
        
        # 최고 점수
        max_score = max(match_details.values()) / 100.0
        
        confidence = (consistency * 0.3 + diversity * 0.3 + keyword_factor * 0.2 + max_score * 0.2)
        
        return min(confidence, 1.0)
    
    def analyze_name_matching_quality(self, product_names: List[str], intent_tags: List[str]) -> Dict:
        """제품명 매칭 품질 분석"""
        
        results = []
        for name in product_names:
            result = self.calculate_name_match_score(name, intent_tags)
            results.append(result)
        
        if not results:
            return {}
        
        scores = [r.match_score for r in results]
        confidences = [r.confidence for r in results]
        
        return {
            'total_products': len(results),
            'avg_score': sum(scores) / len(scores),
            'max_score': max(scores),
            'min_score': min(scores),
            'avg_confidence': sum(confidences) / len(confidences),
            'high_score_count': sum(1 for s in scores if s >= 70),
            'score_distribution': {
                '80+': sum(1 for s in scores if s >= 80),
                '60-79': sum(1 for s in scores if 60 <= s < 80),
                '40-59': sum(1 for s in scores if 40 <= s < 60),
                '<40': sum(1 for s in scores if s < 40)
            }
        }