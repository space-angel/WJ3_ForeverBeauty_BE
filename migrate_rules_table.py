"""
룰 테이블 마이그레이션 스크립트
기존 rules 테이블을 삭제하고 새로운 스키마로 재생성
"""
import importlib.util
spec = importlib.util.spec_from_file_location("database", "app/database.py")
db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db_module)

from sqlalchemy import text

def migrate_rules_table():
    """룰 테이블 마이그레이션"""
    print("=== 룰 테이블 마이그레이션 시작 ===")
    
    with db_module.engine.connect() as conn:
        # 트랜잭션 시작
        trans = conn.begin()
        
        try:
            # 1. 기존 테이블들 백업 (필요시)
            print("📋 기존 테이블 확인...")
            
            # 기존 rules 테이블 확인
            result = conn.execute(text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'rules'
                )
            """))
            old_rules_exists = result.fetchone()[0]
            
            if old_rules_exists:
                print("🗑️ 기존 rules 테이블 삭제...")
                conn.execute(text("DROP TABLE IF EXISTS rules CASCADE"))
            
            # 2. 관련 테이블들도 정리
            tables_to_drop = ['rule_hit_log', 'med_alias_map', 'recommendation_requests']
            for table in tables_to_drop:
                result = conn.execute(text(f"""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = '{table}'
                    )
                """))
                if result.fetchone()[0]:
                    print(f"🗑️ 기존 {table} 테이블 삭제...")
                    conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            
            # 트랜잭션 커밋
            trans.commit()
            print("✅ 기존 테이블 정리 완료")
            
        except Exception as e:
            trans.rollback()
            print(f"❌ 테이블 정리 실패: {e}")
            raise
    
    # 3. 새로운 테이블 생성
    print("🔨 새로운 테이블 생성...")
    db_module.create_tables()
    print("✅ 새로운 테이블 생성 완료")
    
    # 4. 테이블 확인
    print("🔍 생성된 테이블 확인...")
    with db_module.engine.connect() as conn:
        tables_to_check = ['rules', 'med_alias_map', 'rule_hit_log', 'recommendation_requests']
        
        for table_name in tables_to_check:
            result = conn.execute(text(f"""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = '{table_name}'
                )
            """))
            exists = result.fetchone()[0]
            if exists:
                print(f"✅ {table_name} 테이블 생성 확인")
                
                # 컬럼 정보 출력
                result = conn.execute(text(f"""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_name = '{table_name}' 
                    ORDER BY ordinal_position
                """))
                columns = result.fetchall()
                print(f"   컬럼: {[f'{col[0]}({col[1]})' for col in columns]}")
            else:
                print(f"❌ {table_name} 테이블 생성 실패")

if __name__ == "__main__":
    migrate_rules_table()
    print("\n🎉 마이그레이션 완료!")