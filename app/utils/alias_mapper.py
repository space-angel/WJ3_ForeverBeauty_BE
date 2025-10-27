"""
별칭 매퍼 (Alias Mapper)
MULTI:ANTICOAG, MULTI:HTN, MULTI:PREG_LACT 매핑
ATC 코드 배열 해석 및 캐싱
"""
from typing import Dict, List, Set, Optional, Any
from app.services.rule_service import RuleService
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AliasMapper:
    """별칭 매핑 관리 클래스"""
    
    def __init__(self):
        self.rule_service = RuleService()
        self._alias_cache: Dict[str, List[str]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = 3600  # 1시간 캐시
        
        # 기본 별칭 정의 (DB에서 로드되지 않을 경우 사용)
        self._default_aliases = {
            "MULTI:ANTICOAG": [
                "B01AA03",  # 와파린
                "B01AC06",  # 클로피도그렐
                "B01AC04",  # 아스피린 (항혈소판)
                "B01AC05",  # 티클로피딘
                "B01AC07",  # 디피리다몰
                "B01AC22",  # 프라수그렐
                "B01AC24",  # 티카그렐로
                "B01AE07",  # 다비가트란
                "B01AF01",  # 리바록사반
                "B01AF02",  # 아픽사반
                "B01AF03"   # 에독사반
            ],
            "MULTI:HTN": [
                "C03",      # 이뇨제 (전체)
                "C07",      # 베타차단제 (전체)
                "C09",      # ACE억제제/ARB (전체)
                "C08",      # 칼슘채널차단제 (전체)
                "C02"       # 기타 고혈압 치료제
            ],
            "MULTI:PREG_LACT": [
                # 임신/수유는 특별한 상태이므로 ATC 코드가 아닌 상태 표시
                "PREGNANCY",
                "LACTATION"
            ]
        }
    
    def _is_cache_valid(self) -> bool:
        """캐시 유효성 검사"""
        if self._cache_timestamp is None:
            return False
        
        elapsed = datetime.now() - self._cache_timestamp
        return elapsed.total_seconds() < self._cache_ttl
    
    def _refresh_cache(self):
        """캐시 갱신"""
        try:
            logger.info("별칭 매핑 캐시 갱신 시작")
            
            # DB에서 별칭 매핑 로드
            db_aliases = self.rule_service.get_cached_alias_map()
            
            # DB 데이터와 기본 데이터 병합
            self._alias_cache = self._default_aliases.copy()
            self._alias_cache.update(db_aliases)
            
            self._cache_timestamp = datetime.now()
            
            logger.info(f"별칭 매핑 캐시 갱신 완료: {len(self._alias_cache)}개 별칭")
            
        except Exception as e:
            logger.error(f"별칭 매핑 캐시 갱신 실패: {e}")
            # 실패 시 기본 별칭만 사용
            self._alias_cache = self._default_aliases.copy()
            self._cache_timestamp = datetime.now()
    
    def get_alias_mapping(self) -> Dict[str, List[str]]:
        """전체 별칭 매핑 조회"""
        if not self._is_cache_valid():
            self._refresh_cache()
        
        return self._alias_cache.copy()
    
    def resolve_alias(self, alias: str) -> List[str]:
        """
        단일 별칭을 ATC 코드 목록으로 해석
        """
        if not alias.startswith("MULTI:"):
            return [alias]  # MULTI가 아니면 그대로 반환
        
        if not self._is_cache_valid():
            self._refresh_cache()
        
        resolved_codes = self._alias_cache.get(alias, [alias])
        
        logger.debug(f"별칭 해석: {alias} → {resolved_codes}")
        
        return resolved_codes
    
    def resolve_aliases_batch(self, aliases: List[str]) -> Dict[str, List[str]]:
        """
        여러 별칭을 배치로 해석
        """
        if not self._is_cache_valid():
            self._refresh_cache()
        
        result = {}
        
        for alias in aliases:
            if alias.startswith("MULTI:"):
                result[alias] = self._alias_cache.get(alias, [alias])
            else:
                result[alias] = [alias]
        
        logger.debug(f"배치 별칭 해석: {len(aliases)}개 → {sum(len(codes) for codes in result.values())}개 코드")
        
        return result
    
    def expand_med_codes(self, med_codes: List[str]) -> Set[str]:
        """
        의약품 코드 목록을 확장하여 모든 실제 ATC 코드 반환
        """
        expanded_codes = set()
        
        for code in med_codes:
            resolved = self.resolve_alias(code)
            expanded_codes.update(resolved)
        
        logger.debug(f"의약품 코드 확장: {len(med_codes)}개 → {len(expanded_codes)}개")
        
        return expanded_codes
    
    def is_multi_alias(self, code: str) -> bool:
        """코드가 MULTI 별칭인지 확인"""
        return code.startswith("MULTI:")
    
    def get_supported_aliases(self) -> List[str]:
        """지원되는 모든 MULTI 별칭 목록"""
        if not self._is_cache_valid():
            self._refresh_cache()
        
        return [alias for alias in self._alias_cache.keys() if alias.startswith("MULTI:")]
    
    def validate_alias(self, alias: str) -> bool:
        """별칭이 유효한지 검증"""
        if not alias.startswith("MULTI:"):
            return True  # MULTI가 아니면 유효하다고 가정
        
        if not self._is_cache_valid():
            self._refresh_cache()
        
        return alias in self._alias_cache
    
    def get_alias_description(self, alias: str) -> Optional[str]:
        """별칭에 대한 설명 반환"""
        descriptions = {
            "MULTI:ANTICOAG": "항응고/항혈소판제 (와파린, 클로피도그렐, 아스피린 등)",
            "MULTI:HTN": "고혈압 치료제 (이뇨제, 베타차단제, ACE억제제 등)",
            "MULTI:PREG_LACT": "임신/수유 상태"
        }
        
        return descriptions.get(alias)
    
    def get_alias_statistics(self) -> Dict[str, Any]:
        """별칭 매핑 통계"""
        if not self._is_cache_valid():
            self._refresh_cache()
        
        total_aliases = len(self._alias_cache)
        multi_aliases = len([a for a in self._alias_cache.keys() if a.startswith("MULTI:")])
        total_codes = sum(len(codes) for codes in self._alias_cache.values())
        
        # 별칭별 코드 수
        alias_code_counts = {
            alias: len(codes) 
            for alias, codes in self._alias_cache.items() 
            if alias.startswith("MULTI:")
        }
        
        return {
            'total_aliases': total_aliases,
            'multi_aliases': multi_aliases,
            'total_expanded_codes': total_codes,
            'alias_code_counts': alias_code_counts,
            'cache_timestamp': self._cache_timestamp.isoformat() if self._cache_timestamp else None,
            'cache_age_seconds': (datetime.now() - self._cache_timestamp).total_seconds() if self._cache_timestamp else None
        }
    
    def find_aliases_for_code(self, atc_code: str) -> List[str]:
        """
        특정 ATC 코드를 포함하는 MULTI 별칭들 찾기
        """
        if not self._is_cache_valid():
            self._refresh_cache()
        
        matching_aliases = []
        
        for alias, codes in self._alias_cache.items():
            if alias.startswith("MULTI:") and atc_code in codes:
                matching_aliases.append(alias)
        
        return matching_aliases
    
    def get_overlap_analysis(self, med_codes: List[str]) -> Dict[str, Any]:
        """
        의약품 코드들 간의 중복 분석
        """
        expanded_sets = {}
        
        for code in med_codes:
            expanded_sets[code] = set(self.resolve_alias(code))
        
        # 전체 고유 코드 수
        all_codes = set()
        for codes in expanded_sets.values():
            all_codes.update(codes)
        
        # 중복 분석
        overlaps = {}
        for i, code1 in enumerate(med_codes):
            for code2 in med_codes[i+1:]:
                overlap = expanded_sets[code1].intersection(expanded_sets[code2])
                if overlap:
                    overlaps[f"{code1} ∩ {code2}"] = list(overlap)
        
        return {
            'input_codes': med_codes,
            'expanded_sets': {k: list(v) for k, v in expanded_sets.items()},
            'total_unique_codes': len(all_codes),
            'overlaps': overlaps,
            'has_overlaps': len(overlaps) > 0
        }
    
    def close(self):
        """리소스 정리"""
        if self.rule_service:
            self.rule_service.close_session()