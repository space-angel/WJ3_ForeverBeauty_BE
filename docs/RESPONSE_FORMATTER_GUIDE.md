# 결과 포매터 (Response Formatter) 기술문서

## 개요

결과 포매터는 추천 파이프라인의 최종 단계에서 내부 데이터 구조를 클라이언트가 사용할 수 있는 표준화된 API 응답 형태로 변환하는 시스템입니다. 실행 요약, 파이프라인 통계, 추천 결과를 포함한 종합적인 응답을 생성합니다.

## 핵심 기능

### 1. 응답 구조 표준화
- 일관된 API 응답 형태 제공
- 성공/실패 상황별 적절한 응답 생성
- 클라이언트 친화적 데이터 형태 변환

### 2. 실행 통계 제공
- 파이프라인 각 단계별 성능 메트릭
- 룰 적용 통계 및 처리 시간
- 디버깅을 위한 상세 정보

### 3. 에러 처리 및 로깅
- 구조화된 에러 응답
- 상세한 에러 정보 제공
- 안전한 에러 메시지 노출

## 응답 구조

### RecommendationResponse (메인 응답)
```python
class RecommendationResponse(BaseModel):
    execution_summary: ExecutionSummary      # 실행 요약
    input_summary: Dict[str, Any]           # 입력 요약
    pipeline_statistics: PipelineStatistics # 파이프라인 통계
    recommendations: List[RecommendationItem] # 추천 결과
```

### ExecutionSummary (실행 요약)
```python
class ExecutionSummary(BaseModel):
    request_id: UUID                    # 요청 고유 ID
    timestamp: datetime                 # 응답 생성 시간
    success: bool                       # 성공 여부
    execution_time_seconds: float       # 총 실행 시간
    ruleset_version: str               # 룰셋 버전
    active_rules_count: int            # 활성 룰 수
```

### PipelineStatistics (파이프라인 통계)
```python
class PipelineStatistics(BaseModel):
    total_candidates: int              # 총 후보 제품 수
    excluded_by_rules: int             # 룰에 의해 배제된 제품 수
    penalized_products: int            # 감점된 제품 수
    final_recommendations: int         # 최종 추천 제품 수
    eligibility_rules_applied: int     # 적용된 배제 룰 수
    scoring_rules_applied: int         # 적용된 감점 룰 수
    query_time_ms: float              # 쿼리 시간
    evaluation_time_ms: float         # 평가 시간
    ranking_time_ms: float            # 정렬 시간
    total_time_ms: float              # 총 처리 시간
```

### RecommendationItem (추천 아이템)
```python
class RecommendationItem(BaseModel):
    rank: int                         # 추천 순위
    product_id: str                   # 제품 ID
    product_name: str                 # 제품명
    brand_name: str                   # 브랜드명
    category: str                     # 카테고리
    final_score: float                # 최종 점수
    intent_match_score: float         # 의도 일치도
    reasons: List[str]                # 추천 사유
    warnings: List[str]               # 경고 메시지
    rule_hits: List[RuleHit]          # 적용된 룰 정보
```

### RuleHit (룰 적용 정보)
```python
class RuleHit(BaseModel):
    type: str                         # 'exclude' | 'penalize'
    rule_id: str                      # 룰 ID
    weight: int                       # 가중치/감점
    rationale_ko: str                 # 한국어 설명
    citation_url: Optional[str]       # 근거 자료 URL
```

## 포맷팅 프로세스

### 1. 성공 응답 생성
```python
def _build_response(
    self,
    request: RecommendationRequest,
    request_id: UUID,
    pipeline: RecommendationPipeline,
    start_time: datetime
) -> RecommendationResponse:
    """응답 객체 생성"""
    
    execution_time = (datetime.now() - start_time).total_seconds()
    
    # 실행 요약 생성
    execution_summary = ExecutionSummary(
        request_id=request_id,
        timestamp=datetime.now(),
        success=True,
        execution_time_seconds=execution_time,
        ruleset_version="v2.1",
        active_rules_count=28
    )
    
    # 파이프라인 통계 생성
    pipeline_stats = PipelineStatistics(
        total_candidates=pipeline.statistics['total_candidates'],
        excluded_by_rules=pipeline.statistics['excluded_count'],
        penalized_products=pipeline.statistics['penalized_count'],
        final_recommendations=len(pipeline.ranked_products),
        eligibility_rules_applied=pipeline.statistics['eligibility_rules'],
        scoring_rules_applied=pipeline.statistics['scoring_rules'],
        query_time_ms=pipeline.statistics['query_time_ms'],
        evaluation_time_ms=pipeline.statistics['evaluation_time_ms'],
        ranking_time_ms=pipeline.statistics['ranking_time_ms'],
        total_time_ms=execution_time * 1000
    )
    
    # 추천 아이템 변환
    recommendations = self._convert_to_recommendation_items(
        pipeline.ranked_products[:request.top_n]
    )
    
    # 입력 요약 생성
    input_summary = self._generate_input_summary(request)
    
    return RecommendationResponse(
        execution_summary=execution_summary,
        input_summary=input_summary,
        pipeline_statistics=pipeline_stats,
        recommendations=recommendations
    )
```

