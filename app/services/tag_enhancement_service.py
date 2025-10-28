"""
제품 태그 데이터 보강 서비스
AI 기반 태그 생성, 정규화, 품질 개선
"""
from typing import List, Dict, Set, Tuple, Optional, Any
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
import logging

from app.database.sqlite_db import get_sqlite_db
from app.services.ingredient_service import IngredientService

logger = logging.getLogger(__name__)

@dataclass
class TagEnhancementResult:
    """태그 보강 결과"""
    product_id: int
    original_tags: List[str]
    enhanced_tags: List[str]
    generated_tags: List[str]
    confidence_scores: Dict[str, float]
    enhancement_methods: List[str]

class TagEnhancementService:
    """제품 태그 데이터 보강 서비스"""
    
    def __init__(self):
        """초기화"""
        self.db = get_sqlite_db()
        self.ingredient_service = IngredientService()
        
        # 1. 표준 태그 사전 (계층적 구조)
        self.standard_taxonomy = {
            # 기능별 태그
            'function': {
                '보습': ['moisturizing', 'hydrating', '수분', '촉촉', '건조완화'],
                '안티에이징': ['anti-aging', '주름개선', '탄력', '리프팅', '노화방지'],
                '진정': ['soothing', 'calming', '자극완화', '염증완화', '쿨링'],
                '미백': ['brightening', 'whitening', '톤업', '잡티개선', '색소완화'],
                '여드름케어': ['acne-care', '트러블케어', '피지조절', '모공케어'],
                '각질케어': ['exfoliating', '필링', '각질제거', '피부결개선'],
                '자외선차단': ['sun-protection', 'UV차단', 'SPF', 'PA'],
                '민감케어': ['sensitive-care', '저자극', '순한', '베이비']
            },
            
            # 성분별 태그
            'ingredient': {
                '히알루론산': ['hyaluronic-acid', '수분', '보습', '플럼핑'],
                '비타민C': ['vitamin-c', '미백', '항산화', '브라이트닝'],
                '레티놀': ['retinol', '안티에이징', '주름개선', '턴오버'],
                '나이아신아마이드': ['niacinamide', '미백', '피지조절', '모공개선'],
                '펩타이드': ['peptide', '안티에이징', '탄력', '콜라겐부스팅'],
                '시카': ['cica', 'centella', '진정', '상처치유', '항염'],
                'AHA': ['alpha-hydroxy-acid', '각질제거', '피부결개선', '브라이트닝'],
                'BHA': ['beta-hydroxy-acid', '모공케어', '피지조절', '각질제거'],
                '세라마이드': ['ceramide', '보습', '장벽강화', '수분보유']
            },
            
            # 피부타입별 태그
            'skin_type': {
                '건성': ['dry-skin', '보습', '수분공급', '영양공급'],
                '지성': ['oily-skin', '피지조절', '모공케어', '유분조절'],
                '복합성': ['combination-skin', '밸런싱', '부분케어'],
                '민감성': ['sensitive-skin', '저자극', '진정', '순한'],
                '정상': ['normal-skin', '밸런싱', '기본케어']
            },
            
            # 연령대별 태그
            'age_group': {
                '10대': ['teen-care', '여드름케어', '피지조절', '기본케어'],
                '20대': ['young-adult', '예방케어', '수분공급', '트러블케어'],
                '30대': ['early-aging', '초기안티에이징', '탄력케어', '보습강화'],
                '40대': ['anti-aging', '주름케어', '탄력케어', '집중케어'],
                '50대+': ['mature-skin', '깊은주름', '탄력회복', '영양공급']
            }
        }
        
        # 2. 성분-효능 매핑
        self.ingredient_efficacy_map = {
            '히알루론산': ['보습', '수분', '플럼핑'],
            '글리세린': ['보습', '수분보유'],
            '세라마이드': ['보습', '장벽강화'],
            '스쿠알란': ['보습', '영양공급'],
            '판테놀': ['진정', '보습', '상처치유'],
            '알로에': ['진정', '쿨링', '수분공급'],
            '센텔라': ['진정', '항염', '상처치유'],
            '카모마일': ['진정', '항염', '민감케어'],
            '녹차': ['항산화', '진정', '피지조절'],
            '비타민C': ['미백', '항산화', '브라이트닝'],
            '나이아신아마이드': ['미백', '피지조절', '모공개선'],
            '알부틴': ['미백', '색소완화'],
            '코직산': ['미백', '잡티개선'],
            '레티놀': ['안티에이징', '주름개선', '턴오버촉진'],
            '펩타이드': ['안티에이징', '탄력', '콜라겐부스팅'],
            '아데노신': ['안티에이징', '주름개선'],
            '콜라겐': ['탄력', '보습', '안티에이징'],
            '살리실산': ['각질제거', '모공케어', '피지조절'],
            '글리콜산': ['각질제거', '피부결개선'],
            '젖산': ['각질제거', '보습', '순한필링'],
            '티트리': ['여드름케어', '항균', '피지조절'],
            '징크옥사이드': ['자외선차단', '진정', '민감케어'],
            '티타늄디옥사이드': ['자외선차단', '물리차단']
        }
        
        # 3. 제품명 패턴 매칭 규칙
        self.name_pattern_rules = [
            (r'수분|보습|히알루론|아쿠아|워터', ['보습', '수분']),
            (r'주름|안티에이징|탄력|리프팅|펩타이드', ['안티에이징', '주름케어']),
            (r'진정|수딩|카밍|센텔라|시카', ['진정', '민감케어']),
            (r'미백|브라이트|화이트|톤업|비타민C', ['미백', '브라이트닝']),
            (r'여드름|트러블|AC|시카|티트리', ['여드름케어', '트러블케어']),
            (r'모공|포어|블랙헤드|BHA|AHA', ['모공케어', '각질케어']),
            (r'민감|순한|저자극|베이비|센시티브', ['민감케어', '저자극']),
            (r'선크림|선블록|SPF|PA|UV', ['자외선차단']),
            (r'오일|유분|세범|피지', ['피지조절', '유분케어']),
            (r'각질|필링|스크럽|엑스폴리에이팅', ['각질케어', '피부결개선'])
        ]
        
        logger.info("TagEnhancementService 초기화 완료")
    
    def enhance_all_product_tags(self, batch_size: int = 50) -> Dict[str, int]:
        """모든 제품의 태그 보강"""
        
        # 전체 제품 조회
        query = "SELECT product_id, name, brand_name, category_name, tags FROM products"
        products = self.db.execute_query(query)
        
        total_products = len(products)
        enhanced_count = 0
        generated_count = 0
        error_count = 0
        
        logger.info(f"태그 보강 시작: {total_products}개 제품")
        
        for i in range(0, total_products, batch_size):
            batch = products[i:i + batch_size]
            
            for product_data in batch:
                try:
                    result = self.enhance_product_tags(
                        product_data['product_id'],
                        product_data['name'],
                        product_data['brand_name'],
                        product_data['category_name'],
                        product_data.get('tags')
                    )
                    
                    if result.enhanced_tags != result.original_tags:
                        # 데이터베이스 업데이트
                        self._update_product_tags(
                            product_data['product_id'], 
                            result.enhanced_tags
                        )
                        enhanced_count += 1
                    
                    if result.generated_tags:
                        generated_count += 1
                    
                except Exception as e:
                    logger.error(f"제품 {product_data['product_id']} 태그 보강 실패: {e}")
                    error_count += 1
            
            # 진행률 로깅
            progress = min(i + batch_size, total_products)
            logger.info(f"진행률: {progress}/{total_products} ({progress/total_products*100:.1f}%)")
        
        logger.info(f"태그 보강 완료: 보강 {enhanced_count}개, 생성 {generated_count}개, 오류 {error_count}개")
        
        return {
            'total_products': total_products,
            'enhanced_count': enhanced_count,
            'generated_count': generated_count,
            'error_count': error_count
        }
    
    def enhance_product_tags(
        self, 
        product_id: int,
        product_name: str,
        brand_name: str,
        category_name: str,
        existing_tags: Optional[str] = None
    ) -> TagEnhancementResult:
        """단일 제품 태그 보강"""
        
        # 기존 태그 파싱
        original_tags = self._parse_existing_tags(existing_tags)
        
        # 1. 제품명 기반 태그 생성
        name_tags = self._generate_tags_from_name(product_name)
        
        # 2. 성분 기반 태그 생성
        ingredient_tags = self._generate_tags_from_ingredients(product_id)
        
        # 3. 카테고리 기반 태그 생성
        category_tags = self._generate_tags_from_category(category_name)
        
        # 4. 브랜드 기반 태그 생성
        brand_tags = self._generate_tags_from_brand(brand_name)
        
        # 5. 기존 태그 정규화
        normalized_tags = self._normalize_existing_tags(original_tags)
        
        # 6. 모든 태그 통합 및 중복 제거
        all_generated_tags = (
            name_tags + ingredient_tags + 
            category_tags + brand_tags
        )
        
        enhanced_tags = self._merge_and_deduplicate_tags(
            normalized_tags, all_generated_tags
        )
        
        # 7. 태그 품질 검증 및 신뢰도 계산
        confidence_scores = self._calculate_tag_confidence(
            enhanced_tags, product_name, all_generated_tags
        )
        
        # 8. 보강 방법 기록
        enhancement_methods = []
        if name_tags:
            enhancement_methods.append('name_analysis')
        if ingredient_tags:
            enhancement_methods.append('ingredient_analysis')
        if category_tags:
            enhancement_methods.append('category_mapping')
        if brand_tags:
            enhancement_methods.append('brand_expertise')
        if normalized_tags != original_tags:
            enhancement_methods.append('tag_normalization')
        
        return TagEnhancementResult(
            product_id=product_id,
            original_tags=original_tags,
            enhanced_tags=enhanced_tags,
            generated_tags=all_generated_tags,
            confidence_scores=confidence_scores,
            enhancement_methods=enhancement_methods
        )
    
    def _parse_existing_tags(self, tags_str: Optional[str]) -> List[str]:
        """기존 태그 파싱"""
        if not tags_str:
            return []
        
        try:
            if tags_str.startswith('[') and tags_str.endswith(']'):
                tags = json.loads(tags_str)
                if isinstance(tags, list):
                    return [str(tag).strip() for tag in tags if tag]
        except:
            pass
        
        # JSON 파싱 실패 시 문자열 분리 시도
        if ',' in tags_str:
            return [tag.strip().strip('"\'') for tag in tags_str.split(',') if tag.strip()]
        
        return [tags_str.strip()] if tags_str.strip() else []
    
    def _generate_tags_from_name(self, product_name: str) -> List[str]:
        """제품명 기반 태그 생성"""
        if not product_name:
            return []
        
        generated_tags = []
        name_lower = product_name.lower()
        
        # 패턴 매칭 규칙 적용
        for pattern, tags in self.name_pattern_rules:
            if re.search(pattern, name_lower):
                generated_tags.extend(tags)
        
        # 직접 성분명 매칭
        for ingredient, efficacies in self.ingredient_efficacy_map.items():
            if ingredient in name_lower:
                generated_tags.extend(efficacies)
        
        return list(set(generated_tags))  # 중복 제거
    
    def _generate_tags_from_ingredients(self, product_id: int) -> List[str]:
        """성분 기반 태그 생성"""
        try:
            # 제품의 성분 정보 조회
            ingredients = self.ingredient_service.get_product_ingredients(product_id)
            
            generated_tags = []
            
            for ingredient in ingredients:
                # 성분명 기반 태그 생성
                korean_name = getattr(ingredient, 'korean', '').lower()
                english_name = getattr(ingredient, 'english', '').lower()
                
                # 성분-효능 매핑에서 태그 생성
                for mapped_ingredient, efficacies in self.ingredient_efficacy_map.items():
                    if (mapped_ingredient in korean_name or 
                        mapped_ingredient in english_name):
                        generated_tags.extend(efficacies)
                
                # 성분 태그에서 직접 추출
                if hasattr(ingredient, 'tags') and ingredient.tags:
                    try:
                        ingredient_tags = json.loads(ingredient.tags) if isinstance(ingredient.tags, str) else ingredient.tags
                        if isinstance(ingredient_tags, list):
                            generated_tags.extend(ingredient_tags)
                    except:
                        pass
            
            return list(set(generated_tags))  # 중복 제거
            
        except Exception as e:
            logger.error(f"성분 기반 태그 생성 실패 (product_id: {product_id}): {e}")
            return []
    
    def _generate_tags_from_category(self, category_name: str) -> List[str]:
        """카테고리 기반 태그 생성"""
        if not category_name:
            return []
        
        category_lower = category_name.lower()
        generated_tags = []
        
        # 카테고리별 기본 태그 매핑
        category_mappings = {
            '크림': ['보습', '영양공급', '집중케어'],
            '로션': ['보습', '수분공급', '데일리케어'],
            '에센스': ['집중케어', '영양공급', '흡수력'],
            '세럼': ['집중케어', '고농축', '타겟케어'],
            '앰플': ['집중케어', '고농축', '즉각케어'],
            '토너': ['수분공급', '각질케어', '베이스케어'],
            '클렌저': ['세정', '클렌징', '기본케어'],
            '선크림': ['자외선차단', 'UV차단', '보호'],
            '마스크': ['집중케어', '스페셜케어', '즉각케어'],
            '아이크림': ['안티에이징', '주름케어', '집중케어'],
            '미스트': ['수분공급', '진정', '즉각케어']
        }
        
        for category_key, tags in category_mappings.items():
            if category_key in category_lower:
                generated_tags.extend(tags)
        
        return generated_tags
    
    def _generate_tags_from_brand(self, brand_name: str) -> List[str]:
        """브랜드 기반 태그 생성"""
        if not brand_name:
            return []
        
        # 브랜드별 전문성 태그
        brand_expertise = {
            '스킨1004': ['여드름케어', '민감케어', '진정'],
            '라운드랩': ['여드름케어', '자연성분', '순한'],
            '토리든': ['보습', '안티에이징', '집중케어'],
            '웰라쥬': ['보습', '진정', '수분공급'],
            '이니스프리': ['자연성분', '제주', '친환경'],
            '에뛰드하우스': ['컬러', '트렌디', '젊은'],
            '더페이스샵': ['자연성분', '기본케어', '데일리'],
            '아이오페': ['과학적', '안티에이징', '프리미엄'],
            '헤라': ['럭셔리', '안티에이징', '프리미엄'],
            '설화수': ['한방', '프리미엄', '안티에이징']
        }
        
        return brand_expertise.get(brand_name, [])
    
    def _normalize_existing_tags(self, original_tags: List[str]) -> List[str]:
        """기존 태그 정규화"""
        if not original_tags:
            return []
        
        normalized = []
        
        for tag in original_tags:
            tag = tag.strip()
            if not tag:
                continue
            
            # 표준 태그로 매핑
            standardized = self._standardize_tag(tag)
            if standardized:
                normalized.extend(standardized)
            else:
                # 매핑되지 않은 태그는 그대로 유지
                normalized.append(tag)
        
        return list(set(normalized))  # 중복 제거
    
    def _standardize_tag(self, tag: str) -> List[str]:
        """개별 태그 표준화"""
        tag_lower = tag.lower()
        
        # 모든 표준 태그 사전에서 매칭 시도
        for category, tag_groups in self.standard_taxonomy.items():
            for standard_tag, variations in tag_groups.items():
                if tag_lower in [v.lower() for v in variations] or tag_lower == standard_tag.lower():
                    return [standard_tag]
        
        return []
    
    def _merge_and_deduplicate_tags(self, normalized_tags: List[str], generated_tags: List[str]) -> List[str]:
        """태그 통합 및 중복 제거"""
        all_tags = normalized_tags + generated_tags
        
        # 중복 제거 (대소문자 무시)
        unique_tags = []
        seen_lower = set()
        
        for tag in all_tags:
            tag_lower = tag.lower()
            if tag_lower not in seen_lower:
                unique_tags.append(tag)
                seen_lower.add(tag_lower)
        
        # 태그 개수 제한 (최대 10개)
        if len(unique_tags) > 10:
            # 중요도 기반 정렬 (기존 태그 우선, 생성 태그는 빈도순)
            priority_tags = [tag for tag in unique_tags if tag in normalized_tags]
            other_tags = [tag for tag in unique_tags if tag not in normalized_tags]
            
            # 생성된 태그는 빈도 기반으로 정렬
            tag_frequency = Counter(generated_tags)
            other_tags.sort(key=lambda x: tag_frequency.get(x, 0), reverse=True)
            
            # 우선순위 태그 + 상위 생성 태그
            remaining_slots = 10 - len(priority_tags)
            unique_tags = priority_tags + other_tags[:remaining_slots]
        
        return unique_tags
    
    def _calculate_tag_confidence(self, tags: List[str], product_name: str, generated_tags: List[str]) -> Dict[str, float]:
        """태그별 신뢰도 계산"""
        confidence_scores = {}
        
        for tag in tags:
            confidence = 0.5  # 기본 신뢰도
            
            # 제품명에 관련 키워드가 있으면 신뢰도 증가
            if any(keyword in product_name.lower() for keyword in self._get_tag_keywords(tag)):
                confidence += 0.3
            
            # 여러 방법으로 생성된 태그는 신뢰도 증가
            generation_count = generated_tags.count(tag)
            if generation_count > 1:
                confidence += 0.2 * (generation_count - 1)
            
            # 표준 태그인 경우 신뢰도 증가
            if self._is_standard_tag(tag):
                confidence += 0.2
            
            confidence_scores[tag] = min(confidence, 1.0)
        
        return confidence_scores
    
    def _get_tag_keywords(self, tag: str) -> List[str]:
        """태그 관련 키워드 조회"""
        tag_lower = tag.lower()
        
        for category, tag_groups in self.standard_taxonomy.items():
            for standard_tag, variations in tag_groups.items():
                if tag_lower == standard_tag.lower():
                    return variations
        
        return [tag]
    
    def _is_standard_tag(self, tag: str) -> bool:
        """표준 태그 여부 확인"""
        tag_lower = tag.lower()
        
        for category, tag_groups in self.standard_taxonomy.items():
            if tag_lower in [standard_tag.lower() for standard_tag in tag_groups.keys()]:
                return True
        
        return False
    
    def _update_product_tags(self, product_id: int, enhanced_tags: List[str]):
        """제품 태그 데이터베이스 업데이트"""
        try:
            tags_json = json.dumps(enhanced_tags, ensure_ascii=False)
            
            update_query = "UPDATE products SET tags = ? WHERE product_id = ?"
            self.db.execute_query(update_query, (tags_json, product_id))
            
            logger.debug(f"제품 {product_id} 태그 업데이트 완료: {enhanced_tags}")
            
        except Exception as e:
            logger.error(f"제품 {product_id} 태그 업데이트 실패: {e}")
            raise
    
    def analyze_tag_quality(self) -> Dict[str, Any]:
        """전체 태그 품질 분석"""
        
        # 모든 제품의 태그 조회
        query = "SELECT product_id, name, tags FROM products WHERE tags IS NOT NULL AND tags != '[]'"
        products = self.db.execute_query(query)
        
        total_products = len(products)
        tag_stats = {
            'total_products_with_tags': total_products,
            'total_unique_tags': 0,
            'avg_tags_per_product': 0,
            'tag_frequency': Counter(),
            'quality_issues': [],
            'standardization_rate': 0
        }
        
        all_tags = []
        products_tag_counts = []
        standard_tag_count = 0
        
        for product in products:
            try:
                tags = json.loads(product['tags']) if product['tags'] else []
                if isinstance(tags, list):
                    all_tags.extend(tags)
                    products_tag_counts.append(len(tags))
                    
                    # 표준 태그 비율 계산
                    standard_count = sum(1 for tag in tags if self._is_standard_tag(tag))
                    if tags:
                        standard_tag_count += standard_count / len(tags)
            except:
                tag_stats['quality_issues'].append(f"제품 {product['product_id']}: 태그 파싱 오류")
        
        # 통계 계산
        tag_stats['total_unique_tags'] = len(set(all_tags))
        tag_stats['avg_tags_per_product'] = sum(products_tag_counts) / len(products_tag_counts) if products_tag_counts else 0
        tag_stats['tag_frequency'] = Counter(all_tags)
        tag_stats['standardization_rate'] = standard_tag_count / total_products if total_products > 0 else 0
        
        # 품질 이슈 분석
        if tag_stats['avg_tags_per_product'] < 2:
            tag_stats['quality_issues'].append("평균 태그 수가 너무 적음 (< 2개)")
        
        if tag_stats['standardization_rate'] < 0.5:
            tag_stats['quality_issues'].append("표준화 비율이 낮음 (< 50%)")
        
        # 상위 태그 분석
        tag_stats['top_tags'] = tag_stats['tag_frequency'].most_common(20)
        
        return tag_stats
    
    def generate_tag_enhancement_report(self) -> Dict[str, Any]:
        """태그 보강 리포트 생성"""
        
        # 현재 태그 품질 분석
        current_quality = self.analyze_tag_quality()
        
        # 보강 가능한 제품 수 추정
        query = """
        SELECT 
            COUNT(*) as total,
            COUNT(CASE WHEN tags IS NULL OR tags = '[]' THEN 1 END) as no_tags,
            COUNT(CASE WHEN json_array_length(tags) < 3 THEN 1 END) as few_tags
        FROM products
        """
        
        stats = self.db.execute_single(query)
        
        enhancement_potential = {
            'products_needing_tags': stats['no_tags'] if stats else 0,
            'products_needing_more_tags': stats['few_tags'] if stats else 0,
            'estimated_improvement': {
                'tag_coverage': '95%+',
                'avg_tags_per_product': '5-7개',
                'standardization_rate': '80%+'
            }
        }
        
        return {
            'current_quality': current_quality,
            'enhancement_potential': enhancement_potential,
            'recommendations': [
                "전체 제품 태그 보강 실행",
                "성분 기반 자동 태그 생성 활성화", 
                "표준 태그 사전 지속 업데이트",
                "태그 품질 모니터링 시스템 구축"
            ]
        }