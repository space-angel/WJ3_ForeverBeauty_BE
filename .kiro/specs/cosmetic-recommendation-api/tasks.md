# Implementation Plan

- [x] 1. 기존 프로젝트 확장 및 패키지 추가
  - 기존 app/ 구조에 새 폴더 추가 (services/, utils/, models/)
  - SQLite 연결을 위한 패키지 추가 (이미 설치된 패키지 활용)
  - _Requirements: 1.1, 8.1_

- [x] 2. 데이터베이스 연결 설정
- [x] 2.1 SQLite 연결 모듈 구현
  - cosmetics.db 연결 및 기본 쿼리 테스트
  - 제품, 성분, 제품-성분 관계 테이블 접근 확인
  - _Requirements: 5.1, 5.2_

- [x] 2.2 기존 PostgreSQL에 룰 테이블 추가
  - 기존 database.py를 확장하여 새 테이블 모델 추가
  - rules, med_alias_map, rule_hit_log, recommendation_requests 테이블 생성
  - _Requirements: 8.2, 8.3_

- [x] 2.3 JSON 룰 데이터 로딩
  - scoring_rules.json과 eligibility_rules.json을 PostgreSQL에 삽입
  - MULTI 별칭 매핑 데이터 생성 및 삽입
  - _Requirements: 8.2, 9.4_

- [x] 3. 입력/출력 모델 정의
- [x] 3.1 Pydantic 요청 스키마 구현
  - RecommendationRequest, UseContext, MedProfile, PriceRange 모델
  - 입력 검증 및 기본값 설정
  - _Requirements: 1.2, 1.4_

- [x] 3.2 Pydantic 응답 스키마 구현
  - RecommendationResponse, ProductRecommendation, RuleHit 모델
  - 실행 통계 및 파이프라인 정보 포함
  - _Requirements: 1.3, 6.3_

- [x] 4. 핵심 서비스 구현
- [x] 4.1 제품 조회 서비스 구현
  - SQLite에서 카테고리/가격 기반 1차 필터링
  - 제품 기본 정보 조회 기능
  - _Requirements: 1.1, 5.2_

- [x] 4.2 성분 서비스 구현
  - 제품별 성분 정보 조회 (SQLite JOIN 쿼리)
  - canonical tags 추출 및 정규화
  - _Requirements: 5.1, 5.3_

- [x] 4.3 룰 서비스 구현
  - PostgreSQL에서 활성 룰 로딩
  - 룰 만료일 및 버전 관리
  - _Requirements: 9.4, 9.5_

- [x] 5. 추천 엔진 구현
- [x] 5.1 배제 엔진 구현
  - eligibility 룰 평가 로직
  - condition_json AND 매칭 구현
  - 즉시 제외 및 로깅 처리
  - _Requirements: 2.1, 2.2, 2.3_

- [x] 5.2 감점 엔진 구현
  - scoring 룰 평가 및 가중치 누적
  - MULTI 별칭 해석 기능
  - 동계열 중복 감점 상한 정책 적용
  - _Requirements: 3.1, 3.2, 3.4_

- [x] 5.3 정렬 엔진 구현
  - 6단계 tie-break 정렬 알고리즘
  - 의도 일치도 계산 로직
  - 정렬 근거 생성
  - _Requirements: 4.1, 4.2, 4.3, 4.5_

- [x] 6. 유틸리티 및 헬퍼 구현
- [x] 6.1 별칭 매퍼 구현
  - MULTI:ANTICOAG, MULTI:HTN, MULTI:PREG_LACT 매핑
  - ATC 코드 배열 해석
  - _Requirements: 3.2, 8.3_

- [x] 6.2 로깅 서비스 구현
  - rule_hit_log 테이블에 룰 적용 이력 기록
  - request_id 기반 추적 시스템
  - _Requirements: 6.1, 6.2, 6.4_

- [x] 7. API 엔드포인트 구현
- [x] 7.1 기존 추천 API 확장
  - 기존 app/routers/recommendations.py를 화장품 추천 로직으로 교체
  - POST /api/v1/recommendations 엔드포인트에 전체 파이프라인 통합
  - _Requirements: 1.1, 1.3, 6.3_

- [x] 7.2 운영 API 구현
  - GET /api/v1/rules/health 엔드포인트
  - 룰셋 버전, 활성 룰 수 등 운영 지표 제공
  - _Requirements: 7.1, 7.2, 7.4_

- [x] 8. 통합 및 테스트
- [x] 8.1 전체 파이프라인 통합 테스트
  - 샘플 요청으로 end-to-end 테스트
  - 각 단계별 데이터 흐름 검증
  - _Requirements: 1.1, 1.5_

- [x] 8.2 에러 처리 및 검증
  - 입력 검증 에러 (400) 처리
  - 비즈니스 로직 에러 (422) 처리
  - 시스템 에러 (500) 처리
  - _Requirements: 1.4_

- [ ]* 8.3 성능 최적화
  - 응답 시간 측정 및 최적화
  - 메모리 사용량 모니터링
  - _Requirements: 7.5_

- [ ]* 8.4 단위 테스트 작성
  - 각 서비스별 단위 테스트
  - 룰 평가 로직 테스트
  - _Requirements: 모든 요구사항_