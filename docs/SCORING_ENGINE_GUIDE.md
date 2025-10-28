# 감점 엔진 (Scoring Engine) 기술문서

## 개요

감점 엔진은 의약품-성분 상호작용을 기반으로 제품에 감점을 적용하는 시스템입니다. 배제 엔진에서 걸러지지 않은 제품들에 대해 위험도에 따른 점수 조정을 수행하여, 더 안전한 제품이 우선 추천되도록 합니다.

## 핵심 기능

### 1. 위험도 기반 감점
- 의약품-성분 상호작용 위험도에 따른 차등 감점
- 사용 맥락을 고려한 조건부 감점
- 심각도 배수 적용으로 고위험 조합 강화

### 2. 동계열 중복 감점 상한 정책
- 동일 계열 성분에 대한 감점 상한 설정 (기본 50점)
- 공정한 점수 산출을 위한 비례 감소
- 룰 그룹별 독립적 상한 적용

### 3. 심각도 배수 시스템
- 고위험 조합: 2.0배 감점
- 중위험 조합: 1.5배 감점
- 저위험 조합: 1.0배 감점 (기본)

## 아키텍처

```
RecommendationRequest + Products
        ↓
    [의약품 코드 해석]
        ↓
    [성분 태그 배치 로딩]
        ↓
    [감점 룰 적용]
        ↓
    [동계열 상한 적용]
        ↓
    [심각도 배수 적용]
        ↓
    ScoringResult (제품별)
```

## 주요 컴포넌트

### ScoringEngine 클래스
```python
class ScoringEngine:
    def __init__(self):
        self.rule_service = RuleService()
        self.ingredient_service = IngredientService()
        self.max_penalty_per_group = 50  # 동일 계열 최대 감점
        self.severity_multipliers = {
            'high': 2.0,
            'medium': 1.5,
            'low': 1.0
        }
```

### ScoringResult 데이터 클래스
```python
@dataclass
class ScoringResult:
    product_id: int
    base_score: int = 100
    penalty_score: int = 0
    final_score: int = 100
    rule_hits: List[RuleHit] = field(default_factory=list)
    rule_groups_applied: Set[str] = field(default_factory=set)
    severity_multiplier: float = 1.0
```

## 감점 룰 구조

### 필수 필드
- `rule_id`: 룰 고유 식별자
- `rule_type`: "scoring" 고정값
- `action`: "penalize" 고정값
- `weight`: 감점 점수 (양수)
- `med_code` 또는 `ingredient_tag`: 매칭 조건 중 하나 필수

### 선택 필드
- `condition_json`: 추가 조건 (JSON 형태)
- `rationale_ko`: 감점 사유 (한국어)
- `citation_url`: 근거 자료 URL

### 예시 룰
```json
{
    "rule_id": "HTN_RETINOL_MILD",
    "rule_type": "scoring",
    "action": "penalize",
    "med_code": "MULTI:HTN",
    "ingredient_tag": "retinol",
    "weight": 15,
    "condition_json": {
        "leave_on": true,
        "face": true
    },
    "rationale_ko": "고혈압약 복용 시 레티놀 사용으로 인한 피부 민감도 증가",
    "citation_url": "https://example.com/study"
}
```

## 감점 프로세스

### 1. 기본 감점 적용
```python
for product in products:
    result = ScoringResult(product_id=product.product_id)
    
    # 적용 가능한 룰 찾기
    applicable_rules = self._find_applicable_rules(
        scoring_rules, all_med_codes, product_ingredient_tags
    )
    
    # 룰 그룹별 감점 누적
    group_penalties = defaultdict(list)
    
    for rule in applicable_rules:
        if self._evaluate_rule_conditions(rule, use_context):
            penalty = rule['weight']
            rule_group = self._get_rule_group(rule)
            group_penalties[rule_group].append((rule_hit, penalty))
```

### 2. 동계열 중복 감점 상한 적용
```python
for rule_group, penalties in group_penalties.items():
    total_group_penalty = sum(penalty for _, penalty in penalties)
    
    if total_group_penalty > self.max_penalty_per_group:
        # 상한 초과 시 비례 감소
        reduction_factor = self.max_penalty_per_group / total_group_penalty
        logger.debug(f"그룹 {rule_group} 감점 상한 적용: "
                   f"{total_group_penalty} -> {self.max_penalty_per_group}")
    else:
        reduction_factor = 1.0
    
    # 감점 적용
    for rule_hit, penalty in penalties:
        adjusted_penalty = int(penalty * reduction_factor)
        result.add_penalty(rule_hit, adjusted_penalty, rule_group)
```

### 3. 심각도 배수 적용
```python
def apply_severity_multiplier(self, results: Dict[int, ScoringResult]) -> Dict[int, ScoringResult]:
    for result in results.values():
        # 룰 그룹 기반 심각도 결정
        severity = self._calculate_severity(result.rule_groups_applied)
        multiplier = self.severity_multipliers.get(severity, 1.0)
        
        if multiplier != 1.0:
            result.apply_severity_multiplier(multiplier)
    
    return results
```

