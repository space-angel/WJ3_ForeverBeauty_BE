#!/usr/bin/env python3
"""
PostgreSQL 연결 테스트 스크립트
배포 전에 Supabase 연결 상태를 확인합니다.
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

def test_basic_connection():
    """기본 연결 테스트"""
    print("🔍 PostgreSQL 기본 연결 테스트...")
    
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("❌ DATABASE_URL 환경변수가 설정되지 않았습니다.")
        return False
    
    print(f"📡 연결 URL: {DATABASE_URL[:50]}...")
    
    try:
        # 기본 엔진 생성
        engine = create_engine(DATABASE_URL)
        
        # 연결 테스트
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            print(f"✅ 기본 연결 성공: {row}")
            return True
            
    except Exception as e:
        print(f"❌ 기본 연결 실패: {e}")
        return False

def test_optimized_connection():
    """최적화된 연결 설정 테스트"""
    print("\n🔧 최적화된 연결 설정 테스트...")
    
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    try:
        # 최적화된 엔진 생성
        engine = create_engine(
            DATABASE_URL,
            pool_size=2,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=1800,
            pool_timeout=30,
            connect_args={
                "sslmode": "require",
                "application_name": "cosmetic_test"
            }
        )
        
        # 연결 테스트
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            print(f"✅ 최적화된 연결 성공")
            print(f"📊 PostgreSQL 버전: {version[:50]}...")
            
        # 세션 테스트
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        try:
            result = session.execute(text("SELECT current_database(), current_user"))
            db_info = result.fetchone()
            print(f"🗄️  데이터베이스: {db_info[0]}, 사용자: {db_info[1]}")
            
            # 테이블 존재 확인
            result = session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('rules', 'medication_aliases')
                ORDER BY table_name
            """))
            tables = [row[0] for row in result.fetchall()]
            print(f"📋 존재하는 테이블: {tables}")
            
            return True
            
        finally:
            session.close()
            
    except Exception as e:
        print(f"❌ 최적화된 연결 실패: {e}")
        return False

def test_rule_loading():
    """실제 룰 로딩 테스트"""
    print("\n📋 룰 데이터 로딩 테스트...")
    
    try:
        from app.database.postgres_db import get_db_session_sync
        from app.models.postgres_models import Rule
        
        session = get_db_session_sync()
        
        try:
            # 룰 개수 확인
            total_rules = session.query(Rule).count()
            active_rules = session.query(Rule).filter(Rule.active == True).count()
            eligibility_rules = session.query(Rule).filter(
                Rule.rule_type == 'eligibility', Rule.active == True
            ).count()
            scoring_rules = session.query(Rule).filter(
                Rule.rule_type == 'scoring', Rule.active == True
            ).count()
            
            print(f"📊 전체 룰: {total_rules}개")
            print(f"✅ 활성 룰: {active_rules}개")
            print(f"🚫 배제 룰: {eligibility_rules}개")
            print(f"📉 감점 룰: {scoring_rules}개")
            
            # 샘플 룰 조회
            sample_rule = session.query(Rule).filter(Rule.active == True).first()
            if sample_rule:
                print(f"🔍 샘플 룰: {sample_rule.rule_id} ({sample_rule.rule_type})")
            
            return True
            
        finally:
            session.close()
            
    except Exception as e:
        print(f"❌ 룰 로딩 실패: {e}")
        return False

def main():
    """메인 테스트 실행"""
    print("🧪 PostgreSQL 연결 종합 테스트 시작\n")
    
    results = []
    
    # 1. 기본 연결 테스트
    results.append(test_basic_connection())
    
    # 2. 최적화된 연결 테스트
    results.append(test_optimized_connection())
    
    # 3. 룰 로딩 테스트
    results.append(test_rule_loading())
    
    # 결과 요약
    print(f"\n📊 테스트 결과 요약:")
    print(f"✅ 성공: {sum(results)}/{len(results)}")
    print(f"❌ 실패: {len(results) - sum(results)}/{len(results)}")
    
    if all(results):
        print("\n🎉 모든 테스트 통과! 배포 준비 완료")
        return 0
    else:
        print("\n⚠️  일부 테스트 실패. 문제 해결 후 재시도 필요")
        return 1

if __name__ == "__main__":
    sys.exit(main())