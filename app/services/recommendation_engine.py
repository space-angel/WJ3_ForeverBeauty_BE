"""
통합 추천 엔진
모든 추천 로직을 통합 관리하는 메인 엔진
"""
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from uuid import UUID, uuid4
from datetime import datetime
import logging

from app.models.request import RecommendationRequest
from app.models.response import RecommendationResponse, ExecutionSummary, PipelineStatistics, RecommendationItem
from app.models.postgres_models import Product
from app.services.product_service import ProductService
from app.services.intent_matching_service import AdvancedIntentMatcher
from app.services.eligibility_engine import EligibilityEngine
from app.services.scoring_engine import ScoreCalculator
from app.services.ranking_service import RankingService

logger = logging.getLogger(__name__)

@dataclass
class RecommendationPipeline:
    """추천 파이프라인 결과"""
    candidates: List[Product]
    safe_products: List[Product]
    scored_products: Dict
    ranked_products: List
    execution_time: float
    statistics: Dict

class RecommendationEngine:
    """통합 추천 엔진"""
    
    def __init__(self):
        """서비스 초기화"""
        self.product_service = ProductService()
        self.intent_matcher = AdvancedIntentMatcher()
        self.eligibility_engine = EligibilityEngine()
        self.scoring_engine = ScoreCalculator()
        self.ranking_service = RankingService()
        
        # RecommendationEngine 초기화 완료
    
    async def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        """메인 추천 실행"""
        start_time = datetime.now()
        request_id = uuid4()
        
        try:
            # 추천 요청 시작
            
            # 1. 파이프라인 실행
            pipeline_result = await self._execute_pipeline(request, request_id)
            
            # 2. 응답 생성
            response = self._build_response(
                request, request_id, pipeline_result, start_time
            )
            
            # 추천 완료
            return response
            
        except Exception as e:
            logger.error(f"추천 실행 실패: {request_id} - {e}")
            return self._build_error_response(request, request_id, start_time, e)
    
    async def _execute_pipeline(
        self, 
        request: RecommendationRequest, 
        request_id: UUID
    ) -> RecommendationPipeline:
        """추천 파이프라인 실행"""
        
        # 0단계: 요청 전처리 (medications -> med_profile 변환)
        self._preprocess_request(request)
        
        # 1단계: 후보 제품 조회
        candidates = await self.product_service.get_candidate_products(
            request, limit=1000
        )
        
        if not candidates:
            # 카테고리 필터 없이 재시도
            logger.warning("카테고리 필터링된 후보 제품 없음 - 전체 제품에서 재시도")
            request_copy = request.model_copy() if hasattr(request, 'model_copy') else request
            if hasattr(request_copy, 'categories'):
                request_copy.categories = None
            
            candidates = await self.product_service.get_candidate_products(
                request_copy, limit=500
            )
            
            if not candidates:
                raise ValueError("후보 제품이 없습니다 - 데이터베이스 연결 또는 데이터 문제")
        
        # 2단계: 안전성 평가 (배제)
        eligibility_result = self.eligibility_engine.evaluate_products(
            candidates, request, request_id
        )
        
        safe_products = [
            p for p in candidates 
            if p.product_id not in eligibility_result.excluded_products
        ]
        
        # 3단계: 적합성 평가 (감점)
        scoring_results = self.scoring_engine.evaluate_products(
            safe_products, request, request_id
        )
        
        # 4단계: 순위 결정
        ranked_products = self.ranking_service.rank_products(
            safe_products, scoring_results, request, 
            eligibility_result.excluded_products
        )
        
        # 통계 수집
        execution_time = (datetime.now().timestamp() - datetime.now().timestamp()) * 1000
        statistics = {
            'total_candidates': len(candidates),
            'excluded_count': eligibility_result.total_excluded,
            'safe_count': len(safe_products),
            'final_count': len(ranked_products),
            'execution_time_ms': execution_time,
            'eligibility_rules_applied': getattr(eligibility_result, 'rules_applied', 0)
        }
        
        return RecommendationPipeline(
            candidates=candidates,
            safe_products=safe_products,
            scored_products=scoring_results,
            ranked_products=ranked_products,
            execution_time=execution_time,
            statistics=statistics
        )
    
    def _build_response(
        self,
        request: RecommendationRequest,
        request_id: UUID,
        pipeline: RecommendationPipeline,
        start_time: datetime
    ) -> RecommendationResponse:
        """응답 객체 생성"""
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # 실행 요약
        execution_summary = ExecutionSummary(
            request_id=request_id,
            timestamp=datetime.now(),
            success=True,
            execution_time_seconds=execution_time,
            ruleset_version="v2.1",
            active_rules_count=28
        )
        
        # 감점 통계 계산
        penalized_count = len(pipeline.scored_products) if pipeline.scored_products else 0
        total_scoring_rules = sum(len(result['rule_hits']) for result in pipeline.scored_products.values()) if pipeline.scored_products else 0
        
        # 파이프라인 통계
        pipeline_stats = PipelineStatistics(
            total_candidates=pipeline.statistics['total_candidates'],
            excluded_by_rules=pipeline.statistics['excluded_count'],
            penalized_products=penalized_count,
            final_recommendations=len(pipeline.ranked_products),
            eligibility_rules_applied=pipeline.statistics.get('eligibility_rules_applied', 0),
            scoring_rules_applied=total_scoring_rules,
            query_time_ms=50.0,
            evaluation_time_ms=pipeline.execution_time * 0.6,
            ranking_time_ms=pipeline.execution_time * 0.4,
            total_time_ms=pipeline.execution_time
        )
        
        # 추천 아이템 변환
        recommendations = []
        for ranked_product in pipeline.ranked_products[:request.top_n]:
            recommendation = RecommendationItem(
                rank=ranked_product.rank,
                product_id=str(ranked_product.product.product_id),
                product_name=ranked_product.product.name,
                brand_name=ranked_product.product.brand_name,
                category=ranked_product.product.category_name,
                final_score=round(ranked_product.final_score, 1),
                intent_match_score=round(ranked_product.intent_match_score, 1),
                reasons=ranked_product.reasons,
                warnings=[],  # TODO: 경고 메시지
                rule_hits=ranked_product.rule_hits
            )
            recommendations.append(recommendation)
        
        # 입력 요약
        input_summary = {
            "intent_tags_count": len(request.intent_tags),
            "requested_count": request.top_n,
            "has_user_profile": request.user_profile is not None,
            "medications_count": len(request.medications) if request.medications else 0,
            "has_usage_context": request.usage_context is not None,
            "price_range_specified": request.price_range is not None
        }
        
        return RecommendationResponse(
            execution_summary=execution_summary,
            input_summary=input_summary,
            pipeline_statistics=pipeline_stats,
            recommendations=recommendations
        )
    
    def _preprocess_request(self, request: RecommendationRequest):
        """요청 전처리 - medications를 med_profile로 변환"""
        if request.medications and not request.med_profile:
            from app.models.request import MedProfile
            
            # medications에서 active_ingredients 추출
            med_codes = []
            for medication in request.medications:
                if medication.active_ingredients:
                    med_codes.extend(medication.active_ingredients)
            
            # med_profile 생성
            request.med_profile = MedProfile(codes=med_codes)
            
            # 의약품 코드 변환 완료
    
    def _build_error_response(
        self,
        request: RecommendationRequest,
        request_id: UUID,
        start_time: datetime,
        error: Exception
    ) -> RecommendationResponse:
        """에러 응답 생성"""
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        execution_summary = ExecutionSummary(
            request_id=request_id,
            timestamp=datetime.now(),
            success=False,
            execution_time_seconds=execution_time,
            ruleset_version="v2.1",
            active_rules_count=0
        )
        
        pipeline_stats = PipelineStatistics(
            total_candidates=0,
            excluded_by_rules=0,
            penalized_products=0,
            final_recommendations=0,
            eligibility_rules_applied=0,
            scoring_rules_applied=0,
            query_time_ms=0,
            evaluation_time_ms=0,
            ranking_time_ms=0,
            total_time_ms=execution_time * 1000
        )
        
        return RecommendationResponse(
            execution_summary=execution_summary,
            input_summary={"error": str(error)},
            pipeline_statistics=pipeline_stats,
            recommendations=[]
        )