## 룰 그룹 분류

### 의약품 코드 기반 그룹핑
```python
def _get_rule_group(self, rule: Dict[str, Any]) -> str:
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
```

### 성분 태그 기반 그룹핑
```python
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
```

## 심각도 계산 로직

### 고위험 조합 (2.0배)
- 고위험 그룹 2개 이상 조합
- 고위험 + 중위험 그룹 조합

### 중위험 조합 (1.5배)
- 고위험 그룹 1개
- 중위험 그룹 2개 이상

### 저위험 조합 (1.0배)
- 기타 모든 조합

```python
def _calculate_severity(self, rule_groups: Set[str]) -> str:
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
```

## 성능 최적화

### 1. 캐싱 전략
- 감점 룰 5분 캐시
- 의약품 코드 배치 해석
- 성분 태그 배치 로딩

### 2. 배치 처리
```python
# 제품별 성분 태그 배치 로딩
product_ids = [p.product_id for p in products]
product_tags = self.ingredient_service.get_canonical_tags_batch(product_ids)

# 의약품 코드 해석
resolved_med_codes = self.rule_service.resolve_med_codes_batch(med_codes)
```

### 3. 메모리 효율성
- 제품별 독립적 처리
- 불필요한 객체 생성 최소화
- 조기 조건 평가

## 사용 예시

### 기본 사용법
```python
from app.services.scoring_engine import ScoringEngine

# 엔진 초기화
engine = ScoringEngine()

# 제품 감점 평가
results = engine.evaluate_products(
    products=filtered_products,
    request=recommendation_request
)

# 결과 확인
for product_id, result in results.items():
    print(f"제품 {product_id}: {result.base_score} -> {result.final_score} "
          f"(감점: {result.penalty_score})")

# 심각도 배수 적용
results_with_severity = engine.apply_severity_multiplier(results)
```

### 통계 분석
```python
# 감점 통계 계산
stats = engine.calculate_penalty_statistics(results)
print(f"감점율: {stats['penalization_rate']}%")
print(f"평균 감점: {stats['average_penalty']}점")

# 제품별 상세 정보
for product_id, result in results.items():
    details = engine.get_product_penalty_details(result)
    print(f"제품 {product_id} 상세:")
    print(f"  적용된 룰 그룹: {details['rule_groups_applied']}")
    print(f"  심각도 배수: {details['severity_multiplier']}")
```

## 모니터링 및 로깅

### 주요 로그 이벤트
- 엔진 초기화/종료
- 룰 로딩 및 캐시 상태
- 감점 적용 결과
- 동계열 상한 적용
- 심각도 배수 적용
- 성능 통계

### 성능 메트릭
```python
metrics = engine.get_performance_metrics()
print(f"총 평가 횟수: {metrics['total_evaluations']}")
print(f"평균 평가 시간: {metrics['avg_evaluation_time_ms']:.2f}ms")
print(f"캐시 히트율: {metrics['cache_hit_rate']:.2%}")
print(f"그룹별 최대 감점: {metrics['max_penalty_per_group']}")
```

## 설정 및 튜닝

### 감점 상한 조정
```python
# 동계열 중복 감점 상한 변경
engine.max_penalty_per_group = 40  # 기본값: 50

# 심각도 배수 조정
engine.severity_multipliers = {
    'high': 2.5,    # 기본값: 2.0
    'medium': 1.8,  # 기본값: 1.5
    'low': 1.0      # 기본값: 1.0
}
```

### 룰 그룹 커스터마이징
- 새로운 의약품 계열 추가
- 성분 그룹 세분화
- 조합별 위험도 재정의

## 확장성 고려사항

### 1. 룰 확장
- 시간 기반 감점 (예: 계절성)
- 사용자 특성 기반 감점
- 동적 가중치 조정

### 2. 성능 확장
- 병렬 처리 지원
- 분산 캐싱
- 룰 인덱싱 최적화

### 3. 정확성 향상
- 머신러닝 기반 가중치 학습
- 실시간 피드백 반영
- A/B 테스트 지원

## 문제 해결

### 일반적인 문제
1. **과도한 감점**: 상한 설정이 너무 높거나 심각도 배수가 과도한 경우
2. **불균등한 감점**: 룰 그룹 분류가 부적절한 경우
3. **성능 저하**: 복잡한 조건 평가나 캐시 미스

### 디버깅 팁
- 제품별 감점 상세 정보 확인
- 룰 그룹별 감점 분포 분석
- 심각도 계산 로직 검증
- 성능 메트릭 모니터링

## 관련 문서
- [배제 엔진 가이드](ELIGIBILITY_ENGINE_GUIDE.md)
- [정렬 엔진 가이드](RANKING_SERVICE_GUIDE.md)
- [룰 서비스 가이드](RULE_SERVICE_GUIDE.md)