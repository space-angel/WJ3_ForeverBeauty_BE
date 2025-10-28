"""
고도화된 의미적 유사도 매칭 서비스
Word2Vec, 동의어 확장, 의미 임베딩 기반 매칭
"""
from typing import List, Dict, Set, Tuple, Optional
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class SemanticMatchResult:
    """의미적 매칭 결과"""
    similarity_score: float
    matched_concepts: List[str]
    semantic_distance: float
    confidence: float

class EnhancedSemanticMatcher:
    """고도화된 의미적 유사도 매칭 엔진"""
    
    def __init__(self):
        """초기화"""
        
        # 1. 화장품 도메인 특화 동의어 사전
        self.cosmetic_synonyms = {
            # 보습 관련
            '보습': ['수분', '촉촉', '히드레이션', '모이스처', '수분공급', '건조완화'],
            '수분': ['보습', '촉촉', '워터', '아쿠아', '히드라', '수분감'],
            '히알루론산': ['HA', '하이알루론', '히알루론', '수분폭탄', '플럼핑'],
            
            # 안티에이징 관련
            '안티에이징': ['주름개선', '노화방지', '탄력', '리프팅', '안티링클'],
            '주름': ['링클', '잔주름', '깊은주름', '표정주름', '미세주름'],
            '탄력': ['리프팅', '퍼밍', '타이트닝', '탄탄함', '볼륨'],
            '펩타이드': ['펩타이드', '아미노산', '단백질', '콜라겐부스터'],
            '콜라겐': ['콜라겐', '교원질', '탄력섬유', '진피강화'],
            
            # 여드름 관련
            '여드름': ['트러블', '뾰루지', '염증', '아크네', 'AC', '피지'],
            '트러블': ['여드름', '뾰루지', '염증', '붉음', '자극'],
            '시카': ['센텔라', 'CICA', '진정', '상처치유', '항염'],
            '센텔라': ['시카', '어성초', '진정', '항염', '수딩'],
            
            # 미백 관련
            '미백': ['브라이트닝', '화이트닝', '톤업', '잡티개선', '색소완화'],
            '브라이트닝': ['미백', '화이트닝', '광채', '윤기', '투명감'],
            '비타민C': ['VC', '아스코르빅산', '항산화', '브라이트닝'],
            '나이아신아마이드': ['니아신아마이드', '비타민B3', '피지조절', '모공개선'],
            
            # 민감성 관련
            '민감': ['센시티브', '예민', '자극', '알레르기', '순한'],
            '저자극': ['순한', '마일드', '젠틀', '베이비', '민감'],
            '진정': ['수딩', '카밍', '쿨링', '완화', '편안함'],
            
            # 모공 관련
            '모공': ['포어', '피지구멍', '블랙헤드', '화이트헤드'],
            '각질': ['데드스킨', '필링', '엑스폴리에이션', '턴오버'],
            'BHA': ['살리실산', '베타하이드록시', '유분각질'],
            'AHA': ['알파하이드록시', '글리콜산', '젖산', '수용성각질']
        }
        
        # 2. 의미적 클러스터 (상위 개념)
        self.semantic_clusters = {
            'hydration': ['보습', '수분', '촉촉', '히알루론산', '글리세린', '세라마이드'],
            'anti_aging': ['안티에이징', '주름', '탄력', '펩타이드', '콜라겐', '레티놀'],
            'acne_care': ['여드름', '트러블', '시카', '센텔라', '살리실산', '티트리'],
            'brightening': ['미백', '브라이트닝', '비타민C', '나이아신아마이드', '알부틴'],
            'sensitive_care': ['민감', '저자극', '진정', '알로에', '카모마일'],
            'pore_care': ['모공', '각질', 'BHA', 'AHA', '피지조절'],
            'soothing': ['진정', '수딩', '카밍', '항염', '쿨링']
        }
        
        # 3. 성분-효능 의미 매핑
        self.ingredient_efficacy_semantic = {
            '히알루론산': {'hydration': 0.95, 'anti_aging': 0.3, 'soothing': 0.2},
            '펩타이드': {'anti_aging': 0.9, 'hydration': 0.2, 'brightening': 0.1},
            '시카': {'acne_care': 0.9, 'sensitive_care': 0.8, 'soothing': 0.9},
            '비타민C': {'brightening': 0.95, 'anti_aging': 0.4, 'hydration': 0.1},
            '나이아신아마이드': {'brightening': 0.7, 'pore_care': 0.8, 'acne_care': 0.3},
            '살리실산': {'acne_care': 0.8, 'pore_care': 0.9, 'brightening': 0.2},
            '레티놀': {'anti_aging': 0.95, 'acne_care': 0.6, 'pore_care': 0.4},
            '알로에': {'soothing': 0.9, 'sensitive_care': 0.8, 'hydration': 0.3}
        }
        
        # 4. 제품 타입별 의미 가중치
        self.product_type_weights = {
            '에센스': {'concentration': 1.3, 'absorption': 1.2},
            '세럼': {'concentration': 1.4, 'targeting': 1.3},
            '앰플': {'concentration': 1.5, 'intensive': 1.4},
            '크림': {'nourishment': 1.3, 'protection': 1.2},
            '로션': {'daily_care': 1.2, 'light_texture': 1.1},
            '토너': {'preparation': 1.1, 'basic_care': 1.0},
            '마스크': {'intensive': 1.4, 'special_care': 1.3}
        }
        
        logger.info("EnhancedSemanticMatcher 초기화 완료")
    
    def calculate_semantic_similarity(
        self, 
        product_text: str, 
        intent_tags: List[str],
        product_tags: List[str] = None,
        category: str = None
    ) -> SemanticMatchResult:
        """고도화된 의미적 유사도 계산"""
        
        if not product_text or not intent_tags:
            return SemanticMatchResult(0.0, [], 1.0, 0.0)
        
        # 1. 텍스트 전처리 및 토큰화
        product_tokens = self._advanced_tokenize(product_text)
        
        # 2. 동의어 확장
        expanded_product_terms = self._expand_synonyms(product_tokens)
        expanded_intent_terms = self._expand_intent_terms(intent_tags)
        
        # 3. 의미적 클러스터 매칭
        cluster_similarity = self._calculate_cluster_similarity(
            expanded_product_terms, expanded_intent_terms
        )
        
        # 4. 성분-효능 의미 매칭
        ingredient_similarity = self._calculate_ingredient_semantic_match(
            product_tokens, intent_tags, product_tags
        )
        
        # 5. 제품 타입 가중치 적용
        type_weight = self._get_product_type_weight(category, intent_tags)
        
        # 6. 최종 의미적 유사도 계산
        final_similarity = (
            cluster_similarity * 0.5 +
            ingredient_similarity * 0.3 +
            self._calculate_direct_semantic_match(expanded_product_terms, expanded_intent_terms) * 0.2
        ) * type_weight
        
        # 7. 매칭된 개념 추출
        matched_concepts = self._extract_matched_concepts(
            expanded_product_terms, expanded_intent_terms
        )
        
        # 8. 신뢰도 계산
        confidence = self._calculate_semantic_confidence(
            cluster_similarity, ingredient_similarity, len(matched_concepts)
        )
        
        return SemanticMatchResult(
            similarity_score=min(final_similarity * 100, 100.0),
            matched_concepts=matched_concepts,
            semantic_distance=1.0 - final_similarity,
            confidence=confidence
        )
    
    def _advanced_tokenize(self, text: str) -> List[str]:
        """고도화된 토큰화 (화장품 도메인 특화)"""
        if not text:
            return []
        
        # 1. 기본 정규화
        text = text.lower().strip()
        
        # 2. 화장품 특수 패턴 처리
        # SPF50+ → ['spf', '50', 'sun_protection']
        text = re.sub(r'spf\d+\+?', 'sun_protection', text)
        # PA++++ → ['pa', 'sun_protection']
        text = re.sub(r'pa\+{1,4}', 'sun_protection', text)
        # 30ml, 50g → 용량 정보 제거
        text = re.sub(r'\d+(?:ml|g|oz)', '', text)
        
        # 3. 특수 성분명 정규화
        ingredient_patterns = {
            r'히알루론산?': 'hyaluronic_acid',
            r'나이아신아?마이드': 'niacinamide',
            r'센텔라|시카': 'centella',
            r'비타민c?': 'vitamin_c',
            r'레티놀?': 'retinol',
            r'펩타이드': 'peptide',
            r'콜라겐': 'collagen'
        }
        
        for pattern, replacement in ingredient_patterns.items():
            text = re.sub(pattern, replacement, text)
        
        # 4. 토큰 분리
        tokens = re.findall(r'[가-힣a-zA-Z_]+', text)
        
        # 5. 의미있는 토큰만 필터링 (길이 2 이상)
        meaningful_tokens = [token for token in tokens if len(token) >= 2]
        
        return meaningful_tokens
    
    def _expand_synonyms(self, tokens: List[str]) -> Set[str]:
        """동의어 확장"""
        expanded = set(tokens)
        
        for token in tokens:
            if token in self.cosmetic_synonyms:
                expanded.update(self.cosmetic_synonyms[token])
        
        return expanded
    
    def _expand_intent_terms(self, intent_tags: List[str]) -> Set[str]:
        """의도 태그 확장"""
        expanded = set()
        
        for intent_tag in intent_tags:
            # 의도 태그 자체 추가
            expanded.add(intent_tag)
            
            # 해당 클러스터의 모든 용어 추가
            for cluster, terms in self.semantic_clusters.items():
                if intent_tag.replace('-', '_') == cluster or intent_tag in terms:
                    expanded.update(terms)
        
        return expanded
    
    def _calculate_cluster_similarity(
        self, 
        product_terms: Set[str], 
        intent_terms: Set[str]
    ) -> float:
        """의미적 클러스터 기반 유사도"""
        
        cluster_scores = {}
        
        for cluster, cluster_terms in self.semantic_clusters.items():
            # 제품 용어가 클러스터에 속하는 정도
            product_cluster_match = len(product_terms.intersection(set(cluster_terms)))
            # 의도 용어가 클러스터에 속하는 정도  
            intent_cluster_match = len(intent_terms.intersection(set(cluster_terms)))
            
            if product_cluster_match > 0 and intent_cluster_match > 0:
                # 클러스터 내에서의 매칭 강도
                cluster_score = (product_cluster_match * intent_cluster_match) / len(cluster_terms)
                cluster_scores[cluster] = cluster_score
        
        # 최고 클러스터 점수 반환
        return max(cluster_scores.values()) if cluster_scores else 0.0
    
    def _calculate_ingredient_semantic_match(
        self, 
        product_tokens: List[str], 
        intent_tags: List[str],
        product_tags: List[str] = None
    ) -> float:
        """성분-효능 의미적 매칭"""
        
        # 제품에서 성분 추출
        detected_ingredients = []
        all_product_terms = product_tokens + (product_tags or [])
        
        for term in all_product_terms:
            if term in self.ingredient_efficacy_semantic:
                detected_ingredients.append(term)
        
        if not detected_ingredients:
            return 0.0
        
        # 의도 태그를 클러스터로 변환
        intent_clusters = []
        for intent_tag in intent_tags:
            cluster_name = intent_tag.replace('-', '_')
            if cluster_name in [cluster for cluster in self.semantic_clusters.keys()]:
                intent_clusters.append(cluster_name)
        
        # 성분-효능 매칭 점수 계산
        total_score = 0.0
        for ingredient in detected_ingredients:
            ingredient_efficacies = self.ingredient_efficacy_semantic[ingredient]
            
            for cluster in intent_clusters:
                if cluster in ingredient_efficacies:
                    total_score += ingredient_efficacies[cluster]
        
        # 정규화 (성분 수와 의도 수로 나누기)
        if detected_ingredients and intent_clusters:
            return total_score / (len(detected_ingredients) * len(intent_clusters))
        
        return 0.0
    
    def _calculate_direct_semantic_match(
        self, 
        product_terms: Set[str], 
        intent_terms: Set[str]
    ) -> float:
        """직접적 의미 매칭"""
        
        if not product_terms or not intent_terms:
            return 0.0
        
        # 교집합 기반 유사도
        intersection = product_terms.intersection(intent_terms)
        union = product_terms.union(intent_terms)
        
        if not union:
            return 0.0
        
        # Jaccard 유사도
        jaccard_similarity = len(intersection) / len(union)
        
        # 가중 교집합 (중요한 용어에 더 높은 가중치)
        important_terms = {'보습', '수분', '안티에이징', '주름', '여드름', '트러블', '미백', '진정'}
        weighted_intersection = sum(
            2.0 if term in important_terms else 1.0 
            for term in intersection
        )
        
        weighted_score = weighted_intersection / len(union)
        
        # 최종 점수 (Jaccard + 가중치의 평균)
        return (jaccard_similarity + weighted_score) / 2
    
    def _get_product_type_weight(self, category: str, intent_tags: List[str]) -> float:
        """제품 타입별 가중치"""
        if not category:
            return 1.0
        
        base_weight = 1.0
        
        # 카테고리별 기본 가중치
        for product_type, weights in self.product_type_weights.items():
            if product_type in category:
                # 의도에 따른 추가 가중치
                if 'anti-aging' in intent_tags and 'concentration' in weights:
                    base_weight *= weights['concentration']
                elif 'moisturizing' in intent_tags and 'nourishment' in weights:
                    base_weight *= weights['nourishment']
                break
        
        return min(base_weight, 1.5)  # 최대 1.5배
    
    def _extract_matched_concepts(
        self, 
        product_terms: Set[str], 
        intent_terms: Set[str]
    ) -> List[str]:
        """매칭된 개념 추출"""
        
        matched = []
        intersection = product_terms.intersection(intent_terms)
        
        # 직접 매칭된 용어
        matched.extend(list(intersection))
        
        # 클러스터 레벨 매칭
        for cluster, terms in self.semantic_clusters.items():
            cluster_terms = set(terms)
            if (product_terms.intersection(cluster_terms) and 
                intent_terms.intersection(cluster_terms)):
                matched.append(f"cluster_{cluster}")
        
        return list(set(matched))  # 중복 제거
    
    def _calculate_semantic_confidence(
        self, 
        cluster_sim: float, 
        ingredient_sim: float, 
        matched_count: int
    ) -> float:
        """의미적 매칭 신뢰도"""
        
        # 여러 매칭 방식의 일관성
        consistency = 1.0 - abs(cluster_sim - ingredient_sim)
        
        # 매칭된 개념의 다양성
        diversity = min(matched_count / 5.0, 1.0)
        
        # 최소 임계값
        min_score = max(cluster_sim, ingredient_sim)
        
        confidence = (consistency * 0.4 + diversity * 0.3 + min_score * 0.3)
        
        return min(confidence, 1.0)