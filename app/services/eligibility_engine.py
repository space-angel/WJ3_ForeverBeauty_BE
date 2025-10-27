"""
배제 엔진 (Eligibility Engine)
의약품-성분 상호작용 및 사용 맥락 기반 제품 배제 처리
"""
from typing import List, Dict, Any, Optional, Set, Tuple
from uuid import UUID
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import logging
import time
from datetime import datetime

from app.services.rule_service import RuleService
from app.services.ingredient_service import IngredientService
from app.models.request import RecommendationRequest
from app.models.sqlite_models import Product
from app.models.response import RuleHit

logger = logging.getLogger(__name__)

@dataclass
class EligibilityResult:
    """배제 평가 결과"""
    request_id: UUID
    total_evaluated: int = 0
    total_excluded: int = 0
    excluded_products: Set[int] = field(default_factory=set)
    exclusion_reasons: Dict[int, List[str]] = field(default_factory=dict)
    rule_hits: List[RuleHit] = field(default_factory=list)
    evaluation_time_ms: float = 0.0
    rules_applied: int = 0
    
    def add_exclusion(self, product_id: int, rule_hit: RuleHit, reason: str):
        """제품 배제 추가"""
        if product_id not in self.excluded_products:
            self.excluded_products.add(product_id)
            self.total_excluded += 1
            self.exclusion_reasons[product_id] = []
        
        self.exclusion_reasons[product_id].append(reason)
        self.rule_hits.append(rule_hit)

