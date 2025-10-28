#!/usr/bin/env python3
"""
샘플 제품 데이터 생성 스크립트
cosmetics.db SQLite 파일을 생성하고 기본 제품 데이터를 추가합니다.
"""
import sqlite3
import json
from datetime import datetime

def create_cosmetics_db():
    """cosmetics.db 파일 생성 및 샘플 데이터 추가"""
    
    # 데이터베이스 연결
    conn = sqlite3.connect('cosmetics.db')
    cursor = conn.cursor()
    
    # products 테이블 생성
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            product_id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            brand_name TEXT NOT NULL,
            category_code TEXT,
            category_name TEXT,
            primary_attr TEXT,
            tags TEXT,
            image_url TEXT,
            sub_product_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # 샘플 제품 데이터
    sample_products = [
        {
            'product_id': 1,
            'name': '하이드레이팅 모이스처라이저',
            'brand_name': '뷰티브랜드',
            'category_code': 'MOIST',
            'category_name': 'moisturizer',
            'primary_attr': 'hydrating',
            'tags': json.dumps(['moisturizing', 'anti-aging', 'dry-skin']),
            'image_url': 'https://example.com/product1.jpg',
            'sub_product_name': '집중 보습 크림'
        },
        {
            'product_id': 2,
            'name': '리뉴얼 안티에이징 세럼',
            'brand_name': '스킨케어',
            'category_code': 'SERUM',
            'category_name': 'serum',
            'primary_attr': 'anti-aging',
            'tags': json.dumps(['anti-aging', 'moisturizing', 'wrinkle-care']),
            'image_url': 'https://example.com/product2.jpg',
            'sub_product_name': '주름 개선 세럼'
        },
        {
            'product_id': 3,
            'name': '너리싱 나이트 크림',
            'brand_name': '프리미엄케어',
            'category_code': 'NIGHT',
            'category_name': 'night_cream',
            'primary_attr': 'nourishing',
            'tags': json.dumps(['moisturizing', 'anti-aging', 'night-care']),
            'image_url': 'https://example.com/product3.jpg',
            'sub_product_name': '야간 집중 케어'
        },
        {
            'product_id': 4,
            'name': '젠틀 클렌징 폼',
            'brand_name': '센시티브케어',
            'category_code': 'CLEAN',
            'category_name': 'cleanser',
            'primary_attr': 'gentle',
            'tags': json.dumps(['cleansing', 'sensitive-care', 'gentle']),
            'image_url': 'https://example.com/product4.jpg',
            'sub_product_name': '민감성 피부용 클렌저'
        },
        {
            'product_id': 5,
            'name': '오일 컨트롤 토너',
            'brand_name': '오일리케어',
            'category_code': 'TONER',
            'category_name': 'toner',
            'primary_attr': 'oil-control',
            'tags': json.dumps(['oil-control', 'pore-care', 'oily-skin']),
            'image_url': 'https://example.com/product5.jpg',
            'sub_product_name': '지성 피부용 토너'
        },
        {
            'product_id': 6,
            'name': '아쿠아 수딩 젤',
            'brand_name': '아쿠아브랜드',
            'category_code': 'GEL',
            'category_name': 'gel',
            'primary_attr': 'soothing',
            'tags': json.dumps(['soothing', 'sensitive-care', 'hydrating']),
            'image_url': 'https://example.com/product6.jpg',
            'sub_product_name': '진정 수분 젤'
        }
    ]
    
    # 데이터 삽입
    for product in sample_products:
        cursor.execute('''
            INSERT OR REPLACE INTO products 
            (product_id, name, brand_name, category_code, category_name, 
             primary_attr, tags, image_url, sub_product_name)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            product['product_id'],
            product['name'],
            product['brand_name'],
            product['category_code'],
            product['category_name'],
            product['primary_attr'],
            product['tags'],
            product['image_url'],
            product['sub_product_name']
        ))
    
    # 변경사항 저장
    conn.commit()
    conn.close()
    
    print(f"✅ cosmetics.db 생성 완료!")
    print(f"📦 {len(sample_products)}개 샘플 제품 추가됨")

if __name__ == "__main__":
    create_cosmetics_db()