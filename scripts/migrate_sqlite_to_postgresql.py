#!/usr/bin/env python3
"""
SQLite → PostgreSQL 데이터 마이그레이션 스크립트
cosmetics.db의 모든 데이터를 PostgreSQL로 이전
"""

import sqlite3
import asyncpg
import asyncio
import json
import os
import sys
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SQLiteToPostgreSQLMigrator:
    """SQLite에서 PostgreSQL로 데이터 마이그레이션"""
    
    def __init__(self, sqlite_path: str, postgres_config: Dict[str, Any]):
        self.sqlite_path = sqlite_path
        self.postgres_config = postgres_config
        self.sqlite_conn = None
        self.postgres_conn = None
        
    async def connect_databases(self):
        """데이터베이스 연결"""
        # SQLite 연결
        if not os.path.exists(self.sqlite_path):
            raise FileNotFoundError(f"SQLite 파일을 찾을 수 없습니다: {self.sqlite_path}")
        
        self.sqlite_conn = sqlite3.connect(self.sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row
        logger.info(f"SQLite 연결 완료: {self.sqlite_path}")
        
        # PostgreSQL 연결
        try:
            self.postgres_conn = await asyncpg.connect(**self.postgres_config)
            logger.info("PostgreSQL 연결 완료")
        except Exception as e:
            logger.error(f"PostgreSQL 연결 실패: {e}")
            raise
    
    async def close_connections(self):
        """데이터베이스 연결 종료"""
        if self.sqlite_conn:
            self.sqlite_conn.close()
        if self.postgres_conn:
            await self.postgres_conn.close()
    
    def parse_json_field(self, field_value: str) -> List[Any]:
        """JSON 문자열을 파싱하여 리스트로 변환"""
        if not field_value or field_value == '[]':
            return []
        
        try:
            parsed = json.loads(field_value)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    
    def convert_datetime(self, dt_str: str) -> Optional[datetime]:
        """SQLite datetime 문자열을 Python datetime으로 변환"""
        if not dt_str:
            return None
        
        try:
            # SQLite의 CURRENT_TIMESTAMP 형식 처리
            if 'T' in dt_str:
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            else:
                return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return None
    
    async def migrate_products(self):
        """제품 테이블 마이그레이션"""
        logger.info("제품 데이터 마이그레이션 시작...")
        
        # SQLite에서 데이터 조회
        cursor = self.sqlite_conn.cursor()
        cursor.execute("""
            SELECT product_id, name, brand_name, category_code, category_name,
                   primary_attr, tags, image_url, sub_product_name,
                   created_at, updated_at
            FROM products
            ORDER BY product_id
        """)
        
        products = cursor.fetchall()
        logger.info(f"SQLite에서 {len(products)}개 제품 조회 완료")
        
        # PostgreSQL에 배치 삽입
        insert_query = """
            INSERT INTO products (
                product_id, name, brand_name, category_code, category_name,
                primary_attr, tags, image_url, sub_product_name,
                created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            ON CONFLICT (product_id) DO UPDATE SET
                name = EXCLUDED.name,
                brand_name = EXCLUDED.brand_name,
                category_code = EXCLUDED.category_code,
                category_name = EXCLUDED.category_name,
                primary_attr = EXCLUDED.primary_attr,
                tags = EXCLUDED.tags,
                image_url = EXCLUDED.image_url,
                sub_product_name = EXCLUDED.sub_product_name,
                updated_at = EXCLUDED.updated_at
        """
        
        batch_data = []
        for product in products:
            # JSON 필드 변환
            tags = self.parse_json_field(product['tags'])
            created_at = self.convert_datetime(product['created_at']) or datetime.now()
            updated_at = self.convert_datetime(product['updated_at']) or datetime.now()
            
            batch_data.append((
                product['product_id'],
                product['name'],
                product['brand_name'],
                product['category_code'],
                product['category_name'],
                product['primary_attr'],
                json.dumps(tags, ensure_ascii=False),  # JSONB로 저장
                product['image_url'],
                product['sub_product_name'],
                created_at,
                updated_at
            ))
        
        await self.postgres_conn.executemany(insert_query, batch_data)
        
        # 시퀀스 업데이트
        max_id = max(product['product_id'] for product in products)
        await self.postgres_conn.execute(
            f"SELECT setval('products_product_id_seq', {max_id})"
        )
        
        logger.info(f"제품 데이터 마이그레이션 완료: {len(products)}개")
    
    async def migrate_ingredients(self):
        """성분 테이블 마이그레이션"""
        logger.info("성분 데이터 마이그레이션 시작...")
        
        cursor = self.sqlite_conn.cursor()
        cursor.execute("""
            SELECT ingredient_id, korean, english, ewg_grade, is_allergy, is_twenty,
                   skin_type_code, skin_good, skin_bad, limitation, forbidden,
                   purposes, tags, created_at, updated_at
            FROM ingredients
            ORDER BY ingredient_id
        """)
        
        ingredients = cursor.fetchall()
        logger.info(f"SQLite에서 {len(ingredients)}개 성분 조회 완료")
        
        insert_query = """
            INSERT INTO ingredients (
                ingredient_id, korean, english, ewg_grade, is_allergy, is_twenty,
                skin_type_code, skin_good, skin_bad, limitation, forbidden,
                purposes, tags, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
            ON CONFLICT (ingredient_id) DO UPDATE SET
                korean = EXCLUDED.korean,
                english = EXCLUDED.english,
                ewg_grade = EXCLUDED.ewg_grade,
                is_allergy = EXCLUDED.is_allergy,
                is_twenty = EXCLUDED.is_twenty,
                skin_type_code = EXCLUDED.skin_type_code,
                skin_good = EXCLUDED.skin_good,
                skin_bad = EXCLUDED.skin_bad,
                limitation = EXCLUDED.limitation,
                forbidden = EXCLUDED.forbidden,
                purposes = EXCLUDED.purposes,
                tags = EXCLUDED.tags,
                updated_at = EXCLUDED.updated_at
        """
        
        batch_data = []
        for ingredient in ingredients:
            # JSON 필드 변환
            purposes = self.parse_json_field(ingredient['purposes'])
            tags = self.parse_json_field(ingredient['tags']) if ingredient['tags'] else []
            created_at = self.convert_datetime(ingredient['created_at']) or datetime.now()
            updated_at = self.convert_datetime(ingredient['updated_at']) or datetime.now()
            
            batch_data.append((
                ingredient['ingredient_id'],
                ingredient['korean'],
                ingredient['english'],
                ingredient['ewg_grade'],
                bool(ingredient['is_allergy']),
                bool(ingredient['is_twenty']),
                ingredient['skin_type_code'],
                ingredient['skin_good'],
                ingredient['skin_bad'],
                ingredient['limitation'],
                ingredient['forbidden'],
                json.dumps(purposes, ensure_ascii=False),  # JSONB로 저장
                json.dumps(tags, ensure_ascii=False),      # JSONB로 저장
                created_at,
                updated_at
            ))
        
        await self.postgres_conn.executemany(insert_query, batch_data)
        
        # 시퀀스 업데이트
        max_id = max(ingredient['ingredient_id'] for ingredient in ingredients)
        await self.postgres_conn.execute(
            f"SELECT setval('ingredients_ingredient_id_seq', {max_id})"
        )
        
        logger.info(f"성분 데이터 마이그레이션 완료: {len(ingredients)}개")
    
    async def migrate_product_ingredients(self):
        """제품-성분 관계 테이블 마이그레이션"""
        logger.info("제품-성분 관계 데이터 마이그레이션 시작...")
        
        cursor = self.sqlite_conn.cursor()
        cursor.execute("""
            SELECT product_id, ingredient_id, ordinal
            FROM product_ingredients
            ORDER BY product_id, ordinal
        """)
        
        relations = cursor.fetchall()
        logger.info(f"SQLite에서 {len(relations)}개 제품-성분 관계 조회 완료")
        
        insert_query = """
            INSERT INTO product_ingredients (product_id, ingredient_id, ordinal)
            VALUES ($1, $2, $3)
            ON CONFLICT (product_id, ingredient_id) DO UPDATE SET
                ordinal = EXCLUDED.ordinal
        """
        
        batch_data = [
            (relation['product_id'], relation['ingredient_id'], relation['ordinal'])
            for relation in relations
        ]
        
        await self.postgres_conn.executemany(insert_query, batch_data)
        logger.info(f"제품-성분 관계 데이터 마이그레이션 완료: {len(relations)}개")
    
    async def migrate_goods(self):
        """상품 테이블 마이그레이션"""
        logger.info("상품 데이터 마이그레이션 시작...")
        
        cursor = self.sqlite_conn.cursor()
        cursor.execute("""
            SELECT goods_id, product_id, name, price, capacity, sale_status,
                   partner_name, thumbnail_url, created_at, updated_at
            FROM goods
            ORDER BY goods_id
        """)
        
        goods = cursor.fetchall()
        logger.info(f"SQLite에서 {len(goods)}개 상품 조회 완료")
        
        if not goods:
            logger.info("상품 데이터가 없어 마이그레이션을 건너뜁니다.")
            return
        
        insert_query = """
            INSERT INTO goods (
                goods_id, product_id, name, price, capacity, sale_status,
                partner_name, thumbnail_url, created_at, updated_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (goods_id) DO UPDATE SET
                product_id = EXCLUDED.product_id,
                name = EXCLUDED.name,
                price = EXCLUDED.price,
                capacity = EXCLUDED.capacity,
                sale_status = EXCLUDED.sale_status,
                partner_name = EXCLUDED.partner_name,
                thumbnail_url = EXCLUDED.thumbnail_url,
                updated_at = EXCLUDED.updated_at
        """
        
        batch_data = []
        for good in goods:
            created_at = self.convert_datetime(good['created_at']) or datetime.now()
            updated_at = self.convert_datetime(good['updated_at']) or datetime.now()
            
            batch_data.append((
                good['goods_id'],
                good['product_id'],
                good['name'],
                float(good['price']),
                good['capacity'],
                good['sale_status'],
                good['partner_name'],
                good['thumbnail_url'],
                created_at,
                updated_at
            ))
        
        await self.postgres_conn.executemany(insert_query, batch_data)
        
        # 시퀀스 업데이트
        max_id = max(good['goods_id'] for good in goods)
        await self.postgres_conn.execute(
            f"SELECT setval('goods_goods_id_seq', {max_id})"
        )
        
        logger.info(f"상품 데이터 마이그레이션 완료: {len(goods)}개")
    
    async def migrate_other_tables(self):
        """기타 테이블들 마이그레이션 (product_metrics, review_topics)"""
        # product_metrics 마이그레이션
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM product_metrics")
        metrics_count = cursor.fetchone()[0]
        
        if metrics_count > 0:
            logger.info(f"제품 메트릭 데이터 마이그레이션 시작... ({metrics_count}개)")
            cursor.execute("""
                SELECT product_id, rating_avg, review_count, category_overall_rank,
                       by_attribute_rank, rank_attribute_name, updated_at
                FROM product_metrics
            """)
            
            metrics = cursor.fetchall()
            insert_query = """
                INSERT INTO product_metrics (
                    product_id, rating_avg, review_count, category_overall_rank,
                    by_attribute_rank, rank_attribute_name, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (product_id) DO UPDATE SET
                    rating_avg = EXCLUDED.rating_avg,
                    review_count = EXCLUDED.review_count,
                    category_overall_rank = EXCLUDED.category_overall_rank,
                    by_attribute_rank = EXCLUDED.by_attribute_rank,
                    rank_attribute_name = EXCLUDED.rank_attribute_name,
                    updated_at = EXCLUDED.updated_at
            """
            
            batch_data = []
            for metric in metrics:
                updated_at = self.convert_datetime(metric['updated_at']) or datetime.now()
                batch_data.append((
                    metric['product_id'],
                    float(metric['rating_avg']) if metric['rating_avg'] else None,
                    metric['review_count'],
                    metric['category_overall_rank'],
                    metric['by_attribute_rank'],
                    metric['rank_attribute_name'],
                    updated_at
                ))
            
            await self.postgres_conn.executemany(insert_query, batch_data)
            logger.info(f"제품 메트릭 데이터 마이그레이션 완료: {len(metrics)}개")
        
        # review_topics 마이그레이션
        cursor.execute("SELECT COUNT(*) FROM review_topics")
        topics_count = cursor.fetchone()[0]
        
        if topics_count > 0:
            logger.info(f"리뷰 토픽 데이터 마이그레이션 시작... ({topics_count}개)")
            cursor.execute("""
                SELECT id, product_id, sentiment, name, sentence, review_count, score, updated_at
                FROM review_topics
            """)
            
            topics = cursor.fetchall()
            insert_query = """
                INSERT INTO review_topics (
                    id, product_id, sentiment, name, sentence, review_count, score, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (id) DO UPDATE SET
                    product_id = EXCLUDED.product_id,
                    sentiment = EXCLUDED.sentiment,
                    name = EXCLUDED.name,
                    sentence = EXCLUDED.sentence,
                    review_count = EXCLUDED.review_count,
                    score = EXCLUDED.score,
                    updated_at = EXCLUDED.updated_at
            """
            
            batch_data = []
            for topic in topics:
                updated_at = self.convert_datetime(topic['updated_at']) or datetime.now()
                batch_data.append((
                    topic['id'],
                    topic['product_id'],
                    topic['sentiment'],
                    topic['name'],
                    topic['sentence'],
                    topic['review_count'],
                    float(topic['score']) if topic['score'] else 0.0,
                    updated_at
                ))
            
            await self.postgres_conn.executemany(insert_query, batch_data)
            
            # 시퀀스 업데이트
            max_id = max(topic['id'] for topic in topics)
            await self.postgres_conn.execute(
                f"SELECT setval('review_topics_id_seq', {max_id})"
            )
            
            logger.info(f"리뷰 토픽 데이터 마이그레이션 완료: {len(topics)}개")
    
    async def verify_migration(self):
        """마이그레이션 검증"""
        logger.info("마이그레이션 검증 시작...")
        
        # SQLite 데이터 개수 조회
        cursor = self.sqlite_conn.cursor()
        
        sqlite_counts = {}
        tables = ['products', 'ingredients', 'product_ingredients', 'goods', 'product_metrics', 'review_topics']
        
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_counts[table] = cursor.fetchone()[0]
        
        # PostgreSQL 데이터 개수 조회
        postgres_counts = {}
        for table in tables:
            result = await self.postgres_conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            postgres_counts[table] = result
        
        # 검증 결과 출력
        logger.info("=== 마이그레이션 검증 결과 ===")
        all_match = True
        
        for table in tables:
            sqlite_count = sqlite_counts[table]
            postgres_count = postgres_counts[table]
            match = sqlite_count == postgres_count
            
            if not match:
                all_match = False
            
            status = "✓" if match else "✗"
            logger.info(f"{status} {table}: SQLite({sqlite_count}) → PostgreSQL({postgres_count})")
        
        if all_match:
            logger.info("✓ 모든 테이블 데이터가 성공적으로 마이그레이션되었습니다!")
        else:
            logger.error("✗ 일부 테이블에서 데이터 불일치가 발견되었습니다.")
        
        return all_match
    
    async def run_migration(self):
        """전체 마이그레이션 실행"""
        try:
            await self.connect_databases()
            
            # 순서대로 마이그레이션 실행
            await self.migrate_products()
            await self.migrate_ingredients()
            await self.migrate_product_ingredients()
            await self.migrate_goods()
            await self.migrate_other_tables()
            
            # 검증
            success = await self.verify_migration()
            
            if success:
                logger.info("🎉 SQLite → PostgreSQL 마이그레이션이 성공적으로 완료되었습니다!")
            else:
                logger.error("❌ 마이그레이션 중 오류가 발생했습니다.")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"마이그레이션 실패: {e}")
            return False
        finally:
            await self.close_connections()


