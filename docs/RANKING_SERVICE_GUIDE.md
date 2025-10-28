# 정렬 서비스 (Ranking Service) 기술문서

## 개요

정렬 서비스는 6단계 tie-break 알고리즘을 통해 제품을 정렬하고 최종 추천 결과를 생성하는 시스템입니다. 배제 엔진과 감점 엔진을 거친 제품들을 다양한 기준으로 종합 평가하여 사용자에게 최적의 추천 순서를 제공합니다.

## 핵심 기능

### 1. 6단계 Tie-Break 정렬 알고리즘
1. **최종 점수** (높을수록 좋음)
2. **의도 일치도** (높을수록 좋음)
3. **감점 룰 수** (적을수록 좋음)
4. **브랜드 선호도** (높을수록 좋음)
5. **카테고리 일치도** (높을수록 좋음)
6. **제품 ID** (높을수록 좋음, 최신순)

### 2. 종합 추천 사유 생성
- 의도 일치도 기반 사유
- 안전성 기반 사유
- 브랜드 신뢰도 사유
- 카테고리 적합성 사유

### 3. 추천 결과 변환
- RankedProduct → ProductRecommendation 변환
- 상위 N개 제품 선별
- 통계 정보 제공

## 아키텍처

```
Products + ScoringResults + Request
        ↓
    [RankedProduct 생성]
        ↓
    [의도 일치도 계산]
        ↓
    [추천 사유 생성]
        ↓
    [6단계 Tie-Break 정렬]
        ↓
    [순위 할당]
        ↓
    [ProductRecommendation 변환]
        ↓
    최종 추천 결과
```

## 주요 컴포넌트

### RankingService 클래스
```python
class RankingService:
    def __init__(self):
        self.product_service = ProductService()
        
        # 정렬 가중치 설정
        self.tie_break_weights = {
            'final_score': 1000,      # 1순위: 최종 점수
            'intent_match': 100,      # 2순위: 의도 일치도
            'penalty_count': -10,     # 3순위: 감점 룰 수
            'brand_preference': 5,    # 4순위: 브랜드 선호도
            'product_id': -1          # 5순위: 제품 ID
        }
```

### RankedProduct 데이터 클래스
```python
@dataclass
class RankedProduct:
    product: Product
    rank: int
    final_score: int
    base_score: int = 100
    penalty_score: int = 0
    intent_match_score: int = 50
    reasons: List[str] = field(default_factory=list)
    rule_hits: List[RuleHit] = field(default_factory=list)
    excluded_by_rules: bool = False
```

## 정렬 알고리즘 상세

### 1. 정렬 키 함수
```python
def sort_key(ranked_product: RankedProduct) -> Tuple:
    product = ranked_product.product
    
    # 1순위: 최종 점수
    final_score = ranked_product.final_score
    
    # 2순위: 의도 일치도
    intent_match = ranked_product.intent_match_score
    
    # 3순위: 감점 룰 수 (적을수록 좋음)
    penalty_count = len(ranked_product.rule_hits)
    
    # 4순위: 브랜드 선호도
    brand_preference = self._calculate_brand_preference(
        getattr(product, 'brand_name', ''), request
    )
    
    # 5순위: 카테고리 일치도
    category_match = self._calculate_category_match(
        getattr(product, 'category_name', ''), request
    )
    
    # 6순위: 제품 ID (최신순)
    product_id = product.product_id
    
    return (
        -final_score,        # 높을수록 좋음 (음수로 변환)
        -intent_match,       # 높을수록 좋음 (음수로 변환)
        penalty_count,       # 적을수록 좋음
        -brand_preference,   # 높을수록 좋음 (음수로 변환)
        -category_match,     # 높을수록 좋음 (음수로 변환)
        -product_id          # 높을수록 좋음 (음수로 변환)
    )
```

### 2. 브랜드 선호도 계산
```python
def _calculate_brand_preference(self, brand_name: str, request: RecommendationRequest) -> int:
    premium_brands = {
        '라로슈포제', '아벤느', '비쉬', '세타필', '유세린',
        'La Roche-Posay', 'Avene', 'Vichy', 'Cetaphil', 'Eucerin'
    }
    
    popular_brands = {
        '이니스프리', '에뛰드하우스', '더페이스샵', '토니앤가이',
        'Innisfree', 'Etude House', 'The Face Shop'
    }
    
    brand_lower = brand_name.lower()
    
    for premium in premium_brands:
        if premium.lower() in brand_lower:
            return 10  # 프리미엄 브랜드
    
    for popular in popular_brands:
        if popular.lower() in brand_lower:
            return 5   # 인기 브랜드
    
    return 1  # 기본 점수
```

