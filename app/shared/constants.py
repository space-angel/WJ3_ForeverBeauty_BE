"""
공유 상수 정의
모든 하드코딩된 값들을 중앙 집중 관리
"""
from typing import Dict, Any

# 시스템 버전 정보
SYSTEM_VERSION = "1.0.0"
RULESET_VERSION = "v2.1"

# 성능 임계값 (ms)
class PerformanceThresholds:
    SLOW_FUNCTION_MS = 1000  # 느린 함수 임계값
    WARNING_FUNCTION_MS = 500  # 경고 함수 임계값
    MAX_RESPONSE_TIME_MS = 1000  # 최대 응답 시간
    
# 제품 조회 제한
class ProductLimits:
    DEFAULT_CANDIDATE_LIMIT = 1000  # 기본 후보 제품 수
    FALLBACK_CANDIDATE_LIMIT = 500  # 폴백 후보 제품 수
    MAX_PRICE_KRW = 1000000  # 최대 가격 (100만원)

# 룰 엔진 설정
class RuleEngineConfig:
    TOTAL_RULES = 45
    ACTIVE_RULES = 28
    ELIGIBILITY_RULES = 15
    SCORING_RULES = 13
    INACTIVE_RULES = 17
    SYSTEM_ERROR_WEIGHT = 1000

# 순위 가중치
class RankingWeights:
    FINAL_SCORE = 1000      # 1순위: 최종 점수
    INTENT_MATCH = 100      # 2순위: 의도 일치도
    PENALTY_COUNT = -10     # 3순위: 감점 룰 수 (적을수록 좋음)

# HTTP 상태 코드
class HttpStatus:
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    INTERNAL_SERVER_ERROR = 500

# 시간 변환 상수
class TimeConstants:
    MS_PER_SECOND = 1000
    SECONDS_PER_MS = 0.001

# 에러 메시지
ERROR_MESSAGES = {
    'system_error': {
        'ko': '시스템 오류가 발생했습니다. 잠시 후 다시 시도해주세요.',
        'en': 'A system error occurred. Please try again later.'
    },
    'no_products': {
        'ko': '조건에 맞는 제품을 찾을 수 없습니다.',
        'en': 'No products found matching your criteria.'
    },
    'invalid_request': {
        'ko': '잘못된 요청입니다. 입력값을 확인해주세요.',
        'en': 'Invalid request. Please check your input.'
    },
    'database_error': {
        'ko': '데이터베이스 연결 오류입니다. 잠시 후 다시 시도해주세요.',
        'en': 'Database connection error. Please try again later.'
    }
}

# 성능 통계 기본값
DEFAULT_PERFORMANCE_STATS = {
    'avg_response_time_ms': 245.5,
    'error_rate_percent': 0.2,
    'total_requests': 1000,
    'successful_requests': 998
}