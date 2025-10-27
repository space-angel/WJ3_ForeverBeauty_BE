# 화장품 추천 API 요구사항 문서

## Introduction

화장품 추천 시스템은 사용자 입력(JSON)을 받아 제품 후보군을 축소하고, 배제(강제 제외) → 감점(점수 감산) → 동점 정렬을 수행하는 안전성 중심의 보수적 추천 API입니다.

## Glossary

- **Recommendation_System**: 화장품 추천을 수행하는 전체 시스템
- **Exclusion_Engine**: 의약품/건강/사용맥락 조건에 따라 제품을 배제하는 엔진
- **Scoring_Engine**: 위험-주의 신호에 따라 제품에 감점을 적용하는 엔진
- **Ranker**: 동점일 때 의도 일치도, 안전여유, 리뷰 등으로 정렬하는 엔진
- **Canonical_Tag**: 성분을 정규화한 표준 태그 (예: 'retinoid', 'aha', 'essential_oil')
- **ATC_Code**: 의약품 분류 코드 (예: 'B01AA03')
- **Rule_Hit**: 배제 또는 감점 룰이 적용된 경우

## Requirements

### Requirement 1

**User Story:** 사용자로서 JSON 입력을 통해 화장품 추천을 받고 싶다

#### Acceptance Criteria

1. WHEN 사용자가 유효한 JSON 요청을 보내면, THE Recommendation_System SHALL 추천 결과를 반환한다
2. THE Recommendation_System SHALL intent_tags, category_like, use_context, med_profile, price 정보를 처리한다
3. THE Recommendation_System SHALL 실행 시간, 통계, 추천 목록을 포함한 응답을 생성한다
4. IF 입력 스키마가 불일치하면, THEN THE Recommendation_System SHALL 400 에러를 반환한다
5. THE Recommendation_System SHALL 최대 top_n 개의 추천 제품을 반환한다

### Requirement 2

**User Story:** 시스템 관리자로서 안전성을 위해 특정 조건의 제품을 배제하고 싶다

#### Acceptance Criteria

1. THE Exclusion_Engine SHALL eligibility_rules.json의 룰을 로드하여 평가한다
2. THE Exclusion_Engine SHALL condition_json의 leave_on, day_use, face, large_area_hint 조건을 AND 방식으로 평가한다
3. WHEN action이 "exclude"이고 조건이 충족되면, THE Exclusion_Engine SHALL 해당 제품을 즉시 제외한다
4. THE Exclusion_Engine SHALL 와파린-살리실레이트, 광과민-AHA 등 고위험 조합을 처리한다
5. THE Exclusion_Engine SHALL 배제 근거를 rationale_ko와 citation_url로 제공한다

### Requirement 3

**User Story:** 시스템 관리자로서 위험 요소가 있는 제품에 감점을 적용하고 싶다

#### Acceptance Criteria

1. THE Scoring_Engine SHALL scoring_rules.json의 23개 감점 룰을 평가한다
2. THE Scoring_Engine SHALL MULTI:ANTICOAG, MULTI:HTN, MULTI:PREG_LACT 별칭을 해석한다
3. THE Scoring_Engine SHALL -5점부터 -35점까지의 가중치를 누적 적용한다
4. THE Scoring_Engine SHALL AHA/BHA/PHA 동계열 중복 시 상한 정책을 적용한다
5. THE Scoring_Engine SHALL severity 레벨(1-4)에 따른 감점 강도를 반영한다

### Requirement 4

**User Story:** 사용자로서 동점인 제품들이 일관된 기준으로 정렬되기를 원한다

#### Acceptance Criteria

1. THE Ranker SHALL 최종 점수 내림차순으로 1차 정렬한다
2. WHEN 점수가 동일하면, THE Ranker SHALL 의도 일치도 내림차순으로 정렬한다
3. WHEN 의도 일치도도 동일하면, THE Ranker SHALL 안전여유 오름차순으로 정렬한다
4. THE Ranker SHALL 리뷰점수, 가격차이, 브랜드등급, 최신성 순으로 추가 정렬한다
5. THE Ranker SHALL 정렬 근거를 reasons 필드에 포함한다

### Requirement 5

**User Story:** 개발자로서 기존 cosmetics.db의 정규화된 성분 태그를 활용하고 싶다

#### Acceptance Criteria

1. THE Recommendation_System SHALL cosmetics.db의 ingredients 테이블에서 canonical tags를 로드한다
2. THE Recommendation_System SHALL product_ingredients 테이블을 통해 제품별 성분 정보를 조회한다
3. THE Recommendation_System SHALL 기존 태그 시스템(drying_alcohol, aha, peptide 등)을 룰 평가에 사용한다
4. THE Recommendation_System SHALL EWG 등급과 알레르기 정보를 안전성 평가에 활용한다
5. THE Recommendation_System SHALL 태그가 없는 성분에 대해 기본 처리 로직을 제공한다

### Requirement 6

**User Story:** 시스템 관리자로서 룰 적용 내역을 추적하고 싶다

#### Acceptance Criteria

1. THE Recommendation_System SHALL 각 요청에 고유한 request_id를 할당한다
2. THE Recommendation_System SHALL 배제 및 감점 룰 히트를 rule_hit_log에 기록한다
3. THE Recommendation_System SHALL rule_id, weight, rationale을 응답에 포함한다
4. THE Recommendation_System SHALL 실행 통계를 pipeline_statistics에 포함한다
5. THE Recommendation_System SHALL 각 제품의 점수 계산 과정을 추적한다

### Requirement 7

**User Story:** 운영자로서 시스템 상태와 룰셋 정보를 모니터링하고 싶다

#### Acceptance Criteria

1. THE Recommendation_System SHALL GET /api/v1/rules/health 엔드포인트를 제공한다
2. THE Recommendation_System SHALL 룰셋 버전과 활성 룰 수를 반환한다
3. THE Recommendation_System SHALL alias 매핑 수와 태그 사전 버전을 제공한다
4. THE Recommendation_System SHALL 시스템 상태 지표를 실시간으로 업데이트한다
5. THE Recommendation_System SHALL 에러율과 응답시간 메트릭을 포함한다

### Requirement 8

**User Story:** 개발자로서 기존 데이터와 새로운 룰 시스템을 통합하고 싶다

#### Acceptance Criteria

1. THE Recommendation_System SHALL cosmetics.db의 기존 테이블을 활용한다
2. THE Recommendation_System SHALL scoring_rules.json과 eligibility_rules.json을 DB에 로드한다
3. THE Recommendation_System SHALL MULTI 별칭 매핑 테이블을 생성한다
4. THE Recommendation_System SHALL rule_hit_log 테이블로 추적 기능을 제공한다
5. THE Recommendation_System SHALL 룰 만료일(expires_at)과 버전 관리를 지원한다

### Requirement 9

**User Story:** 시스템 관리자로서 룰의 신뢰도와 출처를 관리하고 싶다

#### Acceptance Criteria

1. THE Recommendation_System SHALL confidence 레벨(high, moderate, low)을 룰 평가에 반영한다
2. THE Recommendation_System SHALL citation_source와 citation_url을 추적 정보로 제공한다
3. THE Recommendation_System SHALL reviewer와 reviewed_at 정보를 메타데이터로 저장한다
4. THE Recommendation_System SHALL ruleset_version으로 룰 세트 버전을 관리한다
5. THE Recommendation_System SHALL 만료된 룰을 자동으로 비활성화한다