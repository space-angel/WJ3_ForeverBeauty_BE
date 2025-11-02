"""
고도화된 의도 매칭 서비스
TF-IDF, 의미적 유사도, 다층 매칭 알고리즘 적용
"""
from typing import List, Dict, Set, Tuple, Optional
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

@dataclass
class IntentMatchResult:
    """의도 매칭 결과"""
    product_id: int
    total_score: float
    tag_match_score: float
    name_match_score: float
    category_match_score: float
    semantic_score: float
    matched_tags: List[str]
    matched_keywords: List[str]
    confidence: float

class AdvancedIntentMatcher:
    """고도화된 의도 매칭 엔진"""
    
    def __init__(self):
        """초기화 및 매핑 데이터 로딩"""
        
        # 1. 확장된 의도-키워드 매핑 (계층적 구조)
        self.intent_hierarchy = {
            'moisturizing': {
                'primary': ['보습', '수분', '촉촉', '히알루론산'],
                'secondary': ['건조', '당김', '유연', '부드러움'],
                'ingredients': ['히알루론산', '글리세린', '세라마이드', '스쿠알란', '판테놀'],
                'categories': ['크림', '로션', '에센스', '세럼', '앰플'],
                'weight': 1.0
            },
            'anti-aging': {
                'primary': ['안티에이징', '주름', '탄력', '노화방지', '리프팅'],
                'secondary': ['펩타이드', '콜라겐', '레티놀', '비타민C'],
                'ingredients': ['펩타이드', '콜라겐', '레티놀', '나이아신아마이드', '아데노신'],
                'categories': ['크림', '세럼', '앰플', '아이크림'],
                'weight': 1.2
            },
            'acne-care': {
                'primary': ['여드름', '트러블', '진정', '시카', '센텔라'],
                'secondary': ['염증', '뾰루지', '각질', '피지'],
                'ingredients': ['시카', '센텔라', '살리실산', '티트리', '약콩', '어성초'],
                'categories': ['세럼', '앰플', '토너', '크림'],
                'weight': 1.1
            },
            'sensitive-care': {
                'primary': ['민감', '순한', '저자극', '베이비'],
                'secondary': ['알레르기', '자극', '진정', '보호'],
                'ingredients': ['알로에', '카모마일', '센텔라', '판테놀'],
                'categories': ['크림', '로션', '클렌저', '토너'],
                'weight': 1.0
            },
            'brightening': {
                'primary': ['미백', '브라이트닝', '화이트닝', '톤업'],
                'secondary': ['잡티', '기미', '색소', '균일'],
                'ingredients': ['비타민C', '나이아신아마이드', '알부틴', '코직산'],
                'categories': ['세럼', '앰플', '크림', '마스크'],
                'weight': 1.0
            },
            'pore-care': {
                'primary': ['모공', '포어', '블랙헤드', '각질'],
                'secondary': ['피지', '유분', '세범', '깔끔'],
                'ingredients': ['BHA', 'AHA', '살리실산', '글리콜산'],
                'categories': ['토너', '세럼', '마스크', '클렌저'],
                'weight': 1.0
            },
            'soothing': {
                'primary': ['진정', '수딩', '카밍', '쿨링'],
                'secondary': ['자극완화', '염증완화', '편안함'],
                'ingredients': ['알로에', '센텔라', '카모마일', '녹차'],
                'categories': ['젤', '미스트', '마스크', '크림'],
                'weight': 1.0
            }
        }
        
        # 2. 카테고리별 가중치
        self.category_weights = {
            '에센스/앰플/세럼': 1.2,  # 고농축 제품
            '크림': 1.1,
            '로션/에멀젼': 1.0,
            '토너': 0.9,
            '마스크': 1.1,
            '클렌저': 0.8
        }
        
        # 3. 브랜드별 전문성 가중치
        self.brand_expertise = {
            '스킨1004': {'acne-care': 1.3, 'sensitive-care': 1.2},
            '라운드랩': {'acne-care': 1.2, 'sensitive-care': 1.1},
            '토리든': {'moisturizing': 1.2, 'anti-aging': 1.1},
            '웰라쥬': {'moisturizing': 1.3, 'soothing': 1.1},
            '이니스프리': {'brightening': 1.1, 'pore-care': 1.1}
        }
        
        # 4. TF-IDF 계산용 문서 코퍼스 (제품명 + 태그)
        self.document_corpus = []
        self.idf_scores = {}
        
        # AdvancedIntentMatcher 초기화 완료
    
    def build_corpus(self, products: List) -> None:
        """제품 데이터로부터 TF-IDF 코퍼스 구축"""
        self.document_corpus = []
        all_terms = set()
        
        for product in products:
            # 제품명 + 태그 + 카테고리를 하나의 문서로 구성
            doc_terms = []
            
            # 제품명 토큰화
            name_tokens = self._tokenize_korean(product.name)
            doc_terms.extend(name_tokens)
            
            # 태그 추가
            if hasattr(product, 'tags') and product.tags:
                try:
                    if isinstance(product.tags, str):
                        tags = json.loads(product.tags)
                    else:
                        tags = product.tags
                    
                    if isinstance(tags, list):
                        doc_terms.extend(tags)
                except:
                    pass
            
            # 카테고리 추가
            if hasattr(product, 'category_name') and product.category_name:
                category_tokens = self._tokenize_korean(product.category_name)
                doc_terms.extend(category_tokens)
            
            self.document_corpus.append(doc_terms)
            all_terms.update(doc_terms)
        
        # IDF 점수 계산
        total_docs = len(self.document_corpus)
        for term in all_terms:
            doc_freq = sum(1 for doc in self.document_corpus if term in doc)
            self.idf_scores[term] = math.log(total_docs / (doc_freq + 1))
        
        # TF-IDF 코퍼스 구축 완료
    
    def calculate_intent_match_score(
        self, 
        product, 
        intent_tags: List[str],
        product_index: int = None
    ) -> IntentMatchResult:
        """고도화된 의도 매칭 점수 계산"""
        
        if not intent_tags:
            return IntentMatchResult(
                product_id=getattr(product, 'product_id', 0),
                total_score=30.0,
                tag_match_score=0.0,
                name_match_score=0.0,
                category_match_score=0.0,
                semantic_score=0.0,
                matched_tags=[],
                matched_keywords=[],
                confidence=0.3
            )
        
        # 1. 태그 기반 매칭 (가중치 40%)
        tag_score, matched_tags = self._calculate_tag_matching(product, intent_tags)
        
        # 2. 제품명 기반 매칭 (가중치 30%)
        name_score, matched_keywords = self._calculate_name_matching(product, intent_tags)
        
        # 3. 카테고리 기반 매칭 (가중치 15%)
        category_score = self._calculate_category_matching(product, intent_tags)
        
        # 4. 의미적 유사도 매칭 (가중치 15%)
        semantic_score = self._calculate_semantic_matching(product, intent_tags, product_index)
        
        # 5. 브랜드 전문성 보너스
        brand_bonus = self._calculate_brand_expertise_bonus(product, intent_tags)
        
        # 최종 점수 계산 (가중 평균)
        total_score = (
            tag_score * 0.4 +
            name_score * 0.3 +
            category_score * 0.15 +
            semantic_score * 0.15 +
            brand_bonus
        )
        
        # 신뢰도 계산 (매칭된 요소의 다양성 기반)
        confidence = self._calculate_confidence(
            tag_score, name_score, category_score, semantic_score
        )
        
        return IntentMatchResult(
            product_id=getattr(product, 'product_id', 0),
            total_score=min(total_score, 100.0),
            tag_match_score=tag_score,
            name_match_score=name_score,
            category_match_score=category_score,
            semantic_score=semantic_score,
            matched_tags=matched_tags,
            matched_keywords=matched_keywords,
            confidence=confidence
        )
    
    def _calculate_tag_matching(self, product, intent_tags: List[str]) -> Tuple[float, List[str]]:
        """태그 기반 매칭 점수 계산"""
        if not hasattr(product, 'tags') or not product.tags:
            return 0.0, []
        
        try:
            if isinstance(product.tags, str):
                product_tags = json.loads(product.tags)
            else:
                product_tags = product.tags
            
            if not isinstance(product_tags, list):
                return 0.0, []
        except:
            return 0.0, []
        
        total_score = 0.0
        matched_tags = []
        
        for intent_tag in intent_tags:
            intent_config = self.intent_hierarchy.get(intent_tag, {})
            intent_weight = intent_config.get('weight', 1.0)
            
            # Primary 키워드 매칭 (높은 점수)
            primary_keywords = intent_config.get('primary', [])
            for keyword in primary_keywords:
                if any(keyword in str(tag) for tag in product_tags):
                    total_score += 25 * intent_weight
                    matched_tags.append(keyword)
                    break
            
            # Secondary 키워드 매칭 (중간 점수)
            secondary_keywords = intent_config.get('secondary', [])
            for keyword in secondary_keywords:
                if any(keyword in str(tag) for tag in product_tags):
                    total_score += 15 * intent_weight
                    matched_tags.append(keyword)
                    break
            
            # Ingredient 매칭 (보너스 점수)
            ingredients = intent_config.get('ingredients', [])
            for ingredient in ingredients:
                if any(ingredient in str(tag) for tag in product_tags):
                    total_score += 10 * intent_weight
                    matched_tags.append(ingredient)
        
        return min(total_score, 100.0), matched_tags
    
    def _calculate_name_matching(self, product, intent_tags: List[str]) -> Tuple[float, List[str]]:
        """고도화된 제품명 기반 매칭 점수 계산"""
        if not hasattr(product, 'name') or not product.name:
            return 0.0, []
        
        try:
            # 고도화된 제품명 매칭 엔진 사용
            from app.services.enhanced_name_matcher import EnhancedNameMatcher
            
            name_matcher = EnhancedNameMatcher()
            result = name_matcher.calculate_name_match_score(
                product.name, 
                intent_tags,
                getattr(product, 'brand_name', None),
                getattr(product, 'category_name', None)
            )
            
            return result.match_score, result.matched_keywords
            
        except Exception as e:
            logger.warning(f"고도화된 제품명 매칭 실패, 기본 로직 사용: {e}")
            
            # 폴백: 기존 로직 (개선된 버전)
            product_name = product.name.lower()
            total_score = 0.0
            matched_keywords = []
            
            for intent_tag in intent_tags:
                intent_config = self.intent_hierarchy.get(intent_tag, {})
                intent_weight = intent_config.get('weight', 1.0)
                
                # 모든 키워드 카테고리에서 매칭 시도
                all_keywords = (
                    intent_config.get('primary', []) +
                    intent_config.get('secondary', []) +
                    intent_config.get('ingredients', [])
                )
                
                for keyword in all_keywords:
                    if keyword in product_name:
                        # 키워드 길이에 따른 가중치 (긴 키워드일수록 정확도 높음)
                        length_weight = min(len(keyword) / 3, 2.0)
                        score = 15 * intent_weight * length_weight
                        total_score += score
                        matched_keywords.append(keyword)
            
            return min(total_score, 100.0), matched_keywords
    
    def _calculate_category_matching(self, product, intent_tags: List[str]) -> float:
        """카테고리 기반 매칭 점수 계산"""
        if not hasattr(product, 'category_name') or not product.category_name:
            return 0.0
        
        product_category = product.category_name
        total_score = 0.0
        
        for intent_tag in intent_tags:
            intent_config = self.intent_hierarchy.get(intent_tag, {})
            suitable_categories = intent_config.get('categories', [])
            
            for category in suitable_categories:
                if category in product_category:
                    # 카테고리별 가중치 적용
                    category_weight = self.category_weights.get(product_category, 1.0)
                    total_score += 20 * category_weight
                    break
        
        return min(total_score, 100.0)
    
    def _calculate_semantic_matching(self, product, intent_tags: List[str], product_index: int) -> float:
        """고도화된 의미적 유사도 계산"""
        
        try:
            # 고도화된 의미적 매칭 엔진 사용
            from app.services.enhanced_semantic_matcher import EnhancedSemanticMatcher
            
            semantic_matcher = EnhancedSemanticMatcher()
            
            # 제품 텍스트 구성 (제품명 + 태그)
            product_text = getattr(product, 'name', '')
            product_tags = []
            
            if hasattr(product, 'tags') and product.tags:
                try:
                    if isinstance(product.tags, str):
                        import json
                        product_tags = json.loads(product.tags)
                    else:
                        product_tags = product.tags or []
                except:
                    product_tags = []
            
            result = semantic_matcher.calculate_semantic_similarity(
                product_text,
                intent_tags,
                product_tags,
                getattr(product, 'category_name', None)
            )
            
            return result.similarity_score
            
        except Exception as e:
            logger.warning(f"고도화된 의미적 매칭 실패, 기본 로직 사용: {e}")
            
            # 폴백: 기존 TF-IDF 로직
            if product_index is None or product_index >= len(self.document_corpus):
                return 0.0
            
            product_doc = self.document_corpus[product_index]
            
            # 의도 태그를 쿼리 벡터로 변환
            query_terms = []
            for intent_tag in intent_tags:
                intent_config = self.intent_hierarchy.get(intent_tag, {})
                query_terms.extend(intent_config.get('primary', []))
                query_terms.extend(intent_config.get('secondary', []))
            
            if not query_terms or not product_doc:
                return 0.0
            
            # 코사인 유사도 계산
            similarity = self._calculate_cosine_similarity(query_terms, product_doc)
            return similarity * 100.0
    
    def _calculate_cosine_similarity(self, query_terms: List[str], doc_terms: List[str]) -> float:
        """코사인 유사도 계산"""
        # TF 계산
        query_tf = Counter(query_terms)
        doc_tf = Counter(doc_terms)
        
        # 공통 용어
        common_terms = set(query_tf.keys()) & set(doc_tf.keys())
        
        if not common_terms:
            return 0.0
        
        # TF-IDF 벡터 내적
        dot_product = 0.0
        query_norm = 0.0
        doc_norm = 0.0
        
        all_terms = set(query_tf.keys()) | set(doc_tf.keys())
        
        for term in all_terms:
            query_tfidf = query_tf.get(term, 0) * self.idf_scores.get(term, 0)
            doc_tfidf = doc_tf.get(term, 0) * self.idf_scores.get(term, 0)
            
            dot_product += query_tfidf * doc_tfidf
            query_norm += query_tfidf ** 2
            doc_norm += doc_tfidf ** 2
        
        if query_norm == 0 or doc_norm == 0:
            return 0.0
        
        return dot_product / (math.sqrt(query_norm) * math.sqrt(doc_norm))
    
    def _calculate_brand_expertise_bonus(self, product, intent_tags: List[str]) -> float:
        """브랜드 전문성 보너스 계산"""
        if not hasattr(product, 'brand_name') or not product.brand_name:
            return 0.0
        
        brand_name = product.brand_name
        total_bonus = 0.0
        
        if brand_name in self.brand_expertise:
            brand_config = self.brand_expertise[brand_name]
            for intent_tag in intent_tags:
                if intent_tag in brand_config:
                    expertise_multiplier = brand_config[intent_tag]
                    total_bonus += 5 * (expertise_multiplier - 1.0)
        
        return min(total_bonus, 15.0)  # 최대 15점 보너스
    
    def _calculate_confidence(self, tag_score: float, name_score: float, 
                            category_score: float, semantic_score: float) -> float:
        """매칭 신뢰도 계산"""
        # 여러 매칭 방식에서 점수를 얻을수록 신뢰도 높음
        score_sources = [tag_score, name_score, category_score, semantic_score]
        active_sources = sum(1 for score in score_sources if score > 0)
        
        if active_sources == 0:
            return 0.0
        
        # 평균 점수와 다양성을 고려한 신뢰도
        avg_score = sum(score_sources) / len(score_sources)
        diversity_bonus = active_sources / len(score_sources)
        
        confidence = (avg_score / 100.0) * 0.7 + diversity_bonus * 0.3
        return min(confidence, 1.0)
    
    def _tokenize_korean(self, text: str) -> List[str]:
        """한국어 텍스트 토큰화 (간단한 구현)"""
        if not text:
            return []
        
        # 공백, 특수문자 기준 분리
        import re
        tokens = re.findall(r'[가-힣a-zA-Z0-9]+', text.lower())
        
        # 길이 2 이상인 토큰만 유지
        return [token for token in tokens if len(token) >= 2]
    
    def batch_calculate_scores(self, products: List, intent_tags: List[str]) -> List[IntentMatchResult]:
        """배치 점수 계산"""
        # 코퍼스 구축
        self.build_corpus(products)
        
        results = []
        for i, product in enumerate(products):
            result = self.calculate_intent_match_score(product, intent_tags, i)
            results.append(result)
        
        return results
    
    def get_matching_statistics(self, results: List[IntentMatchResult]) -> Dict:
        """매칭 통계 정보"""
        if not results:
            return {}
        
        scores = [r.total_score for r in results]
        confidences = [r.confidence for r in results]
        
        return {
            'total_products': len(results),
            'avg_score': sum(scores) / len(scores),
            'max_score': max(scores),
            'min_score': min(scores),
            'avg_confidence': sum(confidences) / len(confidences),
            'high_confidence_count': sum(1 for c in confidences if c > 0.7),
            'score_distribution': {
                '80+': sum(1 for s in scores if s >= 80),
                '60-79': sum(1 for s in scores if 60 <= s < 80),
                '40-59': sum(1 for s in scores if 40 <= s < 60),
                '<40': sum(1 for s in scores if s < 40)
            }
        }