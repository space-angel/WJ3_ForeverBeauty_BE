# 화장품 추천 API 설계 문서

## Overview

화장품 추천 시스템은 사용자 입력을 받아 제품 후보군을 축소하고, 배제(강제 제외) → 감점(점수 감산) → 동점 정렬을 수행하는 안전성 중심의 보수적 추천 API입니다. 기존 cosmetics.db와 새로운 룰 시스템(JSON)을 통합하여 구현합니다.

## Architecture

### Database Strategy

**Primary Database**: SQLite (cosmetics.db) - 제품 및 성분 데이터
**Secondary Database**: PostgreSQL (Supabase) - 룰 관리 및 로깅

이 하이브리드 접근법의 장점:
- ✅ 기존 cosmetics.db 데이터를 그대로 활용
- ✅ 룰 관리는 PostgreSQL의 JSONB와 고급 기능 활용
- ✅ 로깅과 분석은 클라우드 DB에서 처리
- ✅ 개발 복잡도 최소화

### High-Level Architecture

```
[Client Request] 
    ↓
[Input Validator] 
    ↓
[Query Builder] (SQLite: products 테이블에서 1차 필터)
    ↓
[Ingredients Loader] (SQLite: ingredients + product_ingredients)
    ↓
[Rule Loader] (PostgreSQL: rules 테이블에서 룰 로드)
    ↓
[Eligibility Engine] (배제 룰 평가) → [EXCLUDED PRODUCTS]
    ↓
[Scoring Engine] (감점 룰 평가)
    ↓
[Ranker] (tie-break rules)
    ↓
[Logger] (PostgreSQL: rule_hit_log에 기록)
    ↓
[Formatter] (rationale/trace 포함)
    ↓
[JSON Response]
```

### Component Architecture

```
app/
├── main.py                    # FastAPI 앱 진입점
├── database/
│   ├── sqlite_db.py          # SQLite (cosmetics.db) 연결
│   ├── postgres_db.py        # PostgreSQL (Supabase) 연결
│   └── models.py             # SQLAlchemy 모델 (PostgreSQL용)
├── models/
│   ├── request.py           # 입력 스키마 (Pydantic)
│   ├── response.py          # 출력 스키마 (Pydantic)
│   └── sqlite_models.py     # SQLite 데이터 모델
├── services/
│   ├── rule_service.py      # 룰 로딩 및 관리 (PostgreSQL)
│   ├── product_service.py   # 제품 조회 (SQLite)
│   ├── ingredient_service.py # 성분 조회 및 태그 매핑 (SQLite)
│   ├── eligibility_engine.py # 배제 엔진
│   ├── scoring_engine.py    # 감점 엔진
│   └── ranking_service.py   # 정렬 및 포맷팅
├── utils/
│   ├── alias_mapper.py      # MULTI 별칭 매핑
│   ├── validators.py        # 입력 검증
│   └── logger_service.py    # 로깅 (PostgreSQL)
└── routers/
    └── recommendations.py   # API 엔드포인트
```

## Components and Interfaces

### 1. Input Validator

**책임**: 사용자 입력 검증 및 기본값 설정

```python
class RecommendationRequest(BaseModel):
    intent_tags: List[str] = []
    category_like: Optional[str] = None
    use_context: UseContext
    med_profile: MedProfile
    price: PriceRange
    top_n: int = 10

class UseContext(BaseModel):
    leave_on: bool = False
    day_use: bool = False
    face: bool = False
    large_area_hint: bool = False

class MedProfile(BaseModel):
    codes: List[str] = []
    preg_lact: bool = False
```

### 2. Product Service (SQLite)

**책임**: cosmetics.db에서 1차 후보군 조회

```python
class ProductService:
    def __init__(self):
        self.sqlite_conn = sqlite3.connect('cosmetics.db')
    
    def get_candidate_products(
        self, 
        category_like: str, 
        price_min: int, 
        price_max: int
    ) -> List[Dict]:
        # SQLite에서 직접 쿼리
        query = """
        SELECT * FROM products 
        WHERE category LIKE ? 
        AND price BETWEEN ? AND ?
        """
        return self.sqlite_conn.execute(query, (category_like, price_min, price_max)).fetchall()
```

### 3. Ingredient Service (SQLite)

**책임**: 제품별 성분 로딩 및 canonical tag 매핑

