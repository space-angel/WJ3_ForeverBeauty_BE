"""
JSON 룰 데이터를 PostgreSQL에 로딩하는 스크립트
scoring_rules.json과 eligibility_rules.json을 읽어서 rules 테이블에 삽입
MULTI 별칭 매핑 데이터도 생성
"""
import json
import importlib.util
from datetime import datetime, date
from typing import Dict, List, Any

# 데이터베이스 모듈 로드
spec = importlib.util.spec_from_file_location("database", "app/database.py")
db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db_module)

def load_json_file(filename: str) -> List[Dict[str, Any]]:
    """JSON 파일 로드"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ {filename} 로드 실패: {e}")
        return []

def parse_date(date_str: str) -> date:
    """날짜 문자열을 date 객체로 변환"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except:
        return None

def load_scoring_rules(db_session) -> int:
    """scoring_rules.json 데이터 로딩"""
    print("📊 scoring_rules.json 로딩 중...")
    
    scoring_data = load_json_file("scoring_rules.json")
    if not scoring_data:
        return 0
    
    loaded_count = 0
    for rule_data in scoring_data:
        try:
            rule = db_module.Rule(
                rule_id=rule_data["rule_id"],
                rule_type="scoring",
                rule_group="scoring",
                med_code=rule_data.get("med_code"),
                med_name_ko=rule_data.get("med_name_ko"),
                ingredient_tag=rule_data.get("ingredient_tag"),
                match_type="tag",  # scoring rules는 모두 tag 매칭
                condition_json=None,  # scoring rules에는 condition이 없음
                action="penalize",
                severity=rule_data.get("severity"),
                weight=rule_data.get("weight"),
                confidence="moderate",  # 기본값
                rationale_ko=rule_data.get("rationale_ko"),
                citation_source=None,
                citation_url=None,
                reviewer="시스템",
                reviewed_at=date.today(),
                expires_at=date(2026, 12, 31),  # 기본 만료일
                ruleset_version="v1.0",
                active=True
            )
            
            db_session.add(rule)
            loaded_count += 1
            
        except Exception as e:
            print(f"❌ scoring rule {rule_data.get('rule_id', 'UNKNOWN')} 로딩 실패: {e}")
    
    print(f"✅ scoring rules {loaded_count}개 로딩 완료")
    return loaded_count

def load_eligibility_rules(db_session) -> int:
    """eligibility_rules.json 데이터 로딩"""
    print("🚫 eligibility_rules.json 로딩 중...")
    
    eligibility_data = load_json_file("eligibility_rules.json")
    if not eligibility_data:
        return 0
    
    loaded_count = 0
    for rule_data in eligibility_data:
        try:
            rule = db_module.Rule(
                rule_id=rule_data["rule_id"],
                rule_type="eligibility",
                rule_group=rule_data.get("rule_group", "eligibility"),
                med_code=rule_data.get("med_code"),
                med_name_ko=rule_data.get("med_name_ko"),
                ingredient_tag=rule_data.get("ingredient_tag"),
                match_type=rule_data.get("match_type", "tag"),
                condition_json=rule_data.get("condition_json"),
                action=rule_data.get("action", "exclude"),
                severity=rule_data.get("severity"),
                weight=rule_data.get("weight"),
                confidence=rule_data.get("confidence", "moderate"),
                rationale_ko=rule_data.get("rationale_ko"),
                citation_source=rule_data.get("citation_source"),
                citation_url=rule_data.get("citation_url"),
                reviewer=rule_data.get("reviewer", "시스템"),
                reviewed_at=parse_date(rule_data.get("reviewed_at", "2025-10-27")),
                expires_at=parse_date(rule_data.get("expires_at", "2026-12-31")),
                ruleset_version=rule_data.get("ruleset_version", "v1.0"),
                active=True
            )
            
            db_session.add(rule)
            loaded_count += 1
            
        except Exception as e:
            print(f"❌ eligibility rule {rule_data.get('rule_id', 'UNKNOWN')} 로딩 실패: {e}")
    
    print(f"✅ eligibility rules {loaded_count}개 로딩 완료")
    return loaded_count