### 2. 추천 아이템 변환
```python
def _convert_to_recommendation_items(
    self, 
    ranked_products: List[RankedProduct]
) -> List[RecommendationItem]:
    """RankedProduct를 RecommendationItem으로 변환"""
    
    recommendations = []
    
    for ranked_product in ranked_products:
        # 경고 메시지 생성
        warnings = self._generate_warnings(ranked_product)
        
        recommendation = RecommendationItem(
            rank=ranked_product.rank,
            product_id=str(ranked_product.product.product_id),
            product_name=ranked_product.product.name,
            brand_name=ranked_product.product.brand_name or "Unknown",
            category=ranked_product.product.category_name or "Unknown",
            final_score=round(ranked_product.final_score, 1),
            intent_match_score=round(ranked_product.intent_match_score, 1),
            reasons=ranked_product.reasons[:3],  # 최대 3개
            warnings=warnings,
            rule_hits=ranked_product.rule_hits
        )
        
        recommendations.append(recommendation)
    
    return recommendations
```

### 3. 경고 메시지 생성
```python
def _generate_warnings(self, ranked_product: RankedProduct) -> List[str]:
    """제품별 경고 메시지 생성"""
    warnings = []
    
    # 감점 기반 경고
    if ranked_product.penalty_score > 25:
        warnings.append("여러 주의사항이 있으니 사용 전 전문가와 상담하세요")
    elif ranked_product.penalty_score > 15:
        warnings.append("일부 주의사항이 있으니 신중히 사용하세요")
    
    # 룰 히트 기반 경고
    high_risk_rules = [
        hit for hit in ranked_product.rule_hits 
        if hit.weight > 50 or 'high' in hit.rule_id.lower()
    ]
    
    if high_risk_rules:
        warnings.append("고위험 상호작용 가능성이 있습니다")
    
    # 특정 성분 경고
    for rule_hit in ranked_product.rule_hits:
        if 'anticoagulant' in rule_hit.rule_id.lower():
            warnings.append("항응고제 복용 중이시라면 특히 주의하세요")
        elif 'pregnancy' in rule_hit.rule_id.lower():
            warnings.append("임신 중에는 사용을 피해주세요")
    
    return warnings[:2]  # 최대 2개까지
```

### 4. 입력 요약 생성
```python
def _generate_input_summary(self, request: RecommendationRequest) -> Dict[str, Any]:
    """입력 요청 요약 생성"""
    
    return {
        "intent_tags": request.intent_tags,
        "intent_tags_count": len(request.intent_tags),
        "requested_count": request.top_n,
        "has_user_profile": request.user_profile is not None,
        "has_med_profile": request.med_profile is not None,
        "medications_count": len(request.med_profile.codes) if request.med_profile else 0,
        "has_use_context": request.use_context is not None,
        "category_filter": request.category_like,
        "price_range_specified": request.price_range is not None,
        "pregnancy_lactation": request.med_profile.preg_lact if request.med_profile else False
    }
```

## 에러 응답 처리

### 1. 에러 응답 구조
```python
class ErrorResponse(BaseModel):
    error: ErrorDetail
    timestamp: datetime
    path: str

class ErrorDetail(BaseModel):
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
```

### 2. 에러 응답 생성
```python
def _build_error_response(
    self,
    request: RecommendationRequest,
    request_id: UUID,
    start_time: datetime,
    error: Exception
) -> RecommendationResponse:
    """에러 응답 생성"""
    
    execution_time = (datetime.now() - start_time).total_seconds()
    
    # 실행 요약 (실패)
    execution_summary = ExecutionSummary(
        request_id=request_id,
        timestamp=datetime.now(),
        success=False,
        execution_time_seconds=execution_time,
        ruleset_version="v2.1",
        active_rules_count=0    
    )
    
    # 기본 통계 (실패 시)
    pipeline_stats = PipelineStatistics(
        total_candidates=0,
        excluded_by_rules=0,
        penalized_products=0,
        final_recommendations=0,
        eligibility_rules_applied=0,
        scoring_rules_applied=0,
        query_time_ms=0,
        evaluation_time_ms=0,
        ranking_time_ms=0,
        total_time_ms=execution_time * 1000
    )
    
    # 에러 정보 포함
    input_summary = {
        "error": str(error),
        "error_type": type(error).__name__,
        "request_valid": False
    }
    
    return RecommendationResponse(
        execution_summary=execution_summary,
        input_summary=input_summary,
        pipeline_statistics=pipeline_stats,
        recommendations=[]
    )
```

## 응답 최적화

