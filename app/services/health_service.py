"""
헬스체크 서비스
시스템 상태 모니터링 및 진단
"""
from datetime import datetime
from typing import Dict, Any
import logging

from app.models.response import HealthResponse, RulesetHealth
from app.services.rule_service import RuleService
# SQLite 의존성 제거됨
from app.database.postgres_db import get_postgres_db

logger = logging.getLogger(__name__)

class HealthService:
    """헬스체크 서비스"""
    
    def __init__(self):
        self.rule_service = RuleService()
        # SQLite 의존성 제거됨
        self.postgres_db = get_postgres_db()
    
    async def check_recommendation_health(self, include_stats: bool = False) -> HealthResponse:
        """추천 시스템 헬스체크"""
        
        try:
            # 룰 시스템 상태 확인
            ruleset_health = await self._check_ruleset_health(include_stats)
            
            # 전체 시스템 상태 결정
            status = "healthy" if self._is_system_healthy(ruleset_health) else "degraded"
            
            return HealthResponse(
                status=status,
                ruleset=ruleset_health,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"헬스체크 실패: {e}")
            return self._build_error_health_response(e)
    
    async def _check_ruleset_health(self, include_stats: bool) -> RulesetHealth:
        """룰셋 상태 확인"""
        
        # 룰 통계 조회
        rule_stats = self.rule_service.get_rule_statistics()
        
        # PostgreSQL 상태 확인
        
        postgres_health = await self.postgres_db.get_health_status()
        postgres_status = postgres_health.get('status', 'disconnected')
        
        # 성능 통계 (옵션)
        avg_response_time = None
        error_rate = None
        
        if include_stats:
            performance_stats = await self._get_performance_stats()
            avg_response_time = performance_stats.get('avg_response_time_ms')
            error_rate = performance_stats.get('error_rate_percent')
        
        return RulesetHealth(
            ruleset_version="v2.1",
            total_rules=rule_stats.get('total_rules', 0),
            active_rules=rule_stats.get('active_rules', 0),
            eligibility_rules=rule_stats.get('eligibility_rules', 0),
            scoring_rules=rule_stats.get('scoring_rules', 0),
            expired_rules=0,  # TODO: 만료된 룰 계산
            total_aliases=120,  # TODO: 실제 별칭 수 계산
            postgres_status=postgres_status,
            avg_response_time_ms=avg_response_time,
            error_rate_percent=error_rate,
            last_updated=datetime.now()
        )
    
    async def _get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 조회"""
        
        # TODO: 실제 성능 메트릭 수집
        # 현재는 모의 데이터
        return {
            'avg_response_time_ms': 245.5,
            'error_rate_percent': 0.2,
            'total_requests': 1000,
            'successful_requests': 998
        }
    
    def _is_system_healthy(self, ruleset_health: RulesetHealth) -> bool:
        """시스템 건강성 판단"""
        
        # 기본 조건들
        conditions = [
            ruleset_health.postgres_status == "healthy",
            ruleset_health.active_rules > 0,
            ruleset_health.total_rules > 0
        ]
        
        # 성능 조건 (통계가 있는 경우)
        if ruleset_health.avg_response_time_ms:
            conditions.append(ruleset_health.avg_response_time_ms < 1000)  # 1초 이하
        
        if ruleset_health.error_rate_percent:
            conditions.append(ruleset_health.error_rate_percent < 5.0)  # 5% 이하
        
        return all(conditions)
    
    def _build_error_health_response(self, error: Exception) -> HealthResponse:
        """에러 헬스 응답 생성"""
        
        error_ruleset = RulesetHealth(
            ruleset_version="unknown",
            total_rules=0,
            active_rules=0,
            eligibility_rules=0,
            scoring_rules=0,
            expired_rules=0,
            total_aliases=0,
            postgres_status="error",
            avg_response_time_ms=None,
            error_rate_percent=None,
            last_updated=datetime.now()
        )
        
        return HealthResponse(
            status="error",
            ruleset=error_ruleset,
            timestamp=datetime.now()
        )
    
    async def check_database_connectivity(self) -> Dict[str, str]:
        """데이터베이스 연결성 확인"""
        
        results = {}
        
        # PostgreSQL 확인 (이미 아래에 있음)
        
        # PostgreSQL 확인
        try:
            postgres_health = await self.postgres_db.get_health_status()
            results['postgres'] = postgres_health.get('status', 'unknown')
        except Exception as e:
            results['postgres'] = f"error: {str(e)}"
        
        return results
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """시스템 메트릭 조회"""
        
        return {
            'database_connectivity': await self.check_database_connectivity(),
            'rule_statistics': self.rule_service.get_rule_statistics(),
            'performance_stats': await self._get_performance_stats(),
            'timestamp': datetime.now().isoformat()
        }