```python
class IngredientService:
    def __init__(self):
        self.sqlite_conn = sqlite3.connect('cosmetics.db')
    
    def load_product_ingredients(self, product_id: int) -> List[Dict]:
        query = """
        SELECT i.korean, i.english, i.tags, i.ewg_grade, i.is_allergy
        FROM product_ingredients pi
        JOIN ingredients i ON pi.ingredient_id = i.ingredient_id
        WHERE pi.product_id = ?
        """
        return self.sqlite_conn.execute(query, (product_id,)).fetchall()
    
    def get_canonical_tags(self, ingredients: List[Dict]) -> List[str]:
        tags = []
        for ingredient in ingredients:
            if ingredient['tags']:
                tags.extend(json.loads(ingredient['tags']))
        return list(set(tags))  # 중복 제거
```

### 4. Rule Service (PostgreSQL)

**책임**: 룰 로딩 및 관리

```python
class RuleService:
    def __init__(self):
        self.postgres_session = get_postgres_session()
    
    def load_eligibility_rules(self) -> List[Dict]:
        # PostgreSQL rules 테이블에서 배제 룰 조회
        return self.postgres_session.query(Rule).filter(
            Rule.rule_type == 'eligibility',
            Rule.active == True,
            Rule.expires_at > datetime.now()
        ).all()
    
    def load_scoring_rules(self) -> List[Dict]:
        # PostgreSQL rules 테이블에서 감점 룰 조회
        return self.postgres_session.query(Rule).filter(
            Rule.rule_type == 'scoring',
            Rule.active == True
        ).all()

### 5. Eligibility Engine

**책임**: 배제 룰 평가 및 제품 제외

```python
class EligibilityEngine:
    def __init__(self, rule_service: RuleService):
        self.rule_service = rule_service
        self.rules = rule_service.load_eligibility_rules()
    
    def evaluate_exclusion(
        self, 
        product_tags: List[str], 
        request: RecommendationRequest
    ) -> Optional[RuleHit]:
        # 룰별로 평가하여 배제 여부 결정
        for rule in self.rules:
            if self._matches_rule(rule, product_tags, request):
                return RuleHit(
                    type='exclude',
                    rule_id=rule.rule_id,
                    weight=rule.weight,
                    rationale_ko=rule.rationale_ko
                )
        return None
```

### 5. Scoring Engine

**책임**: 감점 룰 평가 및 점수 계산

```python
class ScoringEngine:
    def __init__(self):
        self.rules = self.load_scoring_rules()
        self.alias_mapper = AliasMapper()
    
    def calculate_penalties(
        self, 
        product: Product, 
        request: RecommendationRequest
    ) -> ScoringResult:
        # scoring_rules.json 기반 평가
        # MULTI 별칭 해석 및 누적 감점
        pass
```

### 6. Ranker

**책임**: 최종 정렬 및 tie-break 규칙 적용

```python
class RankingService:
    def rank_products(self, products: List[ScoredProduct]) -> List[RankedProduct]:
        # 1. final_score 내림차순
        # 2. intent_match_score 내림차순  
        # 3. total_penalty 오름차순
        # 4. review_score 내림차순
        # 5. price_diff_from_midrange 오름차순
        # 6. brand_tier_value 내림차순
        # 7. last_update_ts 내림차순
        pass
```

## Data Models

### Database Schema

#### SQLite (cosmetics.db) - 읽기 전용
기존 테이블을 그대로 활용:
- `products`: 제품 정보 (id, name, category, price 등)
- `ingredients`: 성분 정보 (korean, english, tags, ewg_grade 등)
- `product_ingredients`: 제품-성분 관계

#### PostgreSQL (Supabase) - 룰 관리 및 로깅

```sql
-- 룰 테이블 (배제/감점 통합)
CREATE TABLE rules (
    rule_id TEXT PRIMARY KEY,
    rule_type TEXT CHECK (rule_type IN ('eligibility', 'scoring')),
    rule_group TEXT,
    med_code TEXT,
    med_name_ko TEXT,
    ingredient_tag TEXT,
    match_type TEXT CHECK (match_type IN ('tag', 'regex')),
    condition_json JSONB,
    action TEXT CHECK (action IN ('exclude', 'penalize')),
    severity INTEGER,
    weight INTEGER,
    confidence TEXT CHECK (confidence IN ('high', 'moderate', 'low')),
    rationale_ko TEXT,
    citation_source TEXT,
    citation_url JSONB,
    reviewer TEXT,
    reviewed_at DATE,
    expires_at DATE,
    ruleset_version TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    active BOOLEAN DEFAULT TRUE
);

