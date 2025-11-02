"""
제품 조회 서비스
PostgreSQL에서 제품 정보 조회 및 추천 시스템용 1차 필터링
"""
from typing import List, Dict, Optional, Any, Tuple
from app.database.postgres_db import get_postgres_db
from app.database.postgres_sync import get_postgres_sync_db
import json
import os
from app.models.postgres_models import Product, Ingredient, ProductIngredient, ProductWithIngredients
from app.models.request import RecommendationRequest, PriceRange
import logging

logger = logging.getLogger(__name__)

class ProductService:
    """제품 조회 서비스"""
    
    def __init__(self):
        self.db = get_postgres_db()
        self.sync_db = get_postgres_sync_db()  # 동기 DB 추가
        self._fallback_products = None
        self._use_sync = True  # 동기 연결 우선 사용
    
    def _load_fallback_products(self) -> List[Dict[str, Any]]:
        """JSON 폴백 데이터 로드"""
        if self._fallback_products is not None:
            return self._fallback_products
        
        try:
            with open('products_fallback.json', 'r', encoding='utf-8') as f:
                self._fallback_products = json.load(f)
            logger.info(f"폴백 제품 데이터 로드: {len(self._fallback_products)}개")
            return self._fallback_products
        except Exception as e:
            logger.error(f"폴백 데이터 로드 실패: {e}")
            return []
    
    def _convert_dict_to_product(self, product_dict: Dict[str, Any]) -> Product:
        """딕셔너리를 Product 객체로 변환 - Product 모델에 맞게 수정"""
        return Product(
            product_id=product_dict['product_id'],
            name=product_dict['name'],
            brand_name=product_dict['brand_name'],
            category_name=product_dict['category_name'],
            category_code=product_dict.get('category_code', ''),
            tags=product_dict.get('tags', []),
            primary_attr=product_dict.get('primary_attr'),
            image_url=product_dict.get('image_url'),
            sub_product_name=product_dict.get('sub_product_name'),
            created_at=None,
            updated_at=None
        )
    
    async def _ensure_connection(self):
        """연결 풀 상태 확인 및 재연결"""
        if not self.db.is_pool_active():
            await self.db.create_pool()
    
    async def get_products_by_category(
        self, 
        category_like: Optional[str] = None,
        limit: int = 100
    ) -> List[Product]:
        """카테고리별 제품 조회"""
        try:
            # PostgreSQL 시도
            query = "SELECT * FROM products"
            params = []
            
            if category_like:
                query += " WHERE category_name ILIKE $1 OR category_code ILIKE $2"
                params = [f"%{category_like}%", f"%{category_like}%"]
            
            query += " ORDER BY product_id LIMIT $" + str(len(params) + 1)
            params.append(limit)
            
            rows = await self.db.execute_query(query, *params)
            return [Product.from_db_row(row) for row in rows]
            
        except Exception as e:
            logger.warning(f"PostgreSQL 조회 실패, 폴백 데이터 사용: {e}")
            
            # JSON 폴백 사용
            fallback_data = self._load_fallback_products()
            products = []
            
            for product_dict in fallback_data:
                # 카테고리 필터링
                if category_like:
                    if (category_like.lower() not in product_dict['category_name'].lower() and
                        category_like.lower() not in product_dict.get('category_code', '').lower()):
                        continue
                
                products.append(self._convert_dict_to_product(product_dict))
                
                if len(products) >= limit:
                    break
            
            return products
    
    async def get_product_by_id(self, product_id: int) -> Optional[Product]:
        """제품 ID로 단일 제품 조회"""
        query = "SELECT * FROM products WHERE product_id = $1"
        try:
            row = await self.db.execute_single(query, product_id)
            return Product.from_db_row(row) if row else None
        except Exception as e:
            logger.error(f"제품 조회 오류 (ID: {product_id}): {e}")
            return None
    
    async def get_products_by_brand(self, brand_name: str, limit: int = 50) -> List[Product]:
        """브랜드별 제품 조회"""
        query = "SELECT * FROM products WHERE brand_name ILIKE $1 ORDER BY product_id LIMIT $2"
        try:
            rows = await self.db.execute_query(query, f"%{brand_name}%", limit)
            return [Product.from_db_row(row) for row in rows]
        except Exception as e:
            logger.error(f"브랜드별 제품 조회 오류: {e}")
            return []
    
    async def search_products(
        self, 
        name_keyword: Optional[str] = None,
        category_like: Optional[str] = None,
        brand_like: Optional[str] = None,
        limit: int = 100
    ) -> List[Product]:
        """제품 검색"""
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        param_count = 0
        
        if name_keyword:
            param_count += 1
            query += f" AND name ILIKE ${param_count}"
            params.append(f"%{name_keyword}%")
        
        if category_like:
            param_count += 1
            query += f" AND (category_name ILIKE ${param_count}"
            params.append(f"%{category_like}%")
            param_count += 1
            query += f" OR category_code ILIKE ${param_count})"
            params.append(f"%{category_like}%")
        
        if brand_like:
            param_count += 1
            query += f" AND brand_name ILIKE ${param_count}"
            params.append(f"%{brand_like}%")
        
        param_count += 1
        query += f" ORDER BY product_id LIMIT ${param_count}"
        params.append(limit)
        
        try:
            rows = await self.db.execute_query(query, *params)
            return [Product.from_db_row(row) for row in rows]
        except Exception as e:
            logger.error(f"제품 검색 오류: {e}")
            return []
    
    async def get_total_product_count(self) -> int:
        """전체 제품 수 조회"""
        query = "SELECT COUNT(*) as count FROM products"
        try:
            result = await self.db.execute_single(query)
            return result['count'] if result else 0
        except Exception as e:
            logger.error(f"제품 수 조회 오류: {e}")
            return 0
    
    # 추천 시스템용 메서드들
    
    async def get_candidate_products(
        self, 
        request: RecommendationRequest,
        limit: int = 1000
    ) -> List[Product]:
        """
        추천 요청에 따른 후보 제품 조회 (1차 필터링)
        카테고리, 가격 범위 기반으로 후보군 축소 - 데이터베이스 우선
        """
        # 쿼리 구성 (먼저 정의)
        query = "SELECT * FROM products WHERE 1=1"
        params = []
        param_count = 0
        
        # 카테고리 필터링
        if hasattr(request, 'categories') and request.categories:
            category_conditions = []
            for category in request.categories:
                param_count += 1
                category_conditions.append(f"(category_name ILIKE ${param_count}")
                params.append(f"%{category}%")
                param_count += 1
                category_conditions[-1] += f" OR category_code ILIKE ${param_count})"
                params.append(f"%{category}%")
            
            if category_conditions:
                query += " AND (" + " OR ".join(category_conditions) + ")"
        
        # 기본 정렬: 최신순
        param_count += 1
        query += f" ORDER BY updated_at DESC, product_id DESC LIMIT ${param_count}"
        params.append(limit)
        
        # 동기 DB 우선 시도
        if self._use_sync and self.sync_db.is_pool_active():
            try:
                return await self._get_products_sync(request, limit, query, params, param_count)
            except Exception as e:
                logger.warning(f"동기 DB 조회 실패, 비동기 DB로 전환: {e}")
                self._use_sync = False
        
        # 비동기 PostgreSQL 연결 상태 확인
        if not self.db.is_pool_active():
            logger.warning("PostgreSQL 연결 풀이 비활성 상태")
            return self._get_fallback_products(request, limit)
        
        # PostgreSQL 조회 (단순화)
        try:
            logger.debug("PostgreSQL 후보 제품 조회 시도")
            
            rows = await self.db.execute_query(query, *params)
            products = [Product.from_db_row(row) for row in rows]
            
            if products:
                logger.info(f"PostgreSQL에서 후보 제품 조회 성공: {len(products)}개")
                return products
            else:
                logger.warning("PostgreSQL에서 조건에 맞는 제품 없음 - 전체 제품 조회 시도")
                # 조건을 완화하여 재시도
                simple_query = f"SELECT * FROM products ORDER BY updated_at DESC, product_id DESC LIMIT ${param_count}"
                rows = await self.db.execute_query(simple_query, limit)
                products = [Product.from_db_row(row) for row in rows]
                if products:
                    logger.info(f"PostgreSQL에서 전체 제품 조회 성공: {len(products)}개")
                    return products
                
        except Exception as e:
            logger.warning(f"PostgreSQL 조회 실패: {e}")
        
        # PostgreSQL 실패 시에만 fallback 사용
        logger.error("PostgreSQL 조회 최종 실패 - fallback 데이터 사용")
        return self._get_fallback_products(request, limit)
    
    def _get_fallback_products(self, request: RecommendationRequest, limit: int) -> List[Product]:
        """fallback 데이터 조회 (PostgreSQL 실패 시에만 사용)"""
        fallback_data = self._load_fallback_products()
        products = []
        
        if not fallback_data:
            logger.error("fallback 데이터도 없음 - 빈 결과 반환")
            return []
        
        for product_dict in fallback_data:
            try:
                # 카테고리 필터링
                if hasattr(request, 'categories') and request.categories:
                    category_match = False
                    for category in request.categories:
                        if (category.lower() in product_dict.get('category_name', '').lower() or
                            category.lower() in product_dict.get('category_code', '').lower()):
                            category_match = True
                            break
                    if not category_match:
                        continue
                
                # 가격 필터링
                if hasattr(request, 'price_range') and request.price_range:
                    product_price = product_dict.get('price', 0)
                    if (request.price_range.min and product_price < request.price_range.min):
                        continue
                    if (request.price_range.max and product_price > request.price_range.max):
                        continue
                
                products.append(self._convert_dict_to_product(product_dict))
                
                if len(products) >= limit:
                    break
                    
            except Exception as e:
                logger.warning(f"fallback 제품 처리 오류 (건너뜀): {e}")
                continue
        
        logger.warning(f"fallback 데이터에서 후보 제품 조회: {len(products)}개")
        return products
    
    async def _get_products_sync(self, request: RecommendationRequest, limit: int, query: str, params: list, param_count: int) -> List[Product]:
        """동기 DB를 사용한 제품 조회"""
        try:
            logger.debug("PostgreSQL 동기 후보 제품 조회 시도")
            
            rows = await self.sync_db.execute_query(query, *params)
            products = [Product.from_db_row(row) for row in rows]
            
            if products:
                logger.info(f"PostgreSQL 동기에서 후보 제품 조회 성공: {len(products)}개")
                return products
            else:
                logger.warning("PostgreSQL 동기에서 조건에 맞는 제품 없음 - 전체 제품 조회 시도")
                # 조건을 완화하여 재시도
                simple_query = f"SELECT * FROM products ORDER BY updated_at DESC, product_id DESC LIMIT ${param_count}"
                rows = await self.sync_db.execute_query(simple_query, limit)
                products = [Product.from_db_row(row) for row in rows]
                if products:
                    logger.info(f"PostgreSQL 동기에서 전체 제품 조회 성공: {len(products)}개")
                    return products
                else:
                    raise Exception("동기 DB에서 제품을 찾을 수 없음")
                
        except Exception as e:
            logger.warning(f"PostgreSQL 동기 조회 실패: {e}")
            raise
    
    async def get_products_by_ids(self, product_ids: List[int]) -> List[Product]:
        """제품 ID 목록으로 제품들 조회"""
        if not product_ids:
            return []
        
        # PostgreSQL의 ANY 사용
        query = "SELECT * FROM products WHERE product_id = ANY($1)"
        
        try:
            rows = await self.db.execute_query(query, product_ids)
            products = [Product.from_db_row(row) for row in rows]
            
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
        영어-한국어 매핑을 통한 다국어 지원
        """
        if not intent_tags:
            return 50  # 기본 점수
        
        if not product.tags:
            return 30  # 태그 없는 제품은 낮은 점수
        
        # 의도 태그 매핑 임포트
        from app.config.intent_config import IntentConfig
        
        # 제품 태그 정규화 (JSONB 배열 처리)
        product_tags = product.tags if isinstance(product.tags, list) else []
        normalized_product = {tag.lower().strip() for tag in product_tags}
        
        # 의도 태그를 한국어로 확장
        expanded_intent_tags = set()
        for intent_tag in intent_tags:
            # 원본 태그 추가
            expanded_intent_tags.add(intent_tag.lower().strip())
            
            # 매핑된 한국어 태그 추가
            if intent_tag in IntentConfig.INTENT_MAPPING:
                for korean_tag in IntentConfig.INTENT_MAPPING[intent_tag]:
                    expanded_intent_tags.add(korean_tag.lower().strip())
        
        # 교집합 계산
        matches = expanded_intent_tags.intersection(normalized_product)
        match_count = len(matches)
        
        if match_count == 0:
            return 20  # 일치하는 태그 없음
        
        # 일치도 점수 계산 (0-100)
        # 완전 일치: 100점, 부분 일치: 비례 점수
        match_ratio = match_count / len(intent_tags)  # 원본 의도 태그 수 기준
        base_score = int(match_ratio * 80) + 20  # 20-100 범위
        
        # 보너스: 많은 태그가 일치할수록 추가 점수
        bonus = min(match_count * 5, 20)
        
        final_score = min(base_score + bonus, 100)
        
        logger.debug(f"의도 일치도 계산 - 제품: {product.name}, "
                    f"일치 태그: {matches}, 점수: {final_score}")
        
        return final_score
    
    async def get_product_statistics(self) -> Dict[str, Any]:
        """제품 통계 정보 조회"""
        try:
            # 전체 제품 수
            total_count = await self.get_total_product_count()
            
            # 카테고리별 통계
            category_query = """
            SELECT category_name, COUNT(*) as count 
            FROM products 
            GROUP BY category_name 
            ORDER BY count DESC 
            LIMIT 10
            """
            category_stats = await self.db.execute_query(category_query)
            
            # 브랜드별 통계
            brand_query = """
            SELECT brand_name, COUNT(*) as count 
            FROM products 
            GROUP BY brand_name 
            ORDER BY count DESC 
            LIMIT 10
            """
            brand_stats = await self.db.execute_query(brand_query)
            
            # 태그 통계 (JSONB 배열이 비어있지 않은 제품)
            tagged_query = "SELECT COUNT(*) as count FROM products WHERE tags IS NOT NULL AND jsonb_array_length(tags) > 0"
            tagged_result = await self.db.execute_single(tagged_query)
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
    
    async def validate_request_feasibility(self, request: RecommendationRequest) -> Tuple[bool, str]:
        """
        요청의 실행 가능성 검증
        후보 제품이 충분히 있는지 미리 확인
        """
        try:
            # 간단한 카운트 쿼리로 후보 수 확인
            query = "SELECT COUNT(*) as count FROM products WHERE 1=1"
            params = []
            param_count = 0
            
            if hasattr(request, 'category_like') and request.category_like:
                param_count += 1
                query += f" AND (category_name ILIKE ${param_count}"
                params.append(f"%{request.category_like}%")
                param_count += 1
                query += f" OR category_code ILIKE ${param_count})"
                params.append(f"%{request.category_like}%")
            
            # 가격 필터링 주석 처리 (DB에 price 컬럼 없음)
            # if request.price.min_price is not None:
            #     param_count += 1
            #     query += f" AND (price IS NULL OR price >= ${param_count})"
            #     params.append(request.price.min_price)
            # 
            # if request.price.max_price is not None:
            #     param_count += 1
            #     query += f" AND (price IS NULL OR price <= ${param_count})"
            #     params.append(request.price.max_price)
            
            result = await self.db.execute_single(query, *params)
            candidate_count = result['count'] if result else 0
            
            if candidate_count == 0:
                return False, "조건에 맞는 제품이 없습니다"
            
            if candidate_count < request.top_n:
                return True, f"요청한 {request.top_n}개보다 적은 {candidate_count}개 제품만 있습니다"
            
            return True, f"{candidate_count}개 후보 제품 확인"
            
        except Exception as e:
            logger.error(f"요청 실행 가능성 검증 오류: {e}")
            return False, f"검증 중 오류 발생: {str(e)}"