### 3. 카테고리 일치도 계산
```python
def _calculate_category_match(self, category_name: str, request: RecommendationRequest) -> int:
    if not category_name or not request.category_like:
        return 0
    
    category_lower = category_name.lower()
    request_category_lower = request.category_like.lower()
    
    # 완전 일치
    if request_category_lower in category_lower:
        return 10
    
    # 부분 일치
    if any(word in category_lower for word in request_category_lower.split()):
        return 5
    
    return 0
```

## 추천 사유 생성

### 1. 의도 일치 기반 사유
```python
# 의도 일치 기반 사유
if ranked_product.intent_match_score >= 80:
    intent_tags = ', '.join(request.intent_tags[:2]) if request.intent_tags else '요청 의도'
    reasons.append(f"{intent_tags}에 매우 적합한 제품입니다")
elif ranked_product.intent_match_score >= 60:
    reasons.append("요청하신 용도에 적합한 제품입니다")
```

### 2. 안전성 기반 사유
```python
# 안전성 기반 사유
if ranked_product.penalty_score == 0:
    reasons.append("안전성 우려가 없어 안심하고 사용할 수 있습니다")
elif ranked_product.penalty_score <= 15:
    reasons.append("경미한 주의사항이 있지만 일반적으로 안전합니다")
```

### 3. 브랜드 기반 사유
```python
# 브랜드 기반 사유
brand_name = getattr(product, 'brand_name', '')
if brand_name:
    brand_pref = self._calculate_brand_preference(brand_name, request)
    if brand_pref >= 10:
        reasons.append(f"{brand_name}는 전문가들이 신뢰하는 브랜드입니다")
    elif brand_pref >= 5:
        reasons.append(f"{brand_name}는 인기 있는 브랜드입니다")
```

### 4. 카테고리 일치 기반 사유
```python
# 카테고리 일치 기반 사유
if request.category_like:
    category_match = self._calculate_category_match(
        getattr(product, 'category_name', ''), request
    )
    if category_match >= 10:
        reasons.append(f"요청하신 {request.category_like} 카테고리에 정확히 맞습니다")
```

## 정렬 프로세스

### 1. RankedProduct 생성
```python
def rank_products(self, products: List[Product], scoring_results: Dict[int, ScoringResult], 
                 request: RecommendationRequest, excluded_products: Set[int] = None) -> List[RankedProduct]:
    
    # 정렬 가능한 제품만 필터링
    valid_products = [p for p in products if p.product_id not in excluded_products]
    
    ranked_products = []
    
    for product in valid_products:
        scoring_result = scoring_results.get(product.product_id)
        
        # 의도 일치도 계산
        intent_match_score = self.product_service.calculate_intent_match_score(
            product, request.intent_tags or []
        )
        
        # RankedProduct 생성
        ranked_product = RankedProduct(
            product=product,
            rank=0,  # 나중에 설정
            final_score=scoring_result.final_score if scoring_result else 100,
            base_score=scoring_result.base_score if scoring_result else 100,
            penalty_score=scoring_result.penalty_score if scoring_result else 0,
            intent_match_score=intent_match_score,
            rule_hits=scoring_result.rule_hits if scoring_result else []
        )
        
        # 추천 사유 생성
        ranked_product.reasons = self._generate_recommendation_reasons(ranked_product, request)
        
        ranked_products.append(ranked_product)
```

### 2. 정렬 및 순위 할당
```python
    # 6단계 tie-break 정렬 수행
    sorted_products = self._apply_tie_break_sorting(ranked_products, request)
    
    # 순위 할당
    for i, product in enumerate(sorted_products):
        product.rank = i + 1
    
    return sorted_products
```

## 통계 및 분석

### 정렬 통계 정보
```python
def get_ranking_statistics(self, ranked_products: List[RankedProduct]) -> Dict[str, Any]:
    total_products = len(ranked_products)
    
    # 평균 점수
    avg_final_score = sum(p.final_score for p in ranked_products) / total_products
    avg_intent_match = sum(p.intent_match_score for p in ranked_products) / total_products
    
    # 점수 분포
    score_ranges = {
        '90-100점': 0, '80-89점': 0, '70-79점': 0, 
        '60-69점': 0, '60점 미만': 0
    }
    
    for product in ranked_products:
        score = product.final_score
        if score >= 90:
            score_ranges['90-100점'] += 1
        elif score >= 80:
            score_ranges['80-89점'] += 1
        # ... 기타 범위
    
    return {
        'total_products': total_products,
        'average_final_score': round(avg_final_score, 1),
        'average_intent_match': round(avg_intent_match, 1),
        'score_distribution': score_ranges,
        'intent_match_distribution': intent_ranges,
        'top_brands': top_brands,
        'penalty_distribution': penalty_ranges
    }
```