-- MULTI 별칭 매핑
CREATE TABLE med_alias_map (
    alias TEXT PRIMARY KEY,
    atc_codes TEXT[] NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 룰 히트 로그
CREATE TABLE rule_hit_log (
    id BIGSERIAL PRIMARY KEY,
    request_id UUID NOT NULL,
    product_id INTEGER,
    rule_id TEXT REFERENCES rules(rule_id),
    hit_type TEXT CHECK (hit_type IN ('exclude', 'penalize')),
    weight_applied INTEGER,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 요청 로그
CREATE TABLE recommendation_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    input_data JSONB NOT NULL,
    execution_time_seconds NUMERIC,
    products_found INTEGER,
    products_excluded INTEGER,
    products_recommended INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Response Data Models

```python
class RecommendationResponse(BaseModel):
    execution_summary: ExecutionSummary
    input_summary: dict
    pipeline_statistics: PipelineStatistics
    recommendations: List[ProductRecommendation]

class ProductRecommendation(BaseModel):
    rank: int
    product_id: int
    product_name: str
    final_score: int
    base_score: int = 100
    penalty_score: int
    intent_match_score: int
    reasons: List[str]
    rule_hits: List[RuleHit]

class RuleHit(BaseModel):
    type: str  # 'exclude' | 'penalize'
    rule_id: str
    weight: int
    rationale_ko: str
```

## Error Handling

### Input Validation Errors (400)
- 스키마 불일치
- 가격 범위 역전 (min > max)
- 필수 필드 누락
- 잘못된 ATC 코드 형식

### Business Logic Errors (422)
- 후보 제품 없음
- 모든 제품 배제됨
- 룰 평가 실패

### System Errors (500)
- 데이터베이스 연결 실패
- 룰 로딩 실패
- 내부 계산 오류

### Error Response Format

```json
{
  "error": {
    "code": "INVALID_PRICE_RANGE",
    "message": "가격 범위가 잘못되었습니다",
    "details": {
      "min_price": 50000,
      "max_price": 10000
    }
  },
  "timestamp": "2025-10-27T10:30:00+09:00"
}
```

## Testing Strategy

### Unit Tests
- **Input Validator**: 스키마 검증 및 기본값 설정
- **Eligibility Engine**: 개별 룰 평가 로직
- **Scoring Engine**: 감점 계산 및 누적 로직
- **Alias Mapper**: MULTI 별칭 매핑 정확성
- **Ranking Service**: 정렬 알고리즘 검증

### Integration Tests
- **Database Integration**: cosmetics.db 연동 테스트
- **Rule Loading**: JSON 룰 파일 로딩 및 DB 저장
- **End-to-End Pipeline**: 전체 추천 파이프라인 테스트

### Performance Tests
- **Response Time**: 목표 < 500ms
- **Concurrent Requests**: 동시 요청 처리 능력
- **Large Dataset**: 대용량 제품 데이터 처리

### Test Data
- **Mock Products**: 다양한 카테고리/가격대 제품
- **Mock Ingredients**: 주요 canonical tags 포함
- **Test Rules**: 각 룰 타입별 샘플 데이터
- **Edge Cases**: 경계값 및 예외 상황

## Performance Considerations

### Database Optimization
- **SQLite 최적화**: 읽기 전용 연결, 인덱스 활용, 메모리 캐싱
- **PostgreSQL 최적화**: 룰 데이터 캐싱, 배치 로깅
- **연결 관리**: SQLite는 단순 연결, PostgreSQL은 connection pool

### Caching Strategy
- **Rule Caching**: 룰 데이터를 메모리에 캐싱 (TTL: 1시간)
- **Ingredient Caching**: 자주 조회되는 성분 정보 캐싱
- **Redis Integration**: 분산 캐싱 고려

### Algorithm Optimization
- **Early Exit**: 배제 룰 히트 시 즉시 중단
- **Batch Processing**: 여러 제품 동시 평가
- **Parallel Evaluation**: 독립적인 룰 병렬 처리

## Security Considerations

### Input Sanitization
- SQL Injection 방지: SQLAlchemy ORM 사용
- JSON Injection 방지: Pydantic 스키마 검증
- XSS 방지: 출력 데이터 이스케이핑

### Rate Limiting
- API 호출 제한: 사용자당 분당 60회
- 리소스 보호: 대용량 요청 제한

### Data Privacy
- 개인정보 로깅 금지
- 의료 정보 암호화 저장 고려
- GDPR 준수: 데이터 보존 기간 설정