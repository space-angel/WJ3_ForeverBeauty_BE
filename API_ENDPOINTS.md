# 화장품 추천 API 엔드포인트 가이드

## 기본 정보
- **Base URL**: `http://localhost:8000` (개발) / `https://your-domain.com` (운영)
- **API Version**: v1
- **Content-Type**: `application/json`

## 📋 목차
1. [추천 API](#추천-api)
2. [관리자 API](#관리자-api)
3. [에러 처리](#에러-처리)
4. [요청/응답 예시](#요청응답-예시)

---

## 🎯 추천 API

### 1. 🚀 메인 제품 추천 (경로 B)
**POST** `/api/v1/recommend`

**고급 3축 스코어링 시스템**으로 개인화된 화장품을 추천합니다.

#### ✨ 주요 특징
- **조건부 성분 분석**: 특수 상황 자동 감지 (알레르기, 의약품, 임신 등)
- **실시간 개인화**: 사용자 프로필 기반 맞춤 추천  
- **안전성 우선**: 실제 성분 DB (1,326개) 기반 검증
- **3축 통합**: 의도 매칭 + 개인화 + 안전성

#### 요청 본문
```json
{
  "intent_tags": ["보습", "미백", "주름개선"],
  "top_n": 10,
  "user_profile": {
    "age_group": "30s",
    "skin_type": "sensitive",
    "skin_concerns": ["건조", "민감"]
  },
  "medications": [
    {
      "name": "와파린",
      "active_ingredients": ["B01AA03"]
    }
  ],
  "usage_context": {
    "season": "winter",
    "time_of_day": "morning"
  },
  "price_range": {
    "min": 10000,
    "max": 50000
  }
}
```

#### 응답
```json
{
  "execution_summary": {
    "request_id": "uuid",
    "timestamp": "2025-11-03T16:30:00Z",
    "success": true,
    "execution_time_seconds": 0.245,
    "ruleset_version": "v2.1",
    "active_rules_count": 28
  },
  "input_summary": {
    "intent_tags_count": 3,
    "requested_count": 10,
    "has_user_profile": true,
    "medications_count": 1,
    "has_usage_context": true,
    "price_range_specified": true
  },
  "pipeline_statistics": {
    "total_candidates": 326,
    "excluded_by_rules": 15,
    "penalized_products": 8,
    "final_recommendations": 10,
    "eligibility_rules_applied": 15,
    "scoring_rules_applied": 23,
    "query_time_ms": 45.2,
    "evaluation_time_ms": 120.8,
    "ranking_time_ms": 78.5,
    "total_time_ms": 244.5
  },
  "recommendations": [
    {
      "rank": 1,
      "product_id": "12345",
      "product_name": "PDRN 5% 액티브 앰플",
      "brand_name": "브랜드명",
      "category": "세럼/앰플",
      "final_score": 94.4,
      "base_score": 100.0,
      "penalty_score": 5.6,
      "intent_match_score": 98.2,
      "reasons": [
        "요청하신 미백, 주름개선에 매우 적합한 제품입니다",
        "안전성 우려가 없어 안심하고 사용할 수 있습니다",
        "전문가들이 신뢰하는 브랜드입니다"
      ],
      "warnings": [],
      "rule_hits": [
        {
          "type": "penalize",
          "rule_id": "SC-SENSITIVE-FRAGRANCE",
          "weight": 5,
          "rationale_ko": "민감성 피부에 향료 성분 주의",
          "citation_url": ["https://example.com/study"]
        }
      ]
    }
  ]
}
```

### 2. 추천 시스템 헬스체크
**GET** `/api/v1/recommend/health`

추천 시스템의 상태를 확인합니다.

#### 응답
```json
{
  "status": "healthy",
  "service": "recommendation",
  "timestamp": "2025-11-03T16:30:00Z",
  "version": "1.0.0"
}
```

---

## 🔧 관리자 API

### 1. 전체 시스템 상태
**GET** `/api/v1/admin/health`

전체 시스템의 상태를 종합적으로 확인합니다.

#### 응답
```json
{
  "status": "healthy",
  "ruleset": {
    "ruleset_version": "v2.1",
    "total_rules": 45,
    "active_rules": 28,
    "eligibility_rules": 15,
    "scoring_rules": 13,
    "expired_rules": 2,
    "total_aliases": 120,
    "postgres_status": "connected",
    "avg_response_time_ms": 245.5,
    "error_rate_percent": 0.2,
    "last_updated": "2025-11-03T16:00:00Z"
  },
  "timestamp": "2025-11-03T16:30:00Z"
}
```

### 2. 시스템 통계
**GET** `/api/v1/admin/stats`

시스템의 상세한 통계 정보를 제공합니다.

#### 쿼리 파라미터
- `period`: 통계 기간 (`1h`, `24h`, `7d`, `30d`) - 기본값: `24h`
- `include_details`: 상세 정보 포함 여부 (`true`/`false`) - 기본값: `false`

#### 응답
```json
{
  "period": "24h",
  "request_stats": {
    "total_requests": 1250,
    "successful_requests": 1235,
    "failed_requests": 15,
    "success_rate_percent": 98.8,
    "avg_response_time_ms": 245.5
  },
  "recommendation_stats": {
    "total_recommendations": 6175,
    "avg_recommendations_per_request": 4.94,
    "most_common_intent_tags": ["moisturizing", "anti-aging", "cleansing"],
    "category_distribution": {
      "모이스처라이저": 25.2,
      "세럼": 18.7,
      "클렌저": 15.3,
      "크림": 12.8,
      "기타": 28.0
    }
  },
  "rule_stats": {
    "eligibility_rules_triggered": 145,
    "scoring_rules_triggered": 89,
    "most_triggered_rules": ["medication_interaction", "age_restriction", "skin_type_mismatch"]
  },
  "timestamp": "2025-11-03T16:30:00Z"
}
```

### 3. 룰 관리
**GET** `/api/v1/admin/rules`

시스템에서 사용 중인 룰들의 상태를 조회합니다.

#### 쿼리 파라미터
- `rule_type`: 룰 타입 필터 (`eligibility`, `scoring`)
- `active_only`: 활성 룰만 조회 (`true`/`false`) - 기본값: `true`

### 4. 캐시 초기화
**POST** `/api/v1/admin/cache/clear`

시스템 캐시를 초기화합니다.

#### 쿼리 파라미터
- `cache_type`: 캐시 타입 (`rules`, `products`, `all`)

---

## ⚠️ 에러 처리

### HTTP 상태 코드
- `200`: 성공
- `400`: 잘못된 요청 (필수 필드 누락, 잘못된 형식 등)
- `401`: 인증 필요 (관리자 API)
- `403`: 권한 없음 (관리자 API)
- `500`: 서버 내부 오류

### 에러 응답 형식
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "요청 데이터가 올바르지 않습니다",
    "field": "intent_tags",
    "details": {
      "expected_type": "array",
      "received_type": "string"
    }
  },
  "timestamp": "2025-11-03T16:30:00Z",
  "path": "/api/v1/recommend"
}
```

---

## 📝 요청/응답 예시

### 기본 추천 요청
```bash
curl -X POST "http://localhost:8000/api/v1/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "intent_tags": ["보습", "민감성피부"],
    "top_n": 5,
    "user_profile": {
      "age_group": "30s",
      "skin_type": "sensitive"
    }
  }'
```

### 의약품 복용자 추천 요청
```bash
curl -X POST "http://localhost:8000/api/v1/recommend" \
  -H "Content-Type: application/json" \
  -d '{
    "intent_tags": ["미백", "주름개선"],
    "top_n": 10,
    "user_profile": {
      "age_group": "40s",
      "skin_type": "normal"
    },
    "medications": [
      {
        "name": "와파린",
        "active_ingredients": ["B01AA03"]
      }
    ]
  }'