def create_multi_aliases(db_session) -> int:
    """MULTI 별칭 매핑 데이터 생성"""
    print("🔗 MULTI 별칭 매핑 생성 중...")
    
    # MULTI 별칭 정의 (설계 문서 기반)
    multi_aliases = [
        {
            "alias": "MULTI:ANTICOAG",
            "atc_codes": ["B01AA03", "B01AC06", "B01AC04", "B01AC05", "B01AC07"],
            "description": "항응고/항혈소판제 (와파린, 클로피도그렐, 아스피린 등)"
        },
        {
            "alias": "MULTI:HTN",
            "atc_codes": ["C03", "C07", "C09"],
            "description": "고혈압 치료제 (이뇨제, 베타차단제, ACE억제제 등)"
        },
        {
            "alias": "MULTI:PREG_LACT",
            "atc_codes": [],  # 특별한 ATC 코드가 아닌 상태 표시
            "description": "임신/수유 상태"
        }
    ]
    
    loaded_count = 0
    for alias_data in multi_aliases:
        try:
            alias = db_module.MedAliasMap(
                alias=alias_data["alias"],
                atc_codes=alias_data["atc_codes"],
                description=alias_data["description"]
            )
            
            db_session.add(alias)
            loaded_count += 1
            
        except Exception as e:
            print(f"❌ 별칭 {alias_data['alias']} 생성 실패: {e}")
    
    print(f"✅ MULTI 별칭 {loaded_count}개 생성 완료")
    return loaded_count

def clear_existing_data(db_session):
    """기존 룰 데이터 정리"""
    print("🧹 기존 룰 데이터 정리 중...")
    
    try:
        # 기존 룰 삭제
        deleted_rules = db_session.query(db_module.Rule).delete()
        print(f"  - 기존 룰 {deleted_rules}개 삭제")
        
        # 기존 별칭 삭제
        deleted_aliases = db_session.query(db_module.MedAliasMap).delete()
        print(f"  - 기존 별칭 {deleted_aliases}개 삭제")
        
        db_session.commit()
        print("✅ 기존 데이터 정리 완료")
        
    except Exception as e:
        print(f"❌ 기존 데이터 정리 실패: {e}")
        db_session.rollback()
        raise

def verify_loaded_data(db_session):
    """로딩된 데이터 검증"""
    print("\n🔍 로딩된 데이터 검증 중...")
    
    # 룰 통계
    total_rules = db_session.query(db_module.Rule).count()
    scoring_rules = db_session.query(db_module.Rule).filter(db_module.Rule.rule_type == "scoring").count()
    eligibility_rules = db_session.query(db_module.Rule).filter(db_module.Rule.rule_type == "eligibility").count()
    
    print(f"📊 룰 통계:")
    print(f"  - 전체 룰: {total_rules}개")
    print(f"  - 감점 룰: {scoring_rules}개")
    print(f"  - 배제 룰: {eligibility_rules}개")
    
    # 별칭 통계
    total_aliases = db_session.query(db_module.MedAliasMap).count()
    print(f"  - MULTI 별칭: {total_aliases}개")
    
    # 샘플 데이터 출력
    print(f"\n📋 샘플 룰 (처음 3개):")
    sample_rules = db_session.query(db_module.Rule).limit(3).all()
    for rule in sample_rules:
        print(f"  - {rule.rule_id}: {rule.rule_type} | {rule.med_name_ko} + {rule.ingredient_tag}")
    
    print(f"\n🔗 MULTI 별칭:")
    aliases = db_session.query(db_module.MedAliasMap).all()
    for alias in aliases:
        print(f"  - {alias.alias}: {alias.description}")
        print(f"    ATC 코드: {alias.atc_codes}")

def main():
    """메인 로딩 함수"""
    print("🚀 JSON 룰 데이터 로딩 시작\n")
    
    # 데이터베이스 세션 생성
    db_session = next(db_module.get_db())
    
    try:
        # 1. 기존 데이터 정리
        clear_existing_data(db_session)
        
        # 2. 룰 데이터 로딩
        scoring_count = load_scoring_rules(db_session)
        eligibility_count = load_eligibility_rules(db_session)
        
        # 3. MULTI 별칭 생성
        alias_count = create_multi_aliases(db_session)
        
        # 4. 커밋
        db_session.commit()
        print(f"\n💾 데이터베이스 커밋 완료")
        
        # 5. 검증
        verify_loaded_data(db_session)
        
        print(f"\n🎉 룰 데이터 로딩 완료!")
        print(f"  - 감점 룰: {scoring_count}개")
        print(f"  - 배제 룰: {eligibility_count}개")
        print(f"  - MULTI 별칭: {alias_count}개")
        
    except Exception as e:
        print(f"❌ 룰 데이터 로딩 실패: {e}")
        db_session.rollback()
        raise
    finally:
        db_session.close()

if __name__ == "__main__":
    main()