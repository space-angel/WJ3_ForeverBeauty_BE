#!/usr/bin/env python3
"""
Supabase rules 테이블 스키마 확인
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

def check_rules_table():
    """rules 테이블 구조 확인"""
    DATABASE_URL = os.getenv("DATABASE_URL")
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # 테이블 컬럼 정보 조회
        result = conn.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'rules' 
            AND table_schema = 'public'
            ORDER BY ordinal_position
        """))
        
        print("📋 rules 테이블 스키마:")
        for row in result:
            print(f"  - {row[0]}: {row[1]} (nullable: {row[2]}, default: {row[3]})")
        
        # 실제 데이터 샘플 조회
        result = conn.execute(text("SELECT * FROM rules LIMIT 3"))
        rows = result.fetchall()
        columns = result.keys()
        
        print(f"\n📊 샘플 데이터 ({len(rows)}개):")
        for i, row in enumerate(rows):
            print(f"  Row {i+1}:")
            for j, col in enumerate(columns):
                print(f"    {col}: {row[j]}")

if __name__ == "__main__":
    check_rules_table()