async def main():
    """메인 실행 함수"""
    # PostgreSQL 연결 설정 (DATABASE_URL 우선, 없으면 개별 환경변수)
    database_url = os.getenv('DATABASE_URL')
    
    if database_url:
        # DATABASE_URL 파싱
        from urllib.parse import urlparse
        parsed = urlparse(database_url)
        postgres_config = {
            'host': parsed.hostname,
            'port': parsed.port or 5432,
            'database': parsed.path.lstrip('/'),
            'user': parsed.username,
            'password': parsed.password,
        }
        # SSL 설정 처리
        if 'sslmode=require' in database_url:
            postgres_config['ssl'] = 'require'
    else:
        # 개별 환경변수 사용
        postgres_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': int(os.getenv('POSTGRES_PORT', 5432)),
            'database': os.getenv('POSTGRES_DB', 'cosmetics'),
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', 'password')
        }
    
    sqlite_path = os.getenv('SQLITE_PATH', 'cosmetics.db')
    
    logger.info("SQLite → PostgreSQL 마이그레이션 시작")
    logger.info(f"SQLite 파일: {sqlite_path}")
    logger.info(f"PostgreSQL: {postgres_config['host']}:{postgres_config['port']}/{postgres_config['database']}")
    
    migrator = SQLiteToPostgreSQLMigrator(sqlite_path, postgres_config)
    success = await migrator.run_migration()
    
    if success:
        logger.info("마이그레이션이 성공적으로 완료되었습니다.")
        sys.exit(0)
    else:
        logger.error("마이그레이션이 실패했습니다.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())