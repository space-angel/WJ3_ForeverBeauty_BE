# 배제 엔진 (Eligibility Engine) 기술문서

## 개요

배제 엔진은 의약품-성분 상호작용 및 사용 맥락을 기반으로 안전하지 않은 제품들을 즉시 배제하는 핵심 안전 시스템입니다. 추천 파이프라인의 첫 번째 단계에서 작동하여 위험한 제품 조합을 사전에 차단합니다.

## 핵심 기능

### 1. 의약품-성분 상호작용 검사
- 사용자의 복용 의약품과 화장품 성분 간의 위험한 상호작용 탐지
- ATC 코드 기반 의약품 분류 및 매칭
- 성분 태그 정규화를 통한 정확한 매칭

### 2. 사용 맥락 기반 배제
- 임신/수유 상태 고려
- 사용 부위 (얼굴/몸) 고려
- 사용 방식 (leave-on/rinse-off) 고려
- 넓은 면적 사용 여부 고려

### 3. 실시간 안전성 평가
- 룰 기반 즉시 배제 결정
- 배제 사유 및 근거 제공
- 성능 최적화된 배치 처리

## 아키텍처

```
RecommendationRequest
        ↓
    [의약품 코드 해석]
        ↓
    [성분 태그 배치 로딩]
        ↓
    [배제 룰 적용]
        ↓
    [조건 평가]
        ↓
    EligibilityResult
```

## 주요 컴포넌트

### EligibilityEngine 클래스
```python
class EligibilityEngine:
    def __init__(self):
        self.rule_service = RuleService()
        self.ingredient_service = IngredientService()
        self._eligibility_rules_cache = None
        self._cache_ttl = 300  # 5분 캐시
```

### EligibilityResult 데이터 클래스
```python
@dataclass
class EligibilityResult:
    request_id: UUID
    total_evaluated: int = 0
    total_excluded: int = 0
    excluded_products: Set[int] = field(default_factory=set)
    exclusion_reasons: Dict[int, List[str]] = field(default_factory=dict)
    rule_hits: List[RuleHit] = field(default_factory=list)
    evaluation_time_ms: float = 0.0
    rules_applied: int = 0
```

## 배제 룰 구조

### 필수 필드
- `rule_id`: 룰 고유 식별자
- `rule_type`: "eligibility" 고정값
- `action`: "exclude" 고정값
- `med_code` 또는 `ingredient_tag`: 매칭 조건 중 하나 필수

### 선택 필드
- `condition_json`: 추가 조건 (JSON 형태)
- `rationale_ko`: 배제 사유 (한국어)
- `citation_url`: 근거 자료 URL
- `weight`: 룰 가중치

### 예시 룰
```json
{
    "rule_id": "WARFARIN_SALICYLIC_ACID",
    "rule_type": "eligibility",
    "action": "exclude",
    "med_code": "B01AA03",
    "ingredient_tag": "salicylic_acid",
    "condition_json": {
        "leave_on": true
    },
    "rationale_ko": "와파린 복용 시 살리실산 성분으로 인한 출혈 위험 증가",
    "citation_url": "https://example.com/study",
    "weight": 100
}
```

## 평가 프로세스

### 1. 입력 검증
```python
def evaluate_products(self, products: List[Product], request: RecommendationRequest, request_id: UUID) -> EligibilityResult:
    # 입력 유효성 검증
    if not products:
        return EligibilityResult(request_id=request_id, total_evaluated=0)
    
    if not request:
        raise ValueError("추천 요청이 없습니다")
```

### 2. 룰 로딩 및 캐싱
```python
def _load_eligibility_rules(self) -> List[Dict[str, Any]]:
    # 캐시 유효성 검사
    if self._eligibility_rules_cache and self._is_cache_valid():
        return self._eligibility_rules_cache
    
    # 룰 서비스에서 배제 룰 조회
    rules = self.rule_service.get_cached_eligibility_rules()
    
    # 룰 유효성 검증
    validated_rules = [rule for rule in rules if self._validate_rule_structure(rule)]
    
    self._eligibility_rules_cache = validated_rules
    return validated_rules
```