```

### 헬스체크
```bash
curl -X GET "http://localhost:8000/api/v1/recommend/health"
```

---

## 🔍 주요 필드 설명

### intent_tags (의도 태그)
- `"보습"`, `"미백"`, `"주름개선"`, `"여드름"`, `"민감성피부"`, `"각질제거"` 등
- 사용자가 원하는 화장품의 기능이나 효과

### age_group (연령대)
- `"10s"`, `"20s"`, `"30s"`, `"40s"`, `"50s"`, `"60s+"`

### skin_type (피부 타입)
- `"oily"` (지성), `"dry"` (건성), `"combination"` (복합성), `"sensitive"` (민감성), `"normal"` (보통)

### medications (의약품)
- `active_ingredients`: 의약품 코드 배열 (ATC 코드 또는 시스템 정의 코드)

---

## 🚀 개발 팁

1. **응답 시간**: 일반적으로 200-300ms 내외
2. **캐싱**: 동일한 요청은 캐시되어 더 빠른 응답
3. **배치 처리**: 여러 사용자의 추천을 한 번에 요청하는 API는 현재 미지원
4. **실시간 업데이트**: 룰 변경 시 `/admin/cache/clear` 호출 필요

---

## 📞 문의사항
- 백엔드 팀: [연락처]
- API 문서 업데이트: [날짜]