class EligibilityEngine:
    """
    배제 엔진
    
    의약품-성분 상호작용 룰과 사용 맥락 조건을 기반으로
    안전하지 않은 제품들을 즉시 배제하는 엔진
    """
    
    def __init__(self):
        """배제 엔진 초기화"""
        try:
            self.rule_service = RuleService()
            self.ingredient_service = IngredientService()
            self._eligibility_rules_cache = None
            self._cache_timestamp = None
            self._cache_ttl = 300  # 5분 캐시
            
            # 성능 모니터링
            self._evaluation_count = 0
            self._total_evaluation_time = 0.0
            
            logger.info("EligibilityEngine 초기화 완료")
            
        except Exception as e:
            logger.error(f"EligibilityEngine 초기화 실패: {e}")
            raise RuntimeError(f"배제 엔진 초기화 실패: {e}")
    
    def _load_eligibility_rules(self) -> List[Dict[str, Any]]:
        """배제 룰 로딩 (캐시 포함)"""
        current_time = datetime.now()
        
        # 캐시 유효성 검사
        if (self._eligibility_rules_cache is not None and 
            self._cache_timestamp is not None and
            (current_time - self._cache_timestamp).total_seconds() < self._cache_ttl):
            return self._eligibility_rules_cache
        
        try:
            # 룰 서비스에서 배제 룰 조회
            rules = self.rule_service.get_cached_eligibility_rules()
            
            # 룰 유효성 검증
            validated_rules = []
            for rule in rules:
                if self._validate_rule_structure(rule):
                    validated_rules.append(rule)
                else:
                    logger.warning(f"잘못된 룰 구조 무시: {rule.get('rule_id', 'unknown')}")
            
            self._eligibility_rules_cache = validated_rules
            self._cache_timestamp = current_time
            
            logger.info(f"배제 룰 로딩 완료: {len(validated_rules)}개 룰")
            return validated_rules
            
        except Exception as e:
            logger.error(f"배제 룰 로딩 실패: {e}")
            # 캐시된 룰이 있으면 그것을 사용
            if self._eligibility_rules_cache is not None:
                logger.warning("캐시된 룰 사용")
                return self._eligibility_rules_cache
            return []
    
    def _validate_rule_structure(self, rule: Dict[str, Any]) -> bool:
        """룰 구조 유효성 검증"""
        if not rule:
            return False
        
        required_fields = ['rule_id', 'rule_type', 'action']
        
        for field in required_fields:
            if field not in rule or not rule[field]:
                return False
        
        # rule_type이 eligibility인지 확인
        if rule['rule_type'] != 'eligibility':
            return False
        
        # action이 exclude인지 확인
        if rule['action'] != 'exclude':
            return False
        
        # med_code나 ingredient_tag 중 하나는 있어야 함
        if not rule.get('med_code') and not rule.get('ingredient_tag'):
            return False
        
        return True
    
    def evaluate_products(
        self, 
        products: List[Product], 
        request: RecommendationRequest,
        request_id: UUID
    ) -> EligibilityResult:
        """
        제품 배제 평가 수행
        
        Args:
            products: 평가할 제품 목록
            request: 추천 요청
            request_id: 요청 ID
            
        Returns:
            EligibilityResult: 배제 평가 결과
        """
        start_time = time.time()
        
        # 입력 유효성 검증
        if not products:
            logger.warning("평가할 제품이 없습니다")
            return EligibilityResult(
                request_id=request_id,
                total_evaluated=0,
                evaluation_time_ms=0.0
            )
        
        if not request:
            raise ValueError("추천 요청이 없습니다")
        
        result = EligibilityResult(
            request_id=request_id,
            total_evaluated=len(products)
        )
        
        try:
            # 배제 룰 로딩
            eligibility_rules = self._load_eligibility_rules()
            if not eligibility_rules:
                logger.warning("배제 룰이 없습니다. 모든 제품 통과")
                result.evaluation_time_ms = (time.time() - start_time) * 1000
                return result
            
            # 제품별 성분 태그 배치 로딩
            product_ids = [p.product_id for p in products]
            product_tags = self.ingredient_service.get_canonical_tags_batch(product_ids)
            
            # 의약품 코드 해석
            med_codes = request.med_profile.codes if request.med_profile else []
            resolved_med_codes = self.rule_service.resolve_med_codes_batch(med_codes)
            all_med_codes = set()
            for codes in resolved_med_codes.values():
                all_med_codes.update(codes)
            
            # 사용 맥락 추출
            use_context = self._extract_use_context(request)
            
            # 각 제품에 대해 배제 평가
            for product in products:
                if product.product_id in result.excluded_products:
                    continue  # 이미 배제된 제품
                
                product_ingredient_tags = product_tags.get(product.product_id, [])
                
                # 적용 가능한 룰 찾기
                applicable_rules = self._find_applicable_rules(
                    eligibility_rules, all_med_codes, product_ingredient_tags
                )
                
                # 각 룰에 대해 평가
                for rule in applicable_rules:
                    if self._evaluate_rule_conditions(rule, use_context):
                        # 배제 조건 만족 - 제품 배제
                        rule_hit = RuleHit(
                            type='exclude',
                            rule_id=rule['rule_id'],
                            weight=rule.get('weight', 0),
                            rationale_ko=rule.get('rationale_ko', '안전성 우려'),
                            citation_url=rule.get('citation_url')
                        )
                        
                        reason = self._generate_exclusion_reason(rule, request)
                        result.add_exclusion(product.product_id, rule_hit, reason)
                        result.rules_applied += 1
                        
                        logger.debug(f"제품 {product.product_id} 배제: {rule['rule_id']} - {reason}")
                        break  # 하나의 룰이라도 배제되면 즉시 중단
            
            # 성능 통계 업데이트
            evaluation_time = (time.time() - start_time) * 1000
            result.evaluation_time_ms = evaluation_time
            
            self._evaluation_count += 1
            self._total_evaluation_time += evaluation_time
            
            logger.info(
                f"배제 평가 완료: {result.total_evaluated}개 중 {result.total_excluded}개 배제 "
                f"({evaluation_time:.2f}ms, {result.rules_applied}개 룰 적용)"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"배제 평가 중 오류: {e}")
            # 오류 발생 시 안전을 위해 모든 제품 배제
            for product in products:
                rule_hit = RuleHit(
                    type='exclude',
                    rule_id='SYSTEM_ERROR',
                    weight=1000,
                    rationale_ko=f'시스템 오류로 인한 안전 배제: {str(e)}',
                    citation_url=None
                )
                result.add_exclusion(product.product_id, rule_hit, '시스템 오류')
            
            result.evaluation_time_ms = (time.time() - start_time) * 1000
            return result
    
    def _extract_use_context(self, request: RecommendationRequest) -> Dict[str, Any]:
        """요청에서 사용 맥락 추출"""
        context = {}
        
        if request.use_context:
            context.update({
                'leave_on': request.use_context.leave_on,
                'day_use': request.use_context.day_use,
                'face': request.use_context.face,
                'large_area_hint': request.use_context.large_area_hint
            })
        
        if request.med_profile:
            context.update({
                'preg_lact': request.med_profile.preg_lact
            })
        
        return context
    
    def _find_applicable_rules(
        self, 
        rules: List[Dict[str, Any]], 
        med_codes: Set[str], 
        ingredient_tags: List[str]
    ) -> List[Dict[str, Any]]:
        """적용 가능한 룰 찾기"""
        applicable = []
        
        # 성분 태그 정규화
        normalized_tags = set(tag.lower().strip() for tag in ingredient_tags)
        
        for rule in rules:
            # 의약품 코드 매칭
            if rule.get('med_code') and rule['med_code'] in med_codes:
                applicable.append(rule)
                continue
            
            # 성분 태그 매칭
            if rule.get('ingredient_tag'):
                rule_tag = rule['ingredient_tag'].lower().strip()
                if rule_tag in normalized_tags:
                    applicable.append(rule)
                    continue
        
        return applicable
    
    def _evaluate_rule_conditions(self, rule: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """룰 조건 평가"""
        condition_json = rule.get('condition_json', {})
        
        if not condition_json:
            return True  # 조건이 없으면 항상 적용
        
        try:
            return self.rule_service.evaluate_condition_json(condition_json, context)
        except Exception as e:
            logger.error(f"룰 조건 평가 오류 (rule_id: {rule.get('rule_id')}): {e}")
            return True  # 오류 시 안전을 위해 적용
    
    def _generate_exclusion_reason(self, rule: Dict[str, Any], request: RecommendationRequest) -> str:
        """배제 사유 생성"""
        base_reason = rule.get('rationale_ko', '안전성 우려')
        
        # 의약품 관련 배제
        if rule.get('med_code'):
            med_name = self._get_med_name(rule['med_code'])
            return f"{med_name} 복용 시 {base_reason}"
        
        # 성분 관련 배제
        if rule.get('ingredient_tag'):
            return f"{rule['ingredient_tag']} 성분으로 인한 {base_reason}"
        
        # 임신/수유 관련
        if request.med_profile and request.med_profile.preg_lact:
            return f"임신/수유 중 {base_reason}"
        
        return base_reason
    
    def _get_med_name(self, med_code: str) -> str:
        """의약품 코드에서 이름 추출"""
        # 간단한 매핑 (실제로는 더 복잡한 매핑 테이블 필요)
        med_names = {
            'B01AA03': '와파린',
            'H02AB': '스테로이드',
            'MULTI:ANTICOAG': '항응고제',
            'MULTI:HTN': '고혈압약'
        }
        return med_names.get(med_code, med_code)
    
    def get_exclusion_summary(self, result: EligibilityResult) -> Dict[str, Any]:
        """배제 요약 통계"""
        if result.total_evaluated == 0:
            return {
                'exclusion_rate': 0.0,
                'rules_triggered': 0,
                'top_exclusion_rules': [],
                'exclusion_reasons_distribution': {},
                'performance_ms': result.evaluation_time_ms
            }
        
        exclusion_rate = (result.total_excluded / result.total_evaluated) * 100
        
        # 룰별 히트 카운트
        rule_hits_count = Counter(hit.rule_id for hit in result.rule_hits)
        top_rules = rule_hits_count.most_common(5)
        
        # 배제 사유 분포
        all_reasons = []
        for reasons in result.exclusion_reasons.values():
            all_reasons.extend(reasons)
        reason_distribution = Counter(all_reasons)
        
        return {
            'exclusion_rate': round(exclusion_rate, 2),
            'rules_triggered': len(rule_hits_count),
            'top_exclusion_rules': [{'rule_id': rule_id, 'count': count} for rule_id, count in top_rules],
            'exclusion_reasons_distribution': dict(reason_distribution.most_common(10)),
            'performance_ms': result.evaluation_time_ms,
            'avg_evaluation_time_ms': self._total_evaluation_time / max(self._evaluation_count, 1)
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회"""
        return {
            'total_evaluations': self._evaluation_count,
            'total_evaluation_time_ms': self._total_evaluation_time,
            'avg_evaluation_time_ms': self._total_evaluation_time / max(self._evaluation_count, 1),
            'cache_hit_rate': 1.0 if self._eligibility_rules_cache else 0.0
        }
    
    def clear_cache(self):
        """캐시 초기화"""
        self._eligibility_rules_cache = None
        self._cache_timestamp = None
        logger.info("배제 엔진 캐시 초기화")
    
    def close(self):
        """리소스 정리"""
        try:
            if hasattr(self, 'rule_service') and self.rule_service:
                self.rule_service.close_session()
            
            # 성능 통계 로깅
            if self._evaluation_count > 0:
                avg_time = self._total_evaluation_time / self._evaluation_count
                logger.info(f"EligibilityEngine 종료 - 총 {self._evaluation_count}회 평가, 평균 {avg_time:.2f}ms")
            
        except Exception as e:
            logger.error(f"EligibilityEngine 리소스 정리 오류: {e}")
        
        logger.info("EligibilityEngine 종료 완료")