"""
응답 모델 정의
"""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from uuid import UUID

class ErrorDetail(BaseModel):
    """에러 상세 정보"""
    code: str
    message: str
    field: Optional[str] = None
    details: Optional[Dict[str, Any]] = None

class ErrorResponse(BaseModel):
    """에러 응답"""
    error: ErrorDetail
    timestamp: datetime
    path: str

class ExecutionSummary(BaseModel):
    """실행 요약"""
    request_id: UUID
    timestamp: datetime
    success: bool
    execution_time_seconds: float
    ruleset_version: str
    active_rules_count: int

class PipelineStatistics(BaseModel):
    """파이프라인 통계"""
    total_candidates: int
    excluded_by_rules: int
    penalized_products: int
    final_recommendations: int
    eligibility_rules_applied: int
    scoring_rules_applied: int
    query_time_ms: float
    evaluation_time_ms: float
    ranking_time_ms: float
    total_time_ms: float

class RuleHit(BaseModel):
    """룰 히트 정보"""
    type: str  # 'exclude' | 'penalize'
    rule_id: str
    weight: int
    rationale_ko: str
    citation_url: Optional[List[str]] = None

class ProductRecommendation(BaseModel):
    """제품 추천 정보"""
    rank: int
    product_id: int
    product_name: str
    brand_name: str
    category: str
    final_score: int
    base_score: int = 100
    penalty_score: int
    intent_match_score: int
    reasons: List[str]
    rule_hits: List[RuleHit]

class RecommendationItem(BaseModel):
    """추천 아이템"""
    rank: int
    product_id: str
    product_name: str
    brand_name: str
    category: str
    final_score: float
    intent_match_score: float
    reasons: List[str]
    warnings: List[str] = []
    rule_hits: List[RuleHit] = []

class RecommendationResponse(BaseModel):
    """추천 응답"""
    execution_summary: ExecutionSummary
    input_summary: Dict[str, Any]
    pipeline_statistics: PipelineStatistics
    recommendations: List[RecommendationItem]

class RulesetHealth(BaseModel):
    """룰셋 상태"""
    ruleset_version: str
    total_rules: int
    active_rules: int
    eligibility_rules: int
    scoring_rules: int
    expired_rules: int
    total_aliases: int
    sqlite_status: str
    postgres_status: str
    avg_response_time_ms: Optional[float] = None
    error_rate_percent: Optional[float] = None
    last_updated: datetime

class HealthResponse(BaseModel):
    """헬스체크 응답"""
    status: str
    ruleset: RulesetHealth
    timestamp: datetime