### 3. 제품별 평가
```python
for product in products:
    product_ingredient_tags = product_tags.get(product.product_id, [])
    
    # 적용 가능한 룰 찾기
    applicable_rules = self._find_applicable_rules(
        eligibility_rules, all_med_codes, product_ingredient_tags
    )
    
    # 각 룰에 대해 평가
    for rule in applicable_rules:
        if self._evaluate_rule_conditions(rule, use_context):
            # 배제 조건 만족 - 제품 배제
            result.add_exclusion(product.product_id, rule_hit, reason)
            break  # 하나의 룰이라도 배제되면 즉시 중단
```

## 성능 최적화

### 1. 캐싱 전략
- 배제 룰 5분 캐시
- 의약품 코드 배치 해석
- 성분 태그 배치 로딩

### 2. 조기 종료
- 제품이 배제되면 추가 룰 평가 중단
- 오류 발생 시 안전을 위해 모든 제품 배제

### 3. 배치 처리
```python
# 제품별 성분 태그 배치 로딩
product_ids = [p.product_id for p in products]
product_tags = self.ingredient_service.get_canonical_tags_batch(product_ids)

# 의약품 코드 해석
resolved_med_codes = self.rule_service.resolve_med_codes_batch(med_codes)
```

## 안전성 보장

### 1. 오류 처리
```python
except Exception as e:
    logger.error(f"배제 평가 중 오류: {e}")
    # 오류 발생 시 안전을 위해 모든 제품 배제
    for product in products:
        rule_hit = RuleHit(
            type='exclude',
            rule_id='SYSTEM_ERROR',
            weight=1000,
            rationale_ko=f'시스템 오류로 인한 안전 배제: {str(e)}'
        )
        result.add_exclusion(product.product_id, rule_hit, '시스템 오류')
```

### 2. 룰 검증
```python
def _validate_rule_structure(self, rule: Dict[str, Any]) -> bool:
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
    
    return True
```

## 사용 예시

### 기본 사용법
```python
from app.services.eligibility_engine import EligibilityEngine

# 엔진 초기화
engine = EligibilityEngine()

# 제품 배제 평가
result = engine.evaluate_products(
    products=candidate_products,
    request=recommendation_request,
    request_id=uuid4()
)

# 결과 확인
print(f"총 {result.total_evaluated}개 중 {result.total_excluded}개 배제")
print(f"배제된 제품: {result.excluded_products}")

# 배제 요약 통계
summary = engine.get_exclusion_summary(result)
print(f"배제율: {summary['exclusion_rate']}%")
```

### 성능 모니터링
```python
# 성능 메트릭 조회
metrics = engine.get_performance_metrics()
print(f"평균 평가 시간: {metrics['avg_evaluation_time_ms']:.2f}ms")
print(f"캐시 히트율: {metrics['cache_hit_rate']:.2%}")

# 캐시 초기화
engine.clear_cache()

# 리소스 정리
engine.close()
```

## 모니터링 및 로깅

### 주요 로그 이벤트
- 엔진 초기화/종료
- 룰 로딩 및 캐시 상태
- 제품 배제 결정
- 성능 통계
- 오류 및 예외 상황

### 성능 메트릭
- 총 평가 횟수
- 평균 평가 시간
- 캐시 히트율
- 배제율 통계

## 확장성 고려사항

### 1. 룰 확장
- 새로운 의약품 코드 추가
- 복합 조건 룰 지원
- 시간 기반 룰 (예: 계절성)

### 2. 성능 확장
- 분산 캐싱 (Redis)
- 비동기 처리
- 룰 인덱싱 최적화

### 3. 안전성 강화
- 룰 버전 관리
- A/B 테스트 지원
- 실시간 룰 업데이트

## 문제 해결

### 일반적인 문제
1. **높은 배제율**: 룰이 너무 엄격한 경우
2. **낮은 성능**: 캐시 미스 또는 복잡한 룰
3. **잘못된 배제**: 룰 로직 오류

### 디버깅 팁
- 로그 레벨을 DEBUG로 설정
- 개별 룰별 평가 결과 확인
- 성능 메트릭 모니터링
- 룰 구조 검증 결과 확인

## 관련 문서
- [감점 엔진 가이드](SCORING_ENGINE_GUIDE.md)
- [정렬 엔진 가이드](RANKING_SERVICE_GUIDE.md)
- [룰 서비스 가이드](RULE_SERVICE_GUIDE.md)