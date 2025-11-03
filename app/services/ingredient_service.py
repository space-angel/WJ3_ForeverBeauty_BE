"""
성분 조회 서비스
PostgreSQL에서 성분 정보 및 제품-성분 관계 조회
추천 시스템용 canonical tags 추출 및 정규화
"""
from typing import List, Dict, Optional, Any, Set, Tuple
from app.database.postgres_sync import get_postgres_sync_db
from app.models.postgres_models import Ingredient, ProductIngredient, ProductWithIngredients, Product
import logging
import json

logger = logging.getLogger(__name__)

class IngredientService:
    """성분 조회 서비스"""
    
    def __init__(self):
        self.db = get_postgres_sync_db()
    
    def get_ingredient_by_id(self, ingredient_id: int) -> Optional[Ingredient]:
        """성분 ID로 단일 성분 조회"""
        query = "SELECT * FROM ingredients WHERE ingredient_id = %s"
        try:
            rows = self.db._execute_sync(query, (ingredient_id,))
            row = rows[0] if rows else None
            return Ingredient(**row) if row else None
        except Exception as e:
            logger.error(f"성분 조회 오류 (ID: {ingredient_id}): {e}")
            return None
    
    def get_product_ingredients(self, product_id: int) -> List[Ingredient]:
        """제품의 모든 성분 조회 (순서대로)"""
        query = """
        SELECT i.* 
        FROM product_ingredients pi
        JOIN ingredients i ON pi.ingredient_id = i.ingredient_id
        WHERE pi.product_id = %s
        ORDER BY pi.ordinal
        """
        try:
            rows = self.db._execute_sync(query, (product_id,))
            return [Ingredient(**row) for row in rows]
        except Exception as e:
            logger.error(f"제품 성분 조회 오류 (Product ID: {product_id}): {e}")
            return []
    
    def get_product_with_ingredients(self, product_id: int) -> Optional[ProductWithIngredients]:
        """제품과 성분 정보를 함께 조회"""
        # 제품 정보 조회
        product_query = "SELECT * FROM products WHERE product_id = %s"
        try:
            product_rows = self.db._execute_sync(product_query, (product_id,))
            product_row = product_rows[0] if product_rows else None
            if not product_row:
                return None
            
            product = Product(**product_row)
            ingredients = self.get_product_ingredients(product_id)
            
            return ProductWithIngredients(product=product, ingredients=ingredients)
        except Exception as e:
            logger.error(f"제품+성분 조회 오류 (Product ID: {product_id}): {e}")
            return None
    
    def get_canonical_tags_for_product(self, product_id: int) -> List[str]:
        """제품의 모든 canonical tags 수집"""
        ingredients = self.get_product_ingredients(product_id)
        tags = []
        for ingredient in ingredients:
            if ingredient.tags:
                tags.extend(ingredient.tags)
        return list(set(tags))  # 중복 제거
    
    def search_ingredients_by_tag(self, tag: str) -> List[Ingredient]:
        """특정 태그를 가진 성분들 조회"""
        query = "SELECT * FROM ingredients WHERE tags LIKE %s"
        try:
            rows = self.db._execute_sync(query, (f'%"{tag}"%',))
            return [Ingredient(**row) for row in rows]
        except Exception as e:
            logger.error(f"태그별 성분 조회 오류 (Tag: {tag}): {e}")
            return []
    
    def get_products_with_ingredient_tag(self, tag: str, limit: int = 100) -> List[int]:
        """특정 성분 태그를 포함한 제품 ID 목록 조회"""
        query = """
        SELECT DISTINCT pi.product_id
        FROM product_ingredients pi
        JOIN ingredients i ON pi.ingredient_id = i.ingredient_id
        WHERE i.tags LIKE %s
        LIMIT %s
        """
        try:
            rows = self.db._execute_sync(query, (f'%"{tag}"%', limit))
            return [row['product_id'] for row in rows]
        except Exception as e:
            logger.error(f"태그별 제품 조회 오류 (Tag: {tag}): {e}")
            return []
    
    def get_ingredient_statistics(self) -> Dict[str, int]:
        """성분 통계 정보"""
        try:
            total_query = "SELECT COUNT(*) as count FROM ingredients"
            total_results = self.db._execute_sync(total_query)
            total_count = total_results[0]['count'] if total_results else 0
            
            allergy_query = "SELECT COUNT(*) as count FROM ingredients WHERE is_allergy = 1"
            allergy_results = self.db._execute_sync(allergy_query)
            allergy_count = allergy_results[0]['count'] if allergy_results else 0
            
            tagged_query = "SELECT COUNT(*) as count FROM ingredients WHERE tags IS NOT NULL AND tags != '[]'"
            tagged_results = self.db._execute_sync(tagged_query)
            tagged_count = tagged_results[0]['count'] if tagged_results else 0
            
            return {
                'total_ingredients': total_count,
                'allergy_ingredients': allergy_count,
                'tagged_ingredients': tagged_count
            }
        except Exception as e:
            logger.error(f"성분 통계 조회 오류: {e}")
            return {
                'total_ingredients': 0,
                'allergy_ingredients': 0,
                'tagged_ingredients': 0
            }
    
    # 추천 시스템용 확장 메서드들
    
    def get_canonical_tags_batch(self, product_ids: List[int]) -> Dict[int, List[str]]:
        """
        여러 제품의 canonical tags를 배치로 조회
        성능 최적화를 위한 배치 처리
        """
        if not product_ids:
            return {}
        
        # IN 절을 위한 플레이스홀더 생성
        placeholders = ','.join(['%s' for _ in product_ids])
        query = f"""
        SELECT pi.product_id, i.tags
        FROM product_ingredients pi
        JOIN ingredients i ON pi.ingredient_id = i.ingredient_id
        WHERE pi.product_id IN ({placeholders})
        AND i.tags IS NOT NULL 
        AND i.tags != '[]'
        ORDER BY pi.product_id, pi.ordinal
        """
        
        try:
            rows = self.db._execute_sync(query, tuple(product_ids))
            
            # 제품별 태그 수집
            product_tags = {}
            for row in rows:
                product_id = row['product_id']
                tags_json = row['tags']
                
                if product_id not in product_tags:
                    product_tags[product_id] = set()
                
                # JSON 태그 파싱
                try:
                    tags = json.loads(tags_json) if tags_json else []
                    if isinstance(tags, list):
                        product_tags[product_id].update(tags)
                except (json.JSONDecodeError, TypeError):
                    continue
            
            # set을 list로 변환
            result = {pid: list(tags) for pid, tags in product_tags.items()}
            
            # 요청된 모든 제품 ID에 대해 빈 리스트라도 반환
            for pid in product_ids:
                if pid not in result:
                    result[pid] = []
            
            logger.debug(f"배치 태그 조회 완료: {len(product_ids)}개 제품, "
                        f"{sum(len(tags) for tags in result.values())}개 태그")
            
            return result
            
        except Exception as e:
            logger.error(f"배치 태그 조회 오류: {e}")
            return {pid: [] for pid in product_ids}
    
    def normalize_canonical_tags(self, tags: List[str]) -> List[str]:
        """
        Canonical tags 정규화
        - 소문자 변환
        - 공백 제거
        - 중복 제거
        - 빈 태그 제거
        """
        if not tags:
            return []
        
        normalized = []
        seen = set()
        
        for tag in tags:
            if not isinstance(tag, str):
                continue
            
            # 정규화: 소문자, 공백 제거
            clean_tag = tag.lower().strip()
            
            if clean_tag and clean_tag not in seen:
                normalized.append(clean_tag)
                seen.add(clean_tag)
        
        return normalized
    
    def get_ingredient_safety_info(self, product_id: int) -> Dict[str, Any]:
        """
        제품의 성분 안전성 정보 수집
        EWG 등급, 알레르기 성분, 20대 주의 성분 등
        """
        query = """
        SELECT 
            i.ewg_grade,
            i.is_allergy,
            i.is_twenty,
            i.korean,
            i.english,
            i.skin_good,
            i.skin_bad,
            i.limitation,
            i.forbidden
        FROM product_ingredients pi
        JOIN ingredients i ON pi.ingredient_id = i.ingredient_id
        WHERE pi.product_id = %s
        ORDER BY pi.ordinal
        """
        
        try:
            rows = self.db._execute_sync(query, (product_id,))
            
            safety_info = {
                'total_ingredients': len(rows),
                'allergy_ingredients': 0,
                'twenty_ingredients': 0,
                'ewg_distribution': {},
                'high_risk_ingredients': [],
                'beneficial_ingredients': [],
                'warnings': []
            }
            
            for row in rows:
                # 알레르기 성분 카운트
                if row['is_allergy']:
                    safety_info['allergy_ingredients'] += 1
                    safety_info['high_risk_ingredients'].append({
                        'name': row['korean'],
                        'reason': '알레르기 유발 가능 성분'
                    })
                
                # 20대 주의 성분 카운트
                if row['is_twenty']:
                    safety_info['twenty_ingredients'] += 1
                    safety_info['warnings'].append(f"20대 주의 성분: {row['korean']}")
                
                # EWG 등급 분포
                ewg_grade = row['ewg_grade'] or 'unknown'
                safety_info['ewg_distribution'][ewg_grade] = safety_info['ewg_distribution'].get(ewg_grade, 0) + 1
                
                # 고위험 성분 (EWG 7-10)
                if ewg_grade in ['7', '8', '9', '10']:
                    safety_info['high_risk_ingredients'].append({
                        'name': row['korean'],
                        'reason': f'EWG 등급 {ewg_grade} (고위험)'
                    })
                
                # 유익한 성분 정보
                if row['skin_good']:
                    safety_info['beneficial_ingredients'].append({
                        'name': row['korean'],
                        'benefit': row['skin_good']
                    })
                
                # 제한사항 경고
                if row['limitation']:
                    safety_info['warnings'].append(f"사용 제한: {row['korean']} - {row['limitation']}")
                
                if row['forbidden']:
                    safety_info['warnings'].append(f"사용 금지: {row['korean']} - {row['forbidden']}")
            
            return safety_info
            
        except Exception as e:
            logger.error(f"성분 안전성 정보 조회 오류 (Product ID: {product_id}): {e}")
            return {
                'total_ingredients': 0,
                'allergy_ingredients': 0,
                'twenty_ingredients': 0,
                'ewg_distribution': {},
                'high_risk_ingredients': [],
                'beneficial_ingredients': [],
                'warnings': []
            }
    
    def find_products_by_ingredient_tags(
        self, 
        required_tags: List[str], 
        excluded_tags: List[str] = None,
        limit: int = 100
    ) -> List[int]:
        """
        특정 성분 태그 조건에 맞는 제품 ID 조회
        required_tags: 반드시 포함해야 하는 태그들
        excluded_tags: 포함하면 안 되는 태그들
        """
        if not required_tags:
            return []
        
        excluded_tags = excluded_tags or []
        
        try:
            # 필수 태그를 포함하는 제품들 조회
            required_conditions = []
            params = []
            
            for tag in required_tags:
                required_conditions.append("i.tags LIKE %s")
                params.append(f'%"{tag}"%')
            
            base_query = f"""
            SELECT DISTINCT pi.product_id
            FROM product_ingredients pi
            JOIN ingredients i ON pi.ingredient_id = i.ingredient_id
            WHERE ({' OR '.join(required_conditions)})
            """
            
            # 제외 태그가 있는 경우
            if excluded_tags:
                excluded_conditions = []
                for tag in excluded_tags:
                    excluded_conditions.append("i2.tags LIKE %s")
                    params.append(f'%"{tag}"%')
                
                base_query += f"""
                AND pi.product_id NOT IN (
                    SELECT DISTINCT pi2.product_id
                    FROM product_ingredients pi2
                    JOIN ingredients i2 ON pi2.ingredient_id = i2.ingredient_id
                    WHERE {' OR '.join(excluded_conditions)}
                )
                """
            
            base_query += f" LIMIT %s"
            params.append(limit)
            
            rows = self.db._execute_sync(base_query, tuple(params))
            product_ids = [row['product_id'] for row in rows]
            
            logger.debug(f"성분 태그 조건 검색 완료: 필수={required_tags}, "
                        f"제외={excluded_tags}, 결과={len(product_ids)}개")
            
            return product_ids
            
        except Exception as e:
            logger.error(f"성분 태그 조건 검색 오류: {e}")
            return []
    
    def get_tag_statistics(self) -> Dict[str, Any]:
        """
        Canonical tags 통계 정보
        가장 많이 사용되는 태그, 태그별 제품 수 등
        """
        try:
            # 모든 태그 수집
            query = """
            SELECT i.tags
            FROM ingredients i
            WHERE i.tags IS NOT NULL 
            AND i.tags != '[]'
            """
            
            rows = self.db._execute_sync(query)
            
            tag_counts = {}
            total_tags = 0
            
            for row in rows:
                try:
                    tags = json.loads(row['tags']) if row['tags'] else []
                    if isinstance(tags, list):
                        for tag in tags:
                            if isinstance(tag, str) and tag.strip():
                                clean_tag = tag.lower().strip()
                                tag_counts[clean_tag] = tag_counts.get(clean_tag, 0) + 1
                                total_tags += 1
                except (json.JSONDecodeError, TypeError):
                    continue
            
            # 상위 태그들
            top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:20]
            
            return {
                'total_unique_tags': len(tag_counts),
                'total_tag_instances': total_tags,
                'top_tags': [tag for tag, count in top_tags],
                'avg_tags_per_ingredient': round(total_tags / len(rows), 2) if rows else 0
            }
            
        except Exception as e:
            logger.error(f"태그 통계 조회 오류: {e}")
            return {
                'total_unique_tags': 0,
                'total_tag_instances': 0,
                'top_tags': [],
                'avg_tags_per_ingredient': 0
            }