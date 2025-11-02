"""
룰 서비스 (Rule Service)
PostgreSQL에서 룰 관리 및 캐싱, 의약품 별칭 해석
"""
from typing import List, Dict, Any, Optional, Tuple, Set
import logging
import json
import os
from datetime import datetime
from collections import defaultdict

logger = logging.getLogger(__name__)

class RuleService:
    """
    룰 서비스
    
    PostgreSQL 연결이 없는 환경에서도 작동하도록
    JSON 파일 기반 룰 로딩을 지원하는 견고한 구현
    """
    
    def __init__(self):
        """룰 서비스 초기화"""
        try:
            # PostgreSQL 연결 시도
            self.session = None
            self.use_postgres = False
            
            try:
                from app.database.postgres_db import get_db_session_sync
                self.session = get_db_session_sync()
                self.use_postgres = True
                # PostgreSQL 연결 성공
            except Exception as e:
                logger.warning(f"PostgreSQL 연결 실패, JSON 파일 사용: {e}")
                self.use_postgres = False
            
            # 캐시 설정
            self._eligibility_rules_cache = None
            self._scoring_rules_cache = None
            self._cache_timestamp = None
            self._cache_ttl = 300  # 5분 캐시
            
            # 의약품 별칭 매핑
            self._med_aliases = self._load_med_aliases()
            
            # 룰 파일 경로
            self.eligibility_rules_file = "eligibility_rules.json"
            self.scoring_rules_file = "scoring_rules.json"
            
            # 초기 룰 로딩
            self._load_initial_rules()
            
            # RuleService 초기화 완료
            
        except Exception as e:
            logger.error(f"RuleService 초기화 실패: {e}")
            # 초기화 실패해도 기본 동작은 가능하도록
            self.session = None
            self.use_postgres = False
            self._eligibility_rules_cache = []
            self._scoring_rules_cache = []
            self._med_aliases = {}
    
    def _load_med_aliases(self) -> Dict[str, List[str]]:
        """의약품 별칭 매핑 로딩"""
        aliases = {
            'MULTI:ANTICOAG': ['B01AA03', 'B01AB01', 'B01AC04'],  # 항응고제
            'MULTI:HTN': ['C09AA01', 'C08CA01', 'C03AA03'],       # 고혈압약
            'MULTI:DM': ['A10BA02', 'A10BB01', 'A10BF01'],        # 당뇨약
            'MULTI:STEROID': ['H02AB02', 'H02AB04', 'H02AB06'],   # 스테로이드
            'H02AB': ['H02AB02', 'H02AB04', 'H02AB06', 'H02AB'],  # 스테로이드 (직접 코드)
            'A10': ['A10BA02', 'A10BB01', 'A10BF01', 'A10'],      # 당뇨약 (직접 코드)
            'H03AA': ['H03AA01', 'H03AA02'],                      # 갑상선 저하약
            'MULTI:PREG_LACT': ['PREG', 'LACT'],                 # 임신/수유 (특수 코드)
            # 새로운 배제 룰용 의약품 코드
            'B01AA03': ['B01AA03'],                               # 와파린 (직접 코드)
            'B01AC': ['B01AC04', 'B01AC05', 'B01AC06'],          # 항혈소판제
            'L04': ['L04AA01', 'L04AA02', 'L04AB01'],            # 면역억제제
            'ANY-PHOTOSENS': ['PHOTOSENS']                        # 광과민성 약물 (특수 코드)
        }
        
        # 의약품 별칭 로딩 완료
        return aliases
    
    def _load_initial_rules(self):
        """초기 룰 로딩"""
        try:
            # 현재는 JSON 파일만 사용 (PostgreSQL 룰 로딩은 이벤트 루프 문제로 비활성화)
            self._load_rules_from_json()
        except Exception as e:
            logger.error(f"초기 룰 로딩 실패: {e}")
            # 모든 방법이 실패하면 기본 룰 생성
            self._create_default_rules()
    
    def _load_rules_from_postgres(self):
        """PostgreSQL에서 룰 로딩"""
        try:
            from app.models.postgres_models import Rule
            from app.database.postgres_db import get_postgres_db
            import asyncio
            
            # 비동기 함수를 동기적으로 실행
            async def load_rules_async():
                db = get_postgres_db()
                
                # 배제 룰 쿼리
                eligibility_query = """
                    SELECT rule_id, rule_type, medication_codes, ingredient_tag, 
                           conditions, action, penalty_score, reason, is_active,
                           created_at, updated_at
                    FROM rules 
                    WHERE rule_type = 'eligibility' AND is_active = true
                """
                eligibility_rows = await db.execute_query(eligibility_query)
                
                # 감점 룰 쿼리
                scoring_query = """
                    SELECT rule_id, rule_type, medication_codes, ingredient_tag, 
                           conditions, action, penalty_score, reason, is_active,
                           created_at, updated_at
                    FROM rules 
                    WHERE rule_type = 'scoring' AND is_active = true
                """
                scoring_rows = await db.execute_query(scoring_query)
                
                return eligibility_rows, scoring_rows
            
            # 이벤트 루프에서 실행
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 이미 실행 중인 루프가 있으면 새 스레드에서 실행
                    import concurrent.futures
                    import threading
                    
                    def run_in_thread():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(load_rules_async())
                        finally:
                            new_loop.close()
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(run_in_thread)
                        eligibility_rows, scoring_rows = future.result()
                else:
                    eligibility_rows, scoring_rows = loop.run_until_complete(load_rules_async())
            except RuntimeError:
                # 이벤트 루프가 없으면 새로 생성
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    eligibility_rows, scoring_rows = loop.run_until_complete(load_rules_async())
                finally:
                    loop.close()
            
            # Rule 객체로 변환
            eligibility_rules = [Rule.from_db_row(row) for row in eligibility_rows]
            scoring_rules = [Rule.from_db_row(row) for row in scoring_rows]
            
            self._eligibility_rules_cache = [
                self._convert_rule_to_dict(rule) for rule in eligibility_rules
            ]
            
            self._scoring_rules_cache = [
                self._convert_rule_to_dict(rule) for rule in scoring_rules
            ]
            
            self._cache_timestamp = datetime.now()
            
            # PostgreSQL 룰 로딩 완료
            
        except Exception as e:
            logger.error(f"PostgreSQL 룰 로딩 오류: {e}")
            raise
        finally:
            # 세션 정리 (비동기 함수를 동기적으로 실행)
            if session:
                try:
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # 이미 실행 중인 루프가 있으면 스케줄링
                        asyncio.create_task(session.close())
                    else:
                        loop.run_until_complete(session.close())
                except Exception as e:
                    logger.warning(f"세션 종료 중 오류 (무시됨): {e}")
    
    def _load_rules_from_json(self):
        """JSON 파일에서 룰 로딩"""
        try:
            # 배제 룰 로딩
            if os.path.exists(self.eligibility_rules_file):
                with open(self.eligibility_rules_file, 'r', encoding='utf-8') as f:
                    raw_rules = json.load(f)
                    converted_rules = [
                        self._convert_json_rule_to_standard(rule, 'eligibility') 
                        for rule in raw_rules
                    ]
                    # None 값 필터링
                    self._eligibility_rules_cache = [rule for rule in converted_rules if rule is not None]
            else:
                self._eligibility_rules_cache = []
            
            # 감점 룰 로딩
            if os.path.exists(self.scoring_rules_file):
                with open(self.scoring_rules_file, 'r', encoding='utf-8') as f:
                    raw_rules = json.load(f)
                    converted_rules = [
                        self._convert_json_rule_to_standard(rule, 'scoring') 
                        for rule in raw_rules
                    ]
                    # None 값 필터링
                    self._scoring_rules_cache = [rule for rule in converted_rules if rule is not None]
            else:
                self._scoring_rules_cache = []
            
            self._cache_timestamp = datetime.now()
            
            # JSON 룰 로딩 완료
            
        except Exception as e:
            logger.error(f"JSON 룰 로딩 오류: {e}")
            self._eligibility_rules_cache = []
            self._scoring_rules_cache = []
    
    def _convert_json_rule_to_standard(self, json_rule: Dict[str, Any], rule_type: str) -> Dict[str, Any]:
        """JSON 룰을 표준 형식으로 변환"""
        try:
            # med_code 정리 (괄호 제거)
            med_code = json_rule.get('med_code', '')
            if med_code and '(' in med_code:
                med_code = med_code.split('(')[0].strip()
            
            # action 결정
            if rule_type == 'eligibility':
                action = 'exclude'
            else:
                action = 'penalize'
            
            # weight 처리
            weight = json_rule.get('weight', 0)
            if rule_type == 'eligibility':
                weight = 0  # 배제 룰은 weight 0
            elif weight < 0:
                weight = abs(weight)  # 감점 룰은 양수로
            
            return {
                'rule_id': json_rule.get('rule_id', ''),
                'rule_type': rule_type,
                'med_code': med_code if med_code else None,
                'ingredient_tag': json_rule.get('ingredient_tag', ''),
                'condition_json': json_rule.get('condition_json', {}),
                'action': action,
                'weight': weight,
                'severity': json_rule.get('severity', 'medium'),
                'rationale_ko': json_rule.get('rationale_ko', ''),
                'citation_url': self._extract_citation_url(json_rule.get('citation_url'))
            }
            
        except Exception as e:
            logger.error(f"룰 변환 오류: {e}")
            return None
    
    def _extract_citation_url(self, citation_data) -> Optional[str]:
        """citation_url 추출"""
        if isinstance(citation_data, list) and citation_data:
            return citation_data[0]  # 첫 번째 URL 사용
        elif isinstance(citation_data, str):
            return citation_data
        return None
    
    def _create_default_rules(self):
        """기본 룰 생성 (테스트용)"""
        # 기본 배제 룰
        self._eligibility_rules_cache = [
            {
                'rule_id': 'ELG_001',
                'rule_type': 'eligibility',
                'med_code': 'B01AA03',
                'ingredient_tag': 'aha',
                'condition_json': {'leave_on': True},
                'action': 'exclude',
                'weight': 0,
                'rationale_ko': '와파린 복용 시 AHA 성분 사용 금지',
                'citation_url': None
            },
            {
                'rule_id': 'ELG_002',
                'rule_type': 'eligibility',
                'med_code': None,
                'ingredient_tag': 'retinoid',
                'condition_json': {'preg_lact': True},
                'action': 'exclude',
                'weight': 0,
                'rationale_ko': '임신/수유 중 레티노이드 사용 금지',
                'citation_url': None
            }
        ]
        
        # 기본 감점 룰
        self._scoring_rules_cache = [
            {
                'rule_id': 'SCR_001',
                'rule_type': 'scoring',
                'med_code': 'B01AA03',
                'ingredient_tag': 'bha',
                'condition_json': {},
                'action': 'penalize',
                'weight': 15,
                'severity': 'medium',
                'rationale_ko': '와파린 복용 시 BHA 성분 주의 필요',
                'citation_url': None
            },
            {
                'rule_id': 'SCR_002',
                'rule_type': 'scoring',
                'med_code': 'H02AB',
                'ingredient_tag': 'vitamin_c',
                'condition_json': {'day_use': True},
                'action': 'penalize',
                'weight': 10,
                'severity': 'low',
                'rationale_ko': '스테로이드 복용 시 비타민C 주간 사용 주의',
                'citation_url': None
            }
        ]
        
        self._cache_timestamp = datetime.now()
        
        # 기본 룰 생성 완료
    
    def _convert_rule_to_dict(self, rule) -> Dict[str, Any]:
        """룰 객체를 딕셔너리로 변환"""
        return {
            'rule_id': rule.rule_id,
            'rule_type': rule.rule_type,
            'med_code': rule.medication_codes,  # PostgreSQL 모델은 medication_codes 리스트
            'ingredient_tag': rule.ingredient_tag,
            'condition_json': rule.conditions if rule.conditions else {},
            'action': rule.action,
            'weight': rule.penalty_score if rule.penalty_score else 1.0,
            'severity': 'medium',  # 기본값
            'rationale_ko': rule.reason if rule.reason else '',
            'citation_url': []  # 기본값
        }
    
    def get_rule_statistics(self) -> Dict[str, Any]:
        """룰 통계 정보 조회"""
        try:
            eligibility_rules = self.get_cached_eligibility_rules()
            scoring_rules = self.get_cached_scoring_rules()
            
            total_rules = len(eligibility_rules) + len(scoring_rules)
            active_rules = total_rules  # 캐시된 룰은 모두 활성
            
            return {
                'total_rules': total_rules,
                'active_rules': active_rules,
                'scoring_rules': len(scoring_rules),
                'eligibility_rules': len(eligibility_rules),
                'ruleset_version': '1.0.0'
            }
            
        except Exception as e:
            logger.error(f"룰 통계 조회 오류: {e}")
            return {
                'total_rules': 0,
                'active_rules': 0,
                'scoring_rules': 0,
                'eligibility_rules': 0,
                'ruleset_version': '1.0.0'
            }
    
    def _is_cache_valid(self) -> bool:
        """캐시 유효성 검사"""
        if not self._cache_timestamp:
            return False
        
        elapsed = (datetime.now() - self._cache_timestamp).total_seconds()
        return elapsed < self._cache_ttl
    
    def get_cached_eligibility_rules(self) -> List[Dict[str, Any]]:
        """캐시된 배제 룰 조회"""
        if not self._is_cache_valid() or self._eligibility_rules_cache is None:
            try:
                if self.use_postgres:
                    self._load_rules_from_postgres()
                else:
                    self._load_rules_from_json()
            except Exception as e:
                logger.error(f"배제 룰 재로딩 실패: {e}")
                if self._eligibility_rules_cache is None:
                    self._eligibility_rules_cache = []
        
        return self._eligibility_rules_cache or []
    
    def get_cached_scoring_rules(self) -> List[Dict[str, Any]]:
        """캐시된 감점 룰 조회"""
        if not self._is_cache_valid() or self._scoring_rules_cache is None:
            try:
                if self.use_postgres:
                    self._load_rules_from_postgres()
                else:
                    self._load_rules_from_json()
            except Exception as e:
                logger.error(f"감점 룰 재로딩 실패: {e}")
                if self._scoring_rules_cache is None:
                    self._scoring_rules_cache = []
        
        return self._scoring_rules_cache or []
    
    def resolve_med_codes_batch(self, codes: List[str]) -> Dict[str, List[str]]:
        """의약품 코드 배치 해석 (양방향 매핑 지원)"""
        result = {}
        
        for code in codes:
            if code.startswith('MULTI:'):
                # 별칭 해석
                resolved = self._med_aliases.get(code, [code])
                result[code] = resolved
            else:
                # 단일 코드 -> 별칭 그룹 찾기
                resolved_codes = [code]  # 기본적으로 자기 자신 포함
                
                # 역방향 매핑: 이 코드가 포함된 별칭 그룹 찾기
                for alias_key, alias_codes in self._med_aliases.items():
                    if code in alias_codes:
                        resolved_codes.append(alias_key)
                        resolved_codes.extend(alias_codes)
                
                # 중복 제거
                result[code] = list(set(resolved_codes))
        
        return result
    
    def find_applicable_rules(self, med_codes: List[str], ingredient_tags: List[str]) -> List[Dict[str, Any]]:
        """적용 가능한 룰 찾기"""
        try:
            eligibility_rules = self.get_cached_eligibility_rules()
            scoring_rules = self.get_cached_scoring_rules()
            all_rules = eligibility_rules + scoring_rules
            
            if not all_rules:
                return []
            
            applicable = []
            
            # 의약품 코드 해석
            resolved_codes = self.resolve_med_codes_batch(med_codes)
            all_resolved_codes = set()
            for codes in resolved_codes.values():
                all_resolved_codes.update(codes)
            
            # 성분 태그 정규화
            normalized_tags = set(tag.lower().strip() for tag in ingredient_tags)
            
            for rule in all_rules:
                # 의약품 코드 매칭
                if rule.get('med_code') and rule['med_code'] in all_resolved_codes:
                    applicable.append(rule)
                    continue
                
                # 성분 태그 매칭
                if rule.get('ingredient_tag'):
                    rule_tag = rule['ingredient_tag'].lower().strip()
                    if rule_tag in normalized_tags:
                        applicable.append(rule)
                        continue
            
            logger.debug(f"적용 가능한 룰 {len(applicable)}개 발견 "
                        f"(의약품: {len(all_resolved_codes)}, 성분: {len(normalized_tags)})")
            
            return applicable
            
        except Exception as e:
            logger.error(f"적용 가능한 룰 찾기 오류: {e}")
            return []
    
    def evaluate_condition_json(self, condition_json: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """
        조건 JSON 평가 (AND 방식) - 중첩 딕셔너리 지원
        
        모든 조건이 만족되어야 True 반환
        """
        if not condition_json:
            return True  # 조건이 없으면 항상 적용
        
        try:
            return self._evaluate_nested_condition(condition_json, context)
            
        except Exception as e:
            logger.error(f"조건 JSON 평가 오류: {e}")
            return False  # 오류 시 안전하게 False 반환
    
    def _evaluate_nested_condition(self, expected: Any, actual: Any) -> bool:
        """중첩된 조건 평가"""
        if isinstance(expected, dict) and isinstance(actual, dict):
            # 딕셔너리인 경우 모든 키-값 쌍이 일치해야 함
            for key, expected_value in expected.items():
                if key not in actual:
                    return False
                
                if not self._evaluate_nested_condition(expected_value, actual[key]):
                    return False
            
            return True
            
        elif isinstance(expected, list) and isinstance(actual, list):
            # 리스트인 경우 expected의 모든 요소가 actual에 포함되어야 함
            for expected_item in expected:
                if expected_item not in actual:
                    return False
            return True
            
        elif isinstance(expected, bool):
            return bool(actual) == expected
            
        elif isinstance(expected, (int, float)):
            try:
                return float(actual) == float(expected)
            except (ValueError, TypeError):
                return False
                
        elif isinstance(expected, str):
            return str(actual) == expected
            
        else:
            # 기타 타입은 직접 비교
            return actual == expected
    
    def validate_ruleset_integrity(self) -> Dict[str, Any]:
        """룰셋 무결성 검증"""
        issues = []
        warnings = []
        
        try:
            eligibility_rules = self.get_cached_eligibility_rules()
            scoring_rules = self.get_cached_scoring_rules()
            all_rules = eligibility_rules + scoring_rules
            
            if not all_rules:
                issues.append('룰이 없습니다')
                return {
                    'is_valid': False,
                    'issues': issues,
                    'warnings': warnings
                }
            
            # 중복 rule_id 검사
            rule_ids = [rule.get('rule_id') for rule in all_rules]
            if len(rule_ids) != len(set(rule_ids)):
                issues.append('중복된 rule_id가 있습니다')
            
            # 필수 필드 검사
            for rule in all_rules:
                rule_id = rule.get('rule_id', 'unknown')
                
                # 필수 필드 확인
                if not rule.get('rule_id'):
                    issues.append(f'rule_id가 없는 룰이 있습니다')
                
                if not rule.get('rule_type'):
                    issues.append(f'rule_type이 없는 룰이 있습니다: {rule_id}')
                elif rule['rule_type'] not in ['eligibility', 'scoring']:
                    issues.append(f'잘못된 rule_type: {rule["rule_type"]} ({rule_id})')
                
                if not rule.get('action'):
                    issues.append(f'action이 없는 룰이 있습니다: {rule_id}')
                
                # 의약품 코드나 성분 태그 중 하나는 있어야 함
                if not rule.get('med_code') and not rule.get('ingredient_tag'):
                    issues.append(f'med_code나 ingredient_tag 중 하나는 있어야 합니다: {rule_id}')
                
                # 감점 룰의 경우 weight 확인
                if rule.get('rule_type') == 'scoring':
                    weight = rule.get('weight')
                    if not isinstance(weight, (int, float)) or weight <= 0:
                        issues.append(f'감점 룰의 weight가 잘못되었습니다: {rule_id}')
            
            # 경고사항 검사
            med_code_counts = defaultdict(int)
            ingredient_tag_counts = defaultdict(int)
            
            for rule in all_rules:
                if rule.get('med_code'):
                    med_code_counts[rule['med_code']] += 1
                if rule.get('ingredient_tag'):
                    ingredient_tag_counts[rule['ingredient_tag']] += 1
            
            # 중복이 많은 코드/태그 경고
            for med_code, count in med_code_counts.items():
                if count > 5:
                    warnings.append(f'의약품 코드 {med_code}에 대한 룰이 {count}개로 많습니다')
            
            for tag, count in ingredient_tag_counts.items():
                if count > 3:
                    warnings.append(f'성분 태그 {tag}에 대한 룰이 {count}개로 많습니다')
            
        except Exception as e:
            issues.append(f'무결성 검증 중 오류: {str(e)}')
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'warnings': warnings
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회"""
        return {
            'use_postgres': self.use_postgres,
            'cache_valid': self._is_cache_valid(),
            'eligibility_rules_count': len(self._eligibility_rules_cache or []),
            'scoring_rules_count': len(self._scoring_rules_cache or []),
            'med_aliases_count': len(self._med_aliases)
        }
    
    def clear_cache(self):
        """캐시 초기화"""
        self._eligibility_rules_cache = None
        self._scoring_rules_cache = None
        self._cache_timestamp = None
        # 룰 서비스 캐시 초기화
    
    def close_session(self):
        """세션 종료"""
        if self.session:
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 이미 실행 중인 루프가 있으면 스케줄링
                    asyncio.create_task(self.session.close())
                else:
                    loop.run_until_complete(self.session.close())
                # PostgreSQL 세션 종료
            except Exception as e:
                logger.error(f"세션 종료 오류: {e}")
            finally:
                self.session = None