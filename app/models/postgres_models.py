"""
PostgreSQL 데이터베이스 모델 정의
룰 엔진 및 추천 시스템용 테이블
"""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, JSON, Date
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from app.database.postgres_db import Base

class Rule(Base):
    """추천 룰 테이블 (실제 Supabase 스키마에 맞춤)"""
    __tablename__ = "rules"
    
    rule_id = Column(String(50), primary_key=True, index=True, nullable=False)
    rule_type = Column(String(20), nullable=False)  # 'eligibility' | 'scoring'
    rule_group = Column(String(20), nullable=True)
    med_code = Column(String(50), nullable=True)
    med_name_ko = Column(String(100), nullable=True)
    ingredient_tag = Column(String(100), nullable=True)
    match_type = Column(String(20), nullable=True)
    condition_json = Column(JSONB, nullable=True)
    action = Column(String(20), nullable=True)     # 'exclude' | 'penalize'
    severity = Column(Integer, nullable=True)
    weight = Column(Integer, nullable=True)
    confidence = Column(String(20), nullable=True)
    rationale_ko = Column(Text, nullable=True)
    citation_source = Column(String(200), nullable=True)
    citation_url = Column(JSONB, nullable=True)
    reviewer = Column(String(100), nullable=True)
    reviewed_at = Column(Date, nullable=True)
    expires_at = Column(Date, nullable=True)
    ruleset_version = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<Rule(rule_id='{self.rule_id}', type='{self.rule_type}', action='{self.action}')>"

class MedicationAlias(Base):
    """의약품 별칭 매핑 테이블"""
    __tablename__ = "medication_aliases"
    
    id = Column(Integer, primary_key=True, index=True)
    alias_code = Column(String(50), unique=True, index=True, nullable=False)  # MULTI:ANTICOAG
    resolved_codes = Column(JSON, nullable=False)  # ["B01AA03", "B01AB01", ...]
    description = Column(String(200), nullable=True)
    
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class RecommendationLog(Base):
    """추천 요청 로그 테이블"""
    __tablename__ = "recommendation_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(36), unique=True, index=True, nullable=False)
    
    # 요청 정보
    intent_tags = Column(JSON, nullable=False)
    user_profile = Column(JSON, nullable=True)
    medications = Column(JSON, nullable=True)
    
    # 실행 결과
    total_candidates = Column(Integer, nullable=False)
    excluded_count = Column(Integer, default=0)
    penalized_count = Column(Integer, default=0)
    final_count = Column(Integer, nullable=False)
    
    # 성능 메트릭
    execution_time_ms = Column(Float, nullable=False)
    query_time_ms = Column(Float, nullable=True)
    evaluation_time_ms = Column(Float, nullable=True)
    ranking_time_ms = Column(Float, nullable=True)
    
    # 메타데이터
    success = Column(Boolean, default=True)
    error_message = Column(Text, nullable=True)
    ruleset_version = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class RulePerformance(Base):
    """룰 성능 통계 테이블"""
    __tablename__ = "rule_performance"
    
    id = Column(Integer, primary_key=True, index=True)
    rule_id = Column(String(50), index=True, nullable=False)
    
    # 적용 통계
    total_applications = Column(Integer, default=0)
    total_hits = Column(Integer, default=0)
    hit_rate = Column(Float, default=0.0)
    
    # 성능 통계
    avg_evaluation_time_ms = Column(Float, default=0.0)
    last_applied = Column(DateTime(timezone=True), nullable=True)
    
    # 집계 기간
    date = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class SystemMetrics(Base):
    """시스템 성능 메트릭 테이블"""
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    metric_unit = Column(String(20), nullable=True)
    
    # 메타데이터
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    component = Column(String(50), nullable=True)  # 'api', 'engine', 'database'
    environment = Column(String(20), default='production')