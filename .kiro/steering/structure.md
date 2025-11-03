# 프로젝트 구조

## 디렉토리 구조

```
app/
├── api/                    # API 엔드포인트
│   ├── recommendation.py   # 추천 API
│   └── admin.py           # 관리자 API
├── config/                # 설정 파일
│   └── intent_config.py   # 의도 태그 설정
├── database/              # 데이터베이스 연결
│   ├── postgres_db.py     # 비동기 PostgreSQL
│   └── postgres_sync.py   # 동기 PostgreSQL
├── models/                # 데이터 모델
│   ├── request.py         # 요청 모델
│   ├── response.py        # 응답 모델
│   ├── postgres_models.py # DB 모델
│   └── personalization_models.py # 개인화 모델
├── services/              # 비즈니스 로직
│   ├── recommendation_engine.py    # 메인 추천 엔진
│   ├── eligibility_engine.py      # 자격 검증 엔진
│   ├── scoring_engine.py          # 점수 계산 엔진
│   ├── ranking_service.py         # 순위 서비스
│   ├── product_service.py         # 제품 서비스
│   ├── ingredient_service.py      # 성분 서비스
│   ├── intent_matching_service.py # 의도 매칭 서비스
│   ├── enhanced_name_matcher.py   # 이름 매칭
│   ├── enhanced_semantic_matcher.py # 의미 매칭
│   ├── rule_service.py            # 룰 서비스
│   └── health_service.py          # 헬스체크 서비스
└── utils/                 # 유틸리티
    ├── time_tracker.py    # 시간 측정
    ├── fallback_factory.py # 폴백 처리
    ├── alias_mapper.py    # 별칭 매핑
    └── validators.py      # 검증 함수
```

## 아키텍처 패턴

### 레이어드 아키텍처
- **API Layer**: FastAPI 라우터로 HTTP 요청 처리
- **Service Layer**: 비즈니스 로직과 추천 알고리즘
- **Data Layer**: PostgreSQL 데이터 접근 및 모델

### 추천 파이프라인
1. **API Layer** (`api/recommendation.py`) - 요청 수신 및 응답
2. **Engine Layer** (`services/recommendation_engine.py`) - 추천 파이프라인 조율
3. **Service Layer** - 각 단계별 전문 서비스
4. **Data Layer** - 데이터베이스 및 모델 접근

## 코딩 컨벤션

### 파일 명명
- 서비스: `{기능}_service.py`
- 엔진: `{기능}_engine.py`
- 모델: `{용도}_models.py`
- API: 기능명으로 명명

### 클래스 구조
- 서비스 클래스는 단일 책임 원칙 준수
- 의존성 주입을 통한 느슨한 결합
- 에러 처리 및 로깅 포함

### 데이터 모델
- **Pydantic**: API 요청/응답 모델
- **Dataclass**: 내부 데이터 구조 (Product, Ingredient)
- **SQLAlchemy**: 데이터베이스 모델 (필요시)

### 한국어 지원
- 주석과 문서화는 한국어 사용
- 로그 메시지는 한국어로 작성
- API 문서의 설명은 한국어 제공
- 에러 메시지는 한국어로 사용자에게 제공