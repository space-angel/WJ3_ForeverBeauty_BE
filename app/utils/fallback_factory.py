"""
폴백 응답 팩토리
에러 상황에서 일관된 응답 생성
"""
from typing import Optional, Dict, Any
from uuid import UUID
from datetime import datetime
import logging

from app.models.response import (
    RecommendationResponse, ExecutionSummary, PipelineStatistics, 
    RecommendationItem
)
from app.models.request import RecommendationRequest

logger = logging.getLogger(__name__)

class FallbackResponseFactory:
    """폴백 응답 생성 팩토리"""
    
    # 에러 타입별 메시지 (하드코딩 제거)
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
    
    @classmethod
    def create_error_response(
        cls,
        error: Exception,
        request: Optional[RecommendationRequest] = None,
        request_id: Optional[UUID] = None,
        execution_time_seconds: float = 0.0,
        error_type: str = 'system_error',
        language: str = 'ko'
    ) -> RecommendationResponse:
        """
        에러 응답 생성
        
        Args:
            error: 발생한 예외
            request: 원본 요청 (있는 경우)
            request_id: 요청 ID
            execution_time_seconds: 실행 시간
            error_type: 에러 타입
            language: 언어 코드
        """
        
        # 기본값 설정
        if request_id is None:
            from uuid import uuid4
            request_id = uuid4()
        
        # 에러 메시지 가져오기
        error_message = cls._get_error_message(error_type, language)
        
        # 실행 요약 생성
        execution_summary = ExecutionSummary(
            request_id=request_id,
            timestamp=datetime.now(),
            success=False,
            execution_time_seconds=execution_time_seconds,
            ruleset_version="error",  # TODO: 실제 버전으로 교체 필요
            active_rules_count=0
        )
        
        # 파이프라인 통계 (모두 0으로 설정)
        pipeline_stats = PipelineStatistics(
            total_candidates=0,
            excluded_by_rules=0,
            penalized_products=0,
            final_recommendations=0,
            eligibility_rules_applied=0,
            scoring_rules_applied=0,
            query_time_ms=0.0,
            evaluation_time_ms=0.0,
            ranking_time_ms=0.0,
            total_time_ms=execution_time_seconds * 1000
        )
        
        # 입력 요약 생성
        input_summary = cls._create_input_summary(request, error)
        
        # 에러 응답 반환 (추천 제품 없음)
        response = RecommendationResponse(
            execution_summary=execution_summary,
            input_summary=input_summary,
            pipeline_statistics=pipeline_stats,
            recommendations=[]  # 에러 시에는 빈 배열
        )
        
        logger.error(f"폴백 응답 생성: {error_type} - {str(error)}")
        return response
    
    @classmethod
    def create_no_results_response(
        cls,
        request: RecommendationRequest,
        request_id: UUID,
        execution_time_seconds: float,
        reason: str = "조건에 맞는 제품이 없습니다"
    ) -> RecommendationResponse:
        """
        결과 없음 응답 생성 (에러가 아닌 정상적인 빈 결과)
        """
        
        execution_summary = ExecutionSummary(
            request_id=request_id,
            timestamp=datetime.now(),
            success=True,  # 정상 처리이지만 결과가 없음
            execution_time_seconds=execution_time_seconds,
            ruleset_version="v2.1",  # TODO: 동적으로 가져오기
            active_rules_count=0  # TODO: 실제 룰 수로 교체
        )
        
        pipeline_stats = PipelineStatistics(
            total_candidates=0,
            excluded_by_rules=0,
            penalized_products=0,
            final_recommendations=0,
            eligibility_rules_applied=0,
            scoring_rules_applied=0,
            query_time_ms=0.0,
            evaluation_time_ms=0.0,
            ranking_time_ms=0.0,
            total_time_ms=execution_time_seconds * 1000
        )
        
        input_summary = cls._create_input_summary(request)
        
        return RecommendationResponse(
            execution_summary=execution_summary,
            input_summary=input_summary,
            pipeline_statistics=pipeline_stats,
            recommendations=[]
        )
    
    @classmethod
    def _get_error_message(cls, error_type: str, language: str) -> str:
        """에러 메시지 가져오기"""
        messages = cls.ERROR_MESSAGES.get(error_type, cls.ERROR_MESSAGES['system_error'])
        return messages.get(language, messages['ko'])
    
    @classmethod
    def _create_input_summary(
        cls, 
        request: Optional[RecommendationRequest], 
        error: Optional[Exception] = None
    ) -> Dict[str, Any]:
        """입력 요약 생성"""
        
        if request is None:
            return {
                "error": "요청 정보 없음",
                "error_details": str(error) if error else "알 수 없는 오류"
            }
        
        summary = {
            "intent_tags_count": len(request.intent_tags) if request.intent_tags else 0,
            "requested_count": request.top_n,
            "has_user_profile": request.user_profile is not None,
            "medications_count": len(request.medications) if request.medications else 0,
            "has_usage_context": request.usage_context is not None,
            "price_range_specified": request.price_range is not None
        }
        
        if error:
            summary["error"] = str(error)
            summary["error_type"] = type(error).__name__
        
        return summary

class ErrorResponseBuilder:
    """에러 응답 빌더 (체이닝 패턴)"""
    
    def __init__(self):
        self.error: Optional[Exception] = None
        self.request: Optional[RecommendationRequest] = None
        self.request_id: Optional[UUID] = None
        self.execution_time: float = 0.0
        self.error_type: str = 'system_error'
        self.language: str = 'ko'
    
    def with_error(self, error: Exception) -> 'ErrorResponseBuilder':
        self.error = error
        return self
    
    def with_request(self, request: RecommendationRequest) -> 'ErrorResponseBuilder':
        self.request = request
        return self
    
    def with_request_id(self, request_id: UUID) -> 'ErrorResponseBuilder':
        self.request_id = request_id
        return self
    
    def with_execution_time(self, seconds: float) -> 'ErrorResponseBuilder':
        self.execution_time = seconds
        return self
    
    def with_error_type(self, error_type: str) -> 'ErrorResponseBuilder':
        self.error_type = error_type
        return self
    
    def with_language(self, language: str) -> 'ErrorResponseBuilder':
        self.language = language
        return self
    
    def build(self) -> RecommendationResponse:
        """에러 응답 생성"""
        if self.error is None:
            raise ValueError("에러 정보가 필요합니다")
        
        return FallbackResponseFactory.create_error_response(
            error=self.error,
            request=self.request,
            request_id=self.request_id,
            execution_time_seconds=self.execution_time,
            error_type=self.error_type,
            language=self.language
        )

# 편의 함수들
def create_error_response(error: Exception, **kwargs) -> RecommendationResponse:
    """간단한 에러 응답 생성"""
    return FallbackResponseFactory.create_error_response(error, **kwargs)

def create_no_results_response(request: RecommendationRequest, request_id: UUID, execution_time: float) -> RecommendationResponse:
    """결과 없음 응답 생성"""
    return FallbackResponseFactory.create_no_results_response(request, request_id, execution_time)