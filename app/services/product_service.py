"""
제품 조회 서비스
SQLite cosmetics.db에서 제품 정보 조회 및 추천 시스템용 1차 필터링
"""
from typing import List, Dict, Optional, Any, Tuple
from app.database.sqlite_db import get_sqlite_db
from app.models.sqlite_models import Product, Ingredient, ProductIngredient, ProductWithIngredients
from app.models.request import RecommendationRequest, PriceRange
import logging

logger = logging.getLogger(__name__)

class ProductService:
    """제품 조회 서비스"""
    
    def __init__(self):
        self.db = get_sqlite_db()
    
    def get_products_by_category(
        self, 
        category_like: Optional[str] = None,
        limit: int = 100
    ) -> List[Product]:
        """카테고리별 제품 조회"""
        query = "SELECT * FROM products"
        params = ()
        
        if category_like:
            query += " WHERE category_name LIKE ? OR category_code LIKE ?"
            params = (f"%{category_like}%", f"%{category_like}%")
        
        query += " ORDER BY product_id LIMIT ?"
        params = params + (limit,)
        
        try:
            rows = self.db.execute_query(query, params)
            return [Product(**row) for row in rows]
        except Exception as e:
            logger.error(f"제품 조회 오류: {e}")
            return []
    
    def get_product_by_id(self, product_id: int) -> Optional[Product]:
        """제품 ID로 단일 제품 조회"""
        query = "SELECT * FROM products WHERE product_id = ?"
        try:
            row = self.db.execute_single(query, (product_id,))
            return Product(**row) if row else None
        except Exception as e:
            logger.error(f"제품 조회 오류 (ID: {product_id}): {e}")
            return None
    
    def get_products_by_brand(self, brand_name: str, limit: int = 50) -> List[Product]:
        """브랜드별 제품 조회"""
        query = "SELECT * FROM products WHERE brand_name LIKE ? ORDER BY product_id LIMIT ?"
        try:
            rows = self.db.execute_query(query, (f"%{brand_name}%", limit))
            return [Product(**row) for row in rows]
        except Exception as e:
            logger.error(f"브랜드별 제품 조회 오류: {e}")
            return []
    
    def search_products(
        self, 
        name_keyword: Optional[str] = None,
        category_like: Optional[str] = None,
        brand_like: Optional[str] = None,
        limit: int = 100
    ) -> List[Product]:
        """제품 검색"""
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        
        if name_keyword:
            query += " AND name LIKE ?"
            params.append(f"%{name_keyword}%")
        
        if category_like:
            query += " AND (category_name LIKE ? OR category_code LIKE ?)"
            params.extend([f"%{category_like}%", f"%{category_like}%"])
        
        if brand_like:
            query += " AND brand_name LIKE ?"
            params.append(f"%{brand_like}%")
        
        query += " ORDER BY product_id LIMIT ?"
        params.append(limit)
        
        try:
            rows = self.db.execute_query(query, tuple(params))
            return [Product(**row) for row in rows]
        except Exception as e:
            logger.error(f"제품 검색 오류: {e}")
            return []
    
    def get_total_product_count(self) -> int:
        """전체 제품 수 조회"""
        query = "SELECT COUNT(*) as count FROM products"
        try:
            result = self.db.execute_single(query)
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"제품 수 조회 오류: {e}")
            return 0
    
    # 추천 시스템용 메서드들
    
    def get_candidate_products(
        self, 
        request: RecommendationRequest,
        limit: int = 1000
    ) -> List[Product]:
        """
        추천 요청에 따른 후보 제품 조회 (1차 필터링)
        카테고리, 가격 범위 기반으로 후보군 축소
        """
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        
        # 카테고리 필터링
        if request.category_like:
            query += " AND (category_name LIKE ? OR category_code LIKE ?)"
            params.extend([f"%{request.category_like}%", f"%{request.category_like}%"])
        
        # 가격 필터링 (가격 정보가 있는 경우) - 현재 DB에 price 컬럼이 없으므로 주석 처리
        # if request.price.min_price is not None:
        #     query += " AND (price IS NULL OR price >= ?)"
        #     params.append(request.price.min_price)
        # 
        # if request.price.max_price is not None:
        #     query += " AND (price IS NULL OR price <= ?)"
        #     params.append(request.price.max_price)
        
        # 기본 정렬: 최신순
        query += " ORDER BY updated_at DESC, product_id DESC LIMIT ?"
        params.append(limit)
        
        try:
            rows = self.db.execute_query(query, tuple(params))
            products = [Product(**row) for row in rows]
            
            logger.info(f"후보 제품 조회 완료: {len(products)}개 (카테고리: {request.category_like})")
            return products
            
        except Exception as e:
            logger.error(f"후보 제품 조회 오류: {e}")
            return []
    
    def get_products_by_ids(self, product_ids: List[int]) -> List[Product]:
        """제품 ID 목록으로 제품들 조회"""
        if not product_ids:
            return []
        
        # IN 절을 위한 플레이스홀더 생성
        placeholders = ','.join(['?' for _ in product_ids])
        query = f"SELECT * FROM products WHERE product_id IN ({placeholders})"
        
        try:
            rows = self.db.execute_query(query, tuple(product_ids))
            products = [Product(**row) for row in rows]
            
            # 원래 순서 유지
            product_dict = {p.product_id: p for p in products}
            ordered_products = [product_dict[pid] for pid in product_ids if pid in product_dict]
            
            return ordered_products
            
        except Exception as e:
            logger.error(f"제품 ID 목록 조회 오류: {e}")
            return []
    
    def calculate_intent_match_score(
        self, 
        product: Product, 
        intent_tags: List[str]
    ) -> int:
        """
        제품과 의도 태그 간의 일치도 점수 계산
        제품 태그와 의도 태그의 교집합 기반으로 점수 산출
        """
        if not intent_tags:
            return 50  # 기본 점수
        
        if not product.tags:
            return 30  # 태그 없는 제품은 낮은 점수
        
        # 태그 정규화 (소문자, 공백 제거)
        normalized_intent = {tag.lower().strip() for tag in intent_tags}
        normalized_product = {tag.lower().strip() for tag in product.tags}
        
        # 교집합 계산
        matches = normalized_intent.intersection(normalized_product)
        match_count = len(matches)
        
        if match_count == 0:
            return 20  # 일치하는 태그 없음
        
        # 일치도 점수 계산 (0-100)
        # 완전 일치: 100점, 부분 일치: 비례 점수
        match_ratio = match_count / len(normalized_intent)
        base_score = int(match_ratio * 80) + 20  # 20-100 범위
        
        # 보너스: 많은 태그가 일치할수록 추가 점수
        bonus = min(match_count * 5, 20)
        
        final_score = min(base_score + bonus, 100)
        
        logger.debug(f"의도 일치도 계산 - 제품: {product.name}, "
                    f"일치 태그: {matches}, 점수: {final_score}")
        
        return final_score
    
    def get_product_statistics(self) -> Dict[str, Any]:
        """제품 통계 정보 조회"""
        try:
            # 전체 제품 수
            total_count = self.get_total_product_count()
            
            # 카테고리별 통계
            category_query = """
            SELECT category_name, COUNT(*) as count 
            FROM products 
            GROUP BY category_name 
            ORDER BY count DESC 
            LIMIT 10
            """
            category_stats = self.db.execute_query(category_query)
            
            # 브랜드별 통계
            brand_query = """
            SELECT brand_name, COUNT(*) as count 
            FROM products 
            GROUP BY brand_name 
            ORDER BY count DESC 
            LIMIT 10
            """
            brand_stats = self.db.execute_query(brand_query)
            
            # 태그 통계 (태그가 있는 제품)
            tagged_query = "SELECT COUNT(*) as count FROM products WHERE tags != '[]' AND tags IS NOT NULL"
            tagged_result = self.db.execute_single(tagged_query)
            tagged_count = tagged_result['count'] if tagged_result else 0
            
            return {
                'total_products': total_count,
                'tagged_products': tagged_count,
                'top_categories': [dict(row) for row in category_stats],
                'top_brands': [dict(row) for row in brand_stats],
                'tag_coverage_percent': round((tagged_count / total_count * 100), 2) if total_count > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"제품 통계 조회 오류: {e}")
            return {
                'total_products': 0,
                'tagged_products': 0,
                'top_categories': [],
                'top_brands': [],
                'tag_coverage_percent': 0
            }
    
    def validate_request_feasibility(self, request: RecommendationRequest) -> Tuple[bool, str]:
        """
        요청의 실행 가능성 검증
        후보 제품이 충분히 있는지 미리 확인
        """
        try:
            # 간단한 카운트 쿼리로 후보 수 확인
            query = "SELECT COUNT(*) as count FROM products WHERE 1=1"
            params = []
            
            if request.category_like:
                query += " AND (category_name LIKE ? OR category_code LIKE ?)"
                params.extend([f"%{request.category_like}%", f"%{request.category_like}%"])
            
            # 가격 필터링 주석 처리 (DB에 price 컬럼 없음)
            # if request.price.min_price is not None:
            #     query += " AND (price IS NULL OR price >= ?)"
            #     params.append(request.price.min_price)
            # 
            # if request.price.max_price is not None:
            #     query += " AND (price IS NULL OR price <= ?)"
            #     params.append(request.price.max_price)
            
            result = self.db.execute_single(query, tuple(params))
            candidate_count = result['count'] if result else 0
            
            if candidate_count == 0:
                return False, "조건에 맞는 제품이 없습니다"
            
            if candidate_count < request.top_n:
                return True, f"요청한 {request.top_n}개보다 적은 {candidate_count}개 제품만 있습니다"
            
            return True, f"{candidate_count}개 후보 제품 확인"
            
        except Exception as e:
            logger.error(f"요청 실행 가능성 검증 오류: {e}")
            return False, f"검증 중 오류 발생: {str(e)}"