## 사용 예시

### 기본 사용법
```python
from app.services.ranking_service import RankingService

# 서비스 초기화
ranking_service = RankingService()

# 제품 정렬
ranked_products = ranking_service.rank_products(
    products=filtered_products,
    scoring_results=scoring_results,
    request=recommendation_request,
    excluded_products=excluded_product_ids
)

# 결과 확인
for ranked_product in ranked_products[:5]:  # 상위 5개
    print(f"순위 {ranked_product.rank}: {ranked_product.product.name}")
    print(f"  최종 점수: {ranked_product.final_score}")
    print(f"  의도 일치도: {ranked_product.intent_match_score}")
    print(f"  추천 사유: {', '.join(ranked_product.reasons)}")
```

### 추천 결과 변환
```python
# ProductRecommendation으로 변환
recommendations = ranking_service.convert_to_recommendation_response(
    ranked_products=ranked_products,
    top_n=10
)

# 통계 정보
stats = ranking_service.get_ranking_statistics(ranked_products)
print(f"평균 최종 점수: {stats['average_final_score']}")
print(f"평균 의도 일치도: {stats['average_intent_match']}")
```

## 성능 최적화

### 1. 정렬 최적화
- 안정 정렬 알고리즘 사용
- 불필요한 계산 최소화
- 조기 종료 조건 활용

### 2. 메모리 효율성
```python
# 대용량 데이터 처리 시 배치 정렬
def rank_products_batch(self, products_batch: List[List[Product]], ...):
    all_ranked = []
    for batch in products_batch:
        ranked_batch = self.rank_products(batch, ...)
        all_ranked.extend(ranked_batch)
    
    # 전체 재정렬
    return self._apply_tie_break_sorting(all_ranked, request)
```

### 3. 캐싱 전략
- 브랜드 선호도 캐싱
- 카테고리 매칭 결과 캐싱
- 의도 일치도 계산 캐싱

## 모니터링 및 로깅

### 성능 메트릭
```python
def get_performance_metrics(self) -> Dict[str, Any]:
    return {
        'total_rankings': self._ranking_count,
        'total_ranking_time_ms': self._total_ranking_time,
        'avg_ranking_time_ms': self._total_ranking_time / max(self._ranking_count, 1)
    }
```

### 주요 로그 이벤트
- 정렬 시작/완료
- 제품 수 및 처리 시간
- 정렬 기준별 분포
- 예외 상황 및 폴백 처리

## 설정 및 튜닝

### 정렬 가중치 조정
```python
# tie-break 가중치 커스터마이징
ranking_service.tie_break_weights = {
    'final_score': 2000,      # 최종 점수 가중치 증가
    'intent_match': 150,      # 의도 일치도 가중치 증가
    'penalty_count': -15,     # 감점 룰 수 가중치 증가
    'brand_preference': 8,    # 브랜드 선호도 가중치 증가
    'product_id': -1          # 제품 ID 가중치 유지
}
```

### 브랜드 선호도 커스터마이징
```python
# 브랜드 카테고리 확장
premium_brands.update({
    '닥터지', '이소이', '토러스', 'Dr.G', 'IOPE'
})

popular_brands.update({
    '미샤', '홀리카홀리카', '스킨푸드', 'Missha', 'Holika Holika'
})
```

## 확장성 고려사항

### 1. 정렬 기준 확장
- 사용자 리뷰 점수
- 가격 대비 성능
- 재구매율
- 계절성 요소

### 2. 개인화 정렬
- 사용자 선호도 학습
- 구매 이력 기반 가중치
- 피부 타입별 맞춤 정렬

### 3. 실시간 정렬
- 재고 상황 반영
- 프로모션 정보 반영
- 실시간 인기도 반영

## 문제 해결

### 일반적인 문제
1. **정렬 불일치**: tie-break 기준이 명확하지 않은 경우
2. **성능 저하**: 대용량 데이터 정렬 시
3. **편향된 결과**: 특정 브랜드나 카테고리 편중

### 디버깅 팁
- 정렬 키 값 로깅
- 단계별 정렬 결과 확인
- 통계 정보 분석
- A/B 테스트를 통한 검증

## 관련 문서
- [배제 엔진 가이드](ELIGIBILITY_ENGINE_GUIDE.md)
- [감점 엔진 가이드](SCORING_ENGINE_GUIDE.md)
- [추천 엔진 가이드](RECOMMENDATION_ENGINE_GUIDE.md)