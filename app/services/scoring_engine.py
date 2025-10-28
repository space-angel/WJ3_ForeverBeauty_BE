"""
감점 엔진 (Scoring Engine)
의약품-성분 상호작용 기반 제품 감점 처리
동계열 중복 감점 상한 정책 및 심각도 배수 적용
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
class ScoringResult:
    """감점 평가 결과"""
    product_id: int
    base_score: int = 100
    penalty_score: int = 0
    final_score: int = 100
    rule_hits: List[RuleHit] = field(default_factory=list)
    rule_groups_applied: Set[str] = field(default_factory=set)
    severity_multiplier: float = 1.0
    
    def add_penalty(self, rule_hit: RuleHit, penalty: int, rule_group: str = None):
        """감점 추가"""
        self.rule_hits.append(rule_hit)
        self.penalty_score += penalty
        
        if rule_group:
            self.rule_groups_applied.add(rule_group)
        
        self.final_score = max(0, self.base_score - self.penalty_score)
    
    def apply_severity_multiplier(self, multiplier: float):
        """심각도 배수 적용"""
        self.severity_multiplier = multiplier
        adjusted_penalty = int(self.penalty_score * multiplier)
        self.penalty_score = adjusted_penalty
        self.final_score = max(0, self.base_score - self.penalty_score)

class ScoringEngine:
    """
    감점 엔진
    
    의약품-성분 상호작용 룰을 기반으로 제품에 감점을 적용하는 엔진
    동계열 중복 감점 상한 정책과 심각도 배수를 적용하여 공정한 점수 산출
    """
    
    def __init__(self):
        """감점 엔진 초기화"""
        try:
            self.rule_service = RuleService()
            self.ingredient_service = IngredientService()
            self._scoring_rules_cache = None
            self._cache_timestamp = None
            self._cache_ttl = 300  # 5분 캐시
            
            # 동계열 중복 감점 상한 설정
            self.max_penalty_per_group = 50  # 동일 계열 최대 감점
            self.severity_multipliers = {
                'high': 2.0,
                'medium': 1.5,
                'low': 1.0
            }
            
            # 성능 모니터링
            self._evaluation_count = 0
            self._total_evaluation_time = 0.0
            
            logger.info("ScoringEngine 초기화 완료")
            
        except Exception as e:
            logger.error(f"ScoringEngine 초기화 실패: {e}")
            raise RuntimeError(f"감점 엔진 초기화 실패: {e}")
    
    def _load_scoring_rules(self) -> List[Dict[str, Any]]:
        """감점 룰 로딩 (캐시 포함)"""
        current_time = datetime.now()
        
        # 캐시 유효성 검사
        if (self._scoring_rules_cache is not None and 
            self._cache_timestamp is not None and
            (current_time - self._cache_timestamp).total_seconds() < self._cache_ttl):
            return self._scoring_rules_cache
        
        try:
            # 룰 서비스에서 감점 룰 조회
            rules = self.rule_service.get_cached_scoring_rules()
            
            # 룰 유효성 검증
            validated_rules = []
            for rule in rules:
                if self._validate_rule_structure(rule):
                    validated_rules.append(rule)
                else:
                    logger.warning(f"잘못된 룰 구조 무시: {rule.get('rule_id', 'unknown')}")
            
            self._scoring_rules_cache = validated_rules
            self._cache_timestamp = current_time
            
            logger.info(f"감점 룰 로딩 완료: {len(validated_rules)}개 룰")
            return validated_rules
            
        except Exception as e:
            logger.error(f"감점 룰 로딩 실패: {e}")
            # 캐시된 룰이 있으면 그것을 사용
            if self._scoring_rules_cache is not None:
                logger.warning("캐시된 룰 사용")
                return self._scoring_rules_cache
            return []
    
    def _validate_rule_structure(self, rule: Dict[str, Any]) -> bool:
        """룰 구조 유효성 검증"""
        if not rule:
            return False
        
        required_fields = ['rule_id', 'rule_type', 'action']
        
        for field in required_fields:
            if field not in rule or not rule[field]:
                return False
        
        # rule_type이 scoring인지 확인
        if rule['rule_type'] != 'scoring':
            return False
        
        # action이 penalize인지 확인
        if rule['action'] != 'penalize':
            return False
        
        # weight 확인 (감점 룰은 weight가 있어야 함, 음수 허용)
        weight = rule.get('weight', 0)
        if not isinstance(weight, (int, float)) or weight == 0:
            return False
        
        # med_code나 ingredient_tag 중 하나는 있어야 함
        if not rule.get('med_code') and not rule.get('ingredient_tag'):
            return False
        
        return True
    
    def evaluate_products(
        self, 
        products: List[Product], 
        request: RecommendationRequest,
        request_id: UUID = None
    ) -> Dict[int, ScoringResult]:
        """
        제품 감점 평가 수행
        
        Args:
            products: 평가할 제품 목록
            request: 추천 요청
            request_id: 요청 ID (선택사항)
            
        Returns:
            Dict[int, ScoringResult]: 제품 ID별 감점 결과
        """
        start_time = time.time()
        
        # 입력 유효성 검증
        if not products:
            logger.warning("평가할 제품이 없습니다")
            return {}
        
        if not request:
            raise ValueError("추천 요청이 없습니다")
        
        results = {}
        
        try:
            # 감점 룰 로딩
            scoring_rules = self._load_scoring_rules()
            if not scoring_rules:
                logger.warning("감점 룰이 없습니다. 모든 제품 기본 점수 유지")
                for product in products:
                    results[product.product_id] = ScoringResult(product_id=product.product_id)
                return results
            
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
            
            # 각 제품에 대해 감점 평가
            for product in products:
                result = ScoringResult(product_id=product.product_id)
                product_ingredient_tags = product_tags.get(product.product_id, [])
                
                # 적용 가능한 룰 찾기
                applicable_rules = self._find_applicable_rules(
                    scoring_rules, all_med_codes, product_ingredient_tags
                )
                
                # 룰 그룹별 감점 누적 (동계열 중복 감점 상한 적용)
                group_penalties = defaultdict(list)
                
                # 각 룰에 대해 평가
                for rule in applicable_rules:
                    if self._evaluate_rule_conditions(rule, use_context):
                        # 감점 조건 만족
                        penalty = rule['weight']
                        rule_group = self._get_rule_group(rule)
                        
                        rule_hit = RuleHit(
                            type='penalize',
                            rule_id=rule['rule_id'],
                            weight=penalty,
                            rationale_ko=rule.get('rationale_ko', '위험도 증가'),
                            citation_url=rule.get('citation_url')
                        )
                        
                        group_penalties[rule_group].append((rule_hit, penalty))
                        
                        logger.debug(f"제품 {product.product_id} 감점: {rule['rule_id']} - {penalty}점")
                
                # 동계열 중복 감점 상한 적용
                for rule_group, penalties in group_penalties.items():
                    total_group_penalty = sum(penalty for _, penalty in penalties)
                    
                    if total_group_penalty > self.max_penalty_per_group:
                        # 상한 초과 시 비례 감소
                        reduction_factor = self.max_penalty_per_group / total_group_penalty
                        logger.debug(f"제품 {product.product_id} 그룹 {rule_group} 감점 상한 적용: "
                                   f"{total_group_penalty} -> {self.max_penalty_per_group}")
                    else:
                        reduction_factor = 1.0
                    
                    # 감점 적용
                    for rule_hit, penalty in penalties:
                        adjusted_penalty = int(penalty * reduction_factor)
                        result.add_penalty(rule_hit, adjusted_penalty, rule_group)
                
                results[product.product_id] = result
            
            # 성능 통계 업데이트
            evaluation_time = (time.time() - start_time) * 1000
            self._evaluation_count += 1
            self._total_evaluation_time += evaluation_time
            
            total_penalties = sum(r.penalty_score for r in results.values())
            penalized_count = sum(1 for r in results.values() if r.penalty_score > 0)
            
            logger.info(
                f"감점 평가 완료: {len(products)}개 제품, {penalized_count}개 감점 적용, "
                f"총 감점 {total_penalties}점 ({evaluation_time:.2f}ms)"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"감점 평가 중 오류: {e}")
            # 오류 발생 시 기본 점수 반환
            for product in products:
                results[product.product_id] = ScoringResult(product_id=product.product_id)
            return results
    
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
            return False  # 오류 시 적용하지 않음
    
    def _get_rule_group(self, rule: Dict[str, Any]) -> str:
        """룰 그룹 결정 (동계열 중복 감점 상한용)"""
        # 의약품 코드 기반 그룹핑
        if rule.get('med_code'):
            med_code = rule['med_code']
            if med_code.startswith('B01'):  # 항응고제
                return 'anticoagulant'
            elif med_code.startswith('H02'):  # 스테로이드
                return 'steroid'
            elif med_code.startswith('MULTI:'):
                return med_code.split(':')[1].lower()
            else:
                return f"med_{med_code[:3]}"
        
        # 성분 태그 기반 그룹핑
        if rule.get('ingredient_tag'):
            tag = rule['ingredient_tag'].lower()
            if 'aha' in tag or 'bha' in tag:
                return 'exfoliant'
            elif 'retinoid' in tag or 'retinol' in tag:
                return 'retinoid'
            elif 'vitamin_c' in tag:
                return 'vitamin_c'
            else:
                return f"ingredient_{tag}"
        
        return 'default'
    
    def calculate_penalty_statistics(self, results: Dict[int, ScoringResult]) -> Dict[str, Any]:
        """감점 통계 계산"""
        if not results:
            return {
                'total_products': 0,
                'penalized_products': 0,
                'penalization_rate': 0.0,
                'average_penalty': 0.0,
                'penalty_distribution': {},
                'top_penalty_rules': []
            }
        
        total_products = len(results)
        penalized_products = sum(1 for r in results.values() if r.penalty_score > 0)
        total_penalty = sum(r.penalty_score for r in results.values())
        
        # 감점 분포
        penalty_ranges = {
            '0점': 0,
            '1-10점': 0,
            '11-25점': 0,
            '26-50점': 0,
            '51점 이상': 0
        }
        
        for result in results.values():
            penalty = result.penalty_score
            if penalty == 0:
                penalty_ranges['0점'] += 1
            elif penalty <= 10:
                penalty_ranges['1-10점'] += 1
            elif penalty <= 25:
                penalty_ranges['11-25점'] += 1
            elif penalty <= 50:
                penalty_ranges['26-50점'] += 1
            else:
                penalty_ranges['51점 이상'] += 1
        
        # 상위 감점 룰
        all_rule_hits = []
        for result in results.values():
            all_rule_hits.extend(result.rule_hits)
        
        rule_hit_counts = Counter(hit.rule_id for hit in all_rule_hits)
        top_penalty_rules = [
            {'rule_id': rule_id, 'count': count} 
            for rule_id, count in rule_hit_counts.most_common(10)
        ]
        
        return {
            'total_products': total_products,
            'penalized_products': penalized_products,
            'penalization_rate': round((penalized_products / total_products) * 100, 2),
            'average_penalty': round(total_penalty / total_products, 2),
            'penalty_distribution': penalty_ranges,
            'top_penalty_rules': top_penalty_rules
        }
    
    def get_product_penalty_details(self, result: ScoringResult) -> Dict[str, Any]:
        """제품 감점 상세 정보"""
        return {
            'product_id': result.product_id,
            'base_score': result.base_score,
            'penalty_score': result.penalty_score,
            'final_score': result.final_score,
            'severity_multiplier': result.severity_multiplier,
            'rules_applied': len(result.rule_hits),
            'rule_groups_applied': list(result.rule_groups_applied),
            'rule_details': [
                {
                    'rule_id': hit.rule_id,
                    'weight': hit.weight,
                    'rationale': hit.rationale_ko
                }
                for hit in result.rule_hits
            ]
        }
    
    def apply_severity_multiplier(self, results: Dict[int, ScoringResult]) -> Dict[int, ScoringResult]:
        """
        심각도 배수 적용
        
        의약품 조합의 위험도에 따라 감점에 배수를 적용
        """
        try:
            for result in results.values():
                # 룰 그룹 기반 심각도 결정
                severity = self._calculate_severity(result.rule_groups_applied)
                multiplier = self.severity_multipliers.get(severity, 1.0)
                
                if multiplier != 1.0:
                    result.apply_severity_multiplier(multiplier)
                    logger.debug(f"제품 {result.product_id} 심각도 배수 적용: {severity} ({multiplier}x)")
            
            return results
            
        except Exception as e:
            logger.error(f"심각도 배수 적용 오류: {e}")
            return results
    
    def _calculate_severity(self, rule_groups: Set[str]) -> str:
        """룰 그룹 조합 기반 심각도 계산"""
        if not rule_groups:
            return 'low'
        
        # 고위험 조합
        high_risk_groups = {'anticoagulant', 'steroid'}
        medium_risk_groups = {'exfoliant', 'retinoid'}
        
        # 고위험 그룹이 2개 이상
        if len(rule_groups.intersection(high_risk_groups)) >= 2:
            return 'high'
        
        # 고위험 + 중위험 조합
        if (rule_groups.intersection(high_risk_groups) and 
            rule_groups.intersection(medium_risk_groups)):
            return 'high'
        
        # 고위험 그룹 1개 또는 중위험 그룹 2개 이상
        if (len(rule_groups.intersection(high_risk_groups)) == 1 or
            len(rule_groups.intersection(medium_risk_groups)) >= 2):
            return 'medium'
        
        return 'low'
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """성능 메트릭 조회"""
        return {
            'total_evaluations': self._evaluation_count,
            'total_evaluation_time_ms': self._total_evaluation_time,
            'avg_evaluation_time_ms': self._total_evaluation_time / max(self._evaluation_count, 1),
            'cache_hit_rate': 1.0 if self._scoring_rules_cache else 0.0,
            'max_penalty_per_group': self.max_penalty_per_group
        }
    
    def clear_cache(self):
        """캐시 초기화"""
        self._scoring_rules_cache = None
        self._cache_timestamp = None
        logger.info("감점 엔진 캐시 초기화")
    
    def close(self):
        """리소스 정리"""
        try:
            if hasattr(self, 'rule_service') and self.rule_service:
                self.rule_service.close_session()
            
            # 성능 통계 로깅
            if self._evaluation_count > 0:
                avg_time = self._total_evaluation_time / self._evaluation_count
                logger.info(f"ScoringEngine 종료 - 총 {self._evaluation_count}회 평가, 평균 {avg_time:.2f}ms")
            
        except Exception as e:
            logger.error(f"ScoringEngine 리소스 정리 오류: {e}")
        
        logger.info("ScoringEngine 종료 완료")