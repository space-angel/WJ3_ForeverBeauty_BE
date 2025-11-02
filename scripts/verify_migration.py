#!/usr/bin/env python3
"""
PostgreSQL 마이그레이션 검증 스크립트
데이터 무결성 및 일관성 검사
"""

import asyncpg
import sqlite3
import asyncio
import os
import json
import logging
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MigrationVerifier:
    """마이그레이션 검증 클래스"""
    
    def __init__(self, sqlite_path: str, postgres_config: Dict[str, Any]):
        self.sqlite_path = sqlite_path
        self.postgres_config = postgres_config
        self.sqlite_conn = None
        self.postgres_conn = None
    
    async def connect_databases(self):
        """데이터베이스 연결"""
        self.sqlite_conn = sqlite3.connect(self.sqlite_path)
        self.sqlite_conn.row_factory = sqlite3.Row
        
        self.postgres_conn = await asyncpg.connect(**self.postgres_config)
        logger.info("데이터베이스 연결 완료")
    
    async def close_connections(self):
        """연결 종료"""
        if self.sqlite_conn:
            self.sqlite_conn.close()
        if self.postgres_conn:
            await self.postgres_conn.close()
    
    async def verify_table_counts(self) -> bool:
        """테이블별 데이터 개수 검증"""
        logger.info("=== 테이블별 데이터 개수 검증 ===")
        
        tables = ['products', 'ingredients', 'product_ingredients', 'goods', 'product_metrics', 'review_topics']
        all_match = True
        
        for table in tables:
            # SQLite 개수
            cursor = self.sqlite_conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            sqlite_count = cursor.fetchone()[0]
            
            # PostgreSQL 개수
            postgres_count = await self.postgres_conn.fetchval(f"SELECT COUNT(*) FROM {table}")
            
            match = sqlite_count == postgres_count
            if not match:
                all_match = False
            
            status = "✓" if match else "✗"
            logger.info(f"{status} {table}: SQLite({sqlite_count}) = PostgreSQL({postgres_count})")
        
        return all_match
    
    async def verify_json_fields(self) -> bool:
        """JSON 필드 변환 검증"""
        logger.info("=== JSON 필드 변환 검증 ===")
        
        # products 테이블의 tags 필드 검증
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT product_id, tags FROM products WHERE tags IS NOT NULL AND tags != '[]' LIMIT 5")
        sqlite_products = cursor.fetchall()
        
        products_match = True
        for product in sqlite_products:
            product_id = product['product_id']
            sqlite_tags = product['tags']
            
            # PostgreSQL에서 조회
            postgres_tags = await self.postgres_conn.fetchval(
                "SELECT tags FROM products WHERE product_id = $1", product_id
            )
            
            # JSON 파싱 비교
            try:
                sqlite_parsed = json.loads(sqlite_tags) if sqlite_tags else []
                postgres_parsed = postgres_tags if postgres_tags else []
                
                if sqlite_parsed != postgres_parsed:
                    products_match = False
                    logger.error(f"제품 {product_id} tags 불일치: SQLite({sqlite_parsed}) != PostgreSQL({postgres_parsed})")
            except json.JSONDecodeError:
                logger.warning(f"제품 {product_id} SQLite tags JSON 파싱 실패: {sqlite_tags}")
        
        # ingredients 테이블의 purposes 필드 검증
        cursor.execute("SELECT ingredient_id, purposes FROM ingredients WHERE purposes IS NOT NULL AND purposes != '[]' LIMIT 5")
        sqlite_ingredients = cursor.fetchall()
        
        ingredients_match = True
        for ingredient in sqlite_ingredients:
            ingredient_id = ingredient['ingredient_id']
            sqlite_purposes = ingredient['purposes']
            
            postgres_purposes = await self.postgres_conn.fetchval(
                "SELECT purposes FROM ingredients WHERE ingredient_id = $1", ingredient_id
            )
            
            try:
                sqlite_parsed = json.loads(sqlite_purposes) if sqlite_purposes else []
                postgres_parsed = postgres_purposes if postgres_purposes else []
                
                if sqlite_parsed != postgres_parsed:
                    ingredients_match = False
                    logger.error(f"성분 {ingredient_id} purposes 불일치: SQLite({sqlite_parsed}) != PostgreSQL({postgres_parsed})")
            except json.JSONDecodeError:
                logger.warning(f"성분 {ingredient_id} SQLite purposes JSON 파싱 실패: {sqlite_purposes}")
        
        json_match = products_match and ingredients_match
        status = "✓" if json_match else "✗"
        logger.info(f"{status} JSON 필드 변환 검증 완료")
        
        return json_match
    
    async def verify_foreign_keys(self) -> bool:
        """외래키 무결성 검증"""
        logger.info("=== 외래키 무결성 검증 ===")
        
        # product_ingredients의 외래키 검증
        orphaned_products = await self.postgres_conn.fetchval("""
            SELECT COUNT(*) FROM product_ingredients pi
            LEFT JOIN products p ON pi.product_id = p.product_id
            WHERE p.product_id IS NULL
        """)
        
        orphaned_ingredients = await self.postgres_conn.fetchval("""
            SELECT COUNT(*) FROM product_ingredients pi
            LEFT JOIN ingredients i ON pi.ingredient_id = i.ingredient_id
            WHERE i.ingredient_id IS NULL
        """)
        
        fk_valid = orphaned_products == 0 and orphaned_ingredients == 0
        
        if fk_valid:
            logger.info("✓ 외래키 무결성 검증 통과")
        else:
            logger.error(f"✗ 외래키 무결성 오류: 고아 제품({orphaned_products}), 고아 성분({orphaned_ingredients})")
        
        return fk_valid
    
    async def verify_data_types(self) -> bool:
        """데이터 타입 검증"""
        logger.info("=== 데이터 타입 검증 ===")
        
        # Boolean 필드 검증
        boolean_check = await self.postgres_conn.fetchval("""
            SELECT COUNT(*) FROM ingredients 
            WHERE is_allergy NOT IN (true, false) OR is_twenty NOT IN (true, false)
        """)
        
        # TIMESTAMPTZ 필드 검증
        timestamp_check = await self.postgres_conn.fetchval("""
            SELECT COUNT(*) FROM products 
            WHERE created_at IS NULL OR updated_at IS NULL
        """)
        
        # EWG 등급 제약 조건 검증
        ewg_check = await self.postgres_conn.fetchval("""
            SELECT COUNT(*) FROM ingredients 
            WHERE ewg_grade IS NOT NULL 
            AND ewg_grade NOT IN ('1','1_2','2','2_3','3','4','5','6','7','8','9','10','unknown')
        """)
        
        type_valid = boolean_check == 0 and timestamp_check == 0 and ewg_check == 0
        
        if type_valid:
            logger.info("✓ 데이터 타입 검증 통과")
        else:
            logger.error(f"✗ 데이터 타입 오류: Boolean({boolean_check}), Timestamp({timestamp_check}), EWG({ewg_check})")
        
        return type_valid
    
    async def verify_indexes(self) -> bool:
        """인덱스 생성 검증"""
        logger.info("=== 인덱스 생성 검증 ===")
        
        # GIN 인덱스 확인
        gin_indexes = await self.postgres_conn.fetch("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename IN ('products', 'ingredients', 'user_profiles') 
            AND indexdef LIKE '%gin%'
        """)
        
        expected_gin_indexes = ['idx_products_tags', 'idx_ingredients_tags', 'idx_ingredients_purposes']
        found_gin_indexes = [idx['indexname'] for idx in gin_indexes]
        
        gin_valid = all(idx in found_gin_indexes for idx in expected_gin_indexes)
        
        # 일반 인덱스 확인
        all_indexes = await self.postgres_conn.fetch("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename IN ('products', 'ingredients', 'product_ingredients', 'users', 'user_preferences')
        """)
        
        index_count = len(all_indexes)
        index_valid = index_count >= 15  # 최소 15개 인덱스 예상
        
        if gin_valid and index_valid:
            logger.info(f"✓ 인덱스 생성 검증 통과 (총 {index_count}개, GIN {len(found_gin_indexes)}개)")
        else:
            logger.error(f"✗ 인덱스 생성 오류: GIN({gin_valid}), 총개수({index_valid})")
        
        return gin_valid and index_valid
    
    async def verify_sample_data(self) -> bool:
        """샘플 데이터 상세 검증"""
        logger.info("=== 샘플 데이터 상세 검증 ===")
        
        # 무작위 제품 5개 선택하여 상세 비교
        cursor = self.sqlite_conn.cursor()
        cursor.execute("SELECT product_id FROM products ORDER BY RANDOM() LIMIT 5")
        sample_product_ids = [row[0] for row in cursor.fetchall()]
        
        sample_valid = True
        
        for product_id in sample_product_ids:
            # SQLite에서 제품 정보 조회
            cursor.execute("""
                SELECT name, brand_name, category_code, tags 
                FROM products WHERE product_id = ?
            """, (product_id,))
            sqlite_product = cursor.fetchone()
            
            # PostgreSQL에서 제품 정보 조회
            postgres_product = await self.postgres_conn.fetchrow("""
                SELECT name, brand_name, category_code, tags 
                FROM products WHERE product_id = $1
            """, product_id)
            
            # 기본 필드 비교
            if (sqlite_product['name'] != postgres_product['name'] or
                sqlite_product['brand_name'] != postgres_product['brand_name'] or
                sqlite_product['category_code'] != postgres_product['category_code']):
                sample_valid = False
                logger.error(f"제품 {product_id} 기본 정보 불일치")
            
            # 해당 제품의 성분 개수 비교
            cursor.execute("SELECT COUNT(*) FROM product_ingredients WHERE product_id = ?", (product_id,))
            sqlite_ingredient_count = cursor.fetchone()[0]
            
            postgres_ingredient_count = await self.postgres_conn.fetchval(
                "SELECT COUNT(*) FROM product_ingredients WHERE product_id = $1", product_id
            )
            
            if sqlite_ingredient_count != postgres_ingredient_count:
                sample_valid = False
                logger.error(f"제품 {product_id} 성분 개수 불일치: SQLite({sqlite_ingredient_count}) != PostgreSQL({postgres_ingredient_count})")
        
        status = "✓" if sample_valid else "✗"
        logger.info(f"{status} 샘플 데이터 상세 검증 완료")
        
        return sample_valid
    
    async def run_full_verification(self) -> bool:
        """전체 검증 실행"""
        try:
            await self.connect_databases()
            
            logger.info("🔍 PostgreSQL 마이그레이션 검증 시작")
            
            # 각 검증 단계 실행
            results = []
            results.append(await self.verify_table_counts())
            results.append(await self.verify_json_fields())
            results.append(await self.verify_foreign_keys())
            results.append(await self.verify_data_types())
            results.append(await self.verify_indexes())
            results.append(await self.verify_sample_data())
            
            # 전체 결과 평가
            all_passed = all(results)
            
            logger.info("=== 최종 검증 결과 ===")
            if all_passed:
                logger.info("🎉 모든 검증을 통과했습니다! 마이그레이션이 성공적으로 완료되었습니다.")
            else:
                logger.error("❌ 일부 검증에서 실패했습니다. 마이그레이션을 다시 확인해주세요.")
            
            return all_passed
            
        except Exception as e:
            logger.error(f"검증 중 오류 발생: {e}")
            return False
        finally:
            await self.close_connections()


async def main():
    """메인 실행 함수"""
    postgres_config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': int(os.getenv('POSTGRES_PORT', 5432)),
        'database': os.getenv('POSTGRES_DB', 'cosmetics'),
        'user': os.getenv('POSTGRES_USER', 'postgres'),
        'password': os.getenv('POSTGRES_PASSWORD', 'password')
    }
    
    sqlite_path = os.getenv('SQLITE_PATH', 'cosmetics.db')
    
    verifier = MigrationVerifier(sqlite_path, postgres_config)
    success = await verifier.run_full_verification()
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)