### 1. 데이터 크기 최적화
```python
def _optimize_response_size(self, response: RecommendationResponse) -> RecommendationResponse:
    """응답 크기 최적화"""
    
    # 추천 사유 길이 제한
    for item in response.recommendations:
        item.reasons = [reason[:100] for reason in item.reasons[:3]]
        
        # 룰 히트 정보 간소화
        for rule_hit in item.rule_hits:
            if rule_hit.rationale_ko and len(rule_hit.rationale_ko) > 150:
                rule_hit.rationale_ko = rule_hit.rationale_ko[:147] + "..."
    
    return response
```

### 2. 민감 정보 필터링
```python
def _sanitize_response(self, response: RecommendationResponse) -> RecommendationResponse:
    """민감 정보 제거"""
    
    # 내부 시스템 정보 제거
    for item in response.recommendations:
        for rule_hit in item.rule_hits:
            # 내부 룰 ID 마스킹
            if rule_hit.rule_id.startswith('INTERNAL_'):
                rule_hit.rule_id = 'SYSTEM_RULE'
            
            # 개발용 URL 제거
            if rule_hit.citation_url and 'localhost' in rule_hit.citation_url:
                rule_hit.citation_url = None
    
    return response
```

## 사용 예시

### 기본 사용법
```python
from app.services.recommendation_engine import RecommendationEngine

# 추천 엔진 초기화
engine = RecommendationEngine()

# 추천 요청 처리
request = RecommendationRequest(
    intent_tags=["moisturizing", "sensitive_skin"],
    top_n=5
)

# 추천 실행 및 응답 생성
response = await engine.recommend(request)

# 응답 확인
print(f"성공: {response.execution_summary.success}")
print(f"실행 시간: {response.execution_summary.execution_time_seconds:.2f}초")
print(f"총 후보: {response.pipeline_statistics.total_candidates}개")
print(f"최종 추천: {len(response.recommendations)}개")

# 추천 결과 출력
for item in response.recommendations:
    print(f"{item.rank}. {item.product_name} ({item.brand_name})")
    print(f"   점수: {item.final_score}, 의도 일치: {item.intent_match_score}")
    print(f"   사유: {', '.join(item.reasons)}")
    if item.warnings:
        print(f"   경고: {', '.join(item.warnings)}")
```

### 에러 처리
```python
try:
    response = await engine.recommend(request)
    
    if not response.execution_summary.success:
        print(f"추천 실패: {response.input_summary.get('error', 'Unknown error')}")
        return
    
    # 정상 처리
    process_recommendations(response.recommendations)
    
except HTTPException as e:
    print(f"API 에러: {e.detail}")
except Exception as e:
    print(f"시스템 에러: {e}")
```

## 성능 고려사항

### 1. 응답 시간 최적화
- 불필요한 데이터 제거
- 지연 로딩 적용
- 캐싱 활용

### 2. 메모리 효율성
- 대용량 응답 스트리밍
- 객체 재사용
- 가비지 컬렉션 최적화

### 3. 네트워크 최적화
- 응답 압축
- 필드 선택적 포함
- 페이지네이션 지원

## 모니터링 및 로깅

### 응답 품질 메트릭
```python
def track_response_quality(response: RecommendationResponse):
    """응답 품질 추적"""
    
    # 응답 크기
    response_size = len(str(response))
    
    # 추천 품질
    avg_score = sum(item.final_score for item in response.recommendations) / len(response.recommendations)
    
    # 다양성
    unique_brands = len(set(item.brand_name for item in response.recommendations))
    unique_categories = len(set(item.category for item in response.recommendations))
    
    logger.info(f"응답 품질 - 크기: {response_size}bytes, 평균점수: {avg_score:.1f}, "
               f"브랜드 다양성: {unique_brands}, 카테고리 다양성: {unique_categories}")
```

## 확장성 고려사항

### 1. 응답 형태 확장
- 다국어 지원
- 모바일 최적화 응답
- GraphQL 스키마 지원

### 2. 개인화 확장
- 사용자별 맞춤 응답
- A/B 테스트 지원
- 실시간 개인화

### 3. 통합 확장
- 외부 시스템 연동
- 웹훅 지원
- 배치 처리 지원

## 문제 해결

### 일반적인 문제
1. **응답 크기 과대**: 불필요한 데이터 포함
2. **응답 시간 지연**: 복잡한 변환 로직
3. **데이터 불일치**: 내부-외부 모델 매핑 오류

### 디버깅 팁
- 응답 구조 검증
- 변환 단계별 로깅
- 성능 프로파일링
- 응답 크기 모니터링

## 관련 문서
- [추천 엔진 가이드](RECOMMENDATION_ENGINE_GUIDE.md)
- [API 명세서](FRONTEND_API_GUIDE.md)
- [에러 처리 가이드](ERROR_HANDLING_GUIDE.md)