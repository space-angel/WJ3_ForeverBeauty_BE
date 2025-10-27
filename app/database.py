from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, JSON, Date, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
import os
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 데이터베이스 URL
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL 환경변수가 설정되지 않았습니다.")

# 데이터베이스 엔진 생성
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base 클래스 생성
Base = declarative_base()

# 데이터베이스 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# 기존 테이블 모델 정의 (유지)
class IngredientTagDictionary(Base):
    __tablename__ = "ingredient_tag_dictionary"
    
    id = Column(Integer, primary_key=True, index=True)
    ingredient_name = Column(String(100), nullable=False, unique=True)
    tags = Column(Text, nullable=False)  # JSON 형태로 저장
    category = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Recommendation(Base):
    __tablename__ = "recommendations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String(50), nullable=False)
    item_id = Column(String(100), nullable=False)
    item_title = Column(String(200), nullable=False)
    score = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 새로운 룰 시스템 테이블 모델들

class Rule(Base):
    """룰 테이블 (배제/감점 통합)"""
    __tablename__ = "rules"
    
    rule_id = Column(String(50), primary_key=True)
    rule_type = Column(String(20), nullable=False)  # 'eligibility' or 'scoring'
    rule_group = Column(String(50), nullable=True)
    med_code = Column(String(50), nullable=True)
    med_name_ko = Column(String(100), nullable=True)
    ingredient_tag = Column(String(100), nullable=True)
    match_type = Column(String(20), nullable=True)  # 'tag' or 'regex'
    condition_json = Column(JSONB, nullable=True)
    action = Column(String(20), nullable=True)  # 'exclude' or 'penalize'
    severity = Column(Integer, nullable=True)
    weight = Column(Integer, nullable=True)
    confidence = Column(String(20), nullable=True)  # 'high', 'moderate', 'low'
    rationale_ko = Column(Text, nullable=True)
    citation_source = Column(String(200), nullable=True)
    citation_url = Column(JSONB, nullable=True)
    reviewer = Column(String(100), nullable=True)
    reviewed_at = Column(Date, nullable=True)
    expires_at = Column(Date, nullable=True)
    ruleset_version = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    active = Column(Boolean, default=True)


class MedAliasMap(Base):
    """MULTI 별칭 매핑 테이블"""
    __tablename__ = "med_alias_map"
    
    alias = Column(String(50), primary_key=True)
    atc_codes = Column(ARRAY(String), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RuleHitLog(Base):
    """룰 히트 로그 테이블"""
    __tablename__ = "rule_hit_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    request_id = Column(UUID(as_uuid=True), nullable=False)
    product_id = Column(Integer, nullable=True)
    rule_id = Column(String(50), nullable=False)
    hit_type = Column(String(20), nullable=False)  # 'exclude' or 'penalize'
    weight_applied = Column(Integer, nullable=True)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class RecommendationRequest(Base):
    """요청 로그 테이블"""
    __tablename__ = "recommendation_requests"
    
    request_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    input_data = Column(JSONB, nullable=False)
    execution_time_seconds = Column(Float, nullable=True)
    products_found = Column(Integer, nullable=True)
    products_excluded = Column(Integer, nullable=True)
    products_recommended = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 테이블 생성 함수
def create_tables():
    Base.metadata.create_all(bind=engine)