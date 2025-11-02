"""
성능 모니터링 API 엔드포인트
성능 메트릭 조회, 캐시 관리, 동시성 통계 제공
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from typing import Dict, Any, Optional, List
import logging

from app.services.advanced_personalization_engine import get_personalization_engine
from app.services.performance_monitor import get_performance_monitor
from app.services.advanced_cache import get_cache_manager
from app.services.concurrency_optimizer import get_concurrency_optimizer
from app.services.performance_integration_test import run_performance_integration_test

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/performance", tags=["Performance Monitoring"])

@router.get("/metrics", response_model=Dict[str, Any])
async def get_performance_metrics(
    time_window_minutes: int = Query(60, ge=1, le=1440, description="시간 윈도우 (분)")
):
    """
    성능 메트릭 조회
    
    Args:
        time_window_minutes: 조회할 시간 윈도우 (분)
    
    Returns:
        Dict: 성능 메트릭 정보
    """
    try:
        engine = get_personalization_engine()
        performance_metrics = await engine.get_performance_metrics()
        
        # 시간 윈도우별 상세 정보
        monitor = get_performance_monitor()
        detailed_summary = monitor.get_performance_summary(time_window_minutes)
        
        return {
            "status": "success",
            "time_window_minutes": time_window_minutes,
            "timestamp": performance_metrics.get("timestamp"),
            "overall_metrics": performance_metrics,
            "detailed_summary": detailed_summary
        }
        
    except Exception as e:
        logger.error(f"성능 메트릭 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"성능 메트릭 조회 실패: {str(e)}")

@router.get("/components", response_model=Dict[str, Any])
async def get_component_stats(
    component: Optional[str] = Query(None, description="특정 컴포넌트 필터")
):
    """
    컴포넌트별 성능 통계 조회
    
    Args:
        component: 조회할 특정 컴포넌트 (선택사항)
    
    Returns:
        Dict: 컴포넌트별 성능 통계
    """
    try:
        monitor = get_performance_monitor()
        component_stats = monitor.get_component_stats(component)
        
        return {
            "status": "success",
            "component_filter": component,
            "component_count": len(component_stats),
            "components": {
                key: {
                    "total_calls": stats.total_calls,
                    "successful_calls": stats.successful_calls,
                    "failed_calls": stats.failed_calls,
                    "avg_execution_time_ms": stats.avg_execution_time_ms,
                    "min_execution_time_ms": stats.min_execution_time_ms,
                    "max_execution_time_ms": stats.max_execution_time_ms,
                    "avg_memory_usage_mb": stats.avg_memory_usage_mb,
                    "error_rate_percent": stats.error_rate_percent
                }
                for key, stats in component_stats.items()
            }
        }
        
    except Exception as e:
        logger.error(f"컴포넌트 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"컴포넌트 통계 조회 실패: {str(e)}")

@router.get("/bottlenecks", response_model=Dict[str, Any])
async def get_bottlenecks(
    limit: int = Query(10, ge=1, le=50, description="반환할 병목 지점 수")
):
    """
    성능 병목 지점 조회
    
    Args:
        limit: 반환할 병목 지점 수
    
    Returns:
        Dict: 병목 지점 정보
    """
    try:
        monitor = get_performance_monitor()
        
        # 가장 느린 작업들
        slowest_ops = monitor.get_slowest_operations(limit)
        
        # 메모리 사용량이 높은 작업들
        memory_intensive_ops = monitor.get_memory_intensive_operations(limit)
        
        # 전체 성능 요약에서 병목 지점 추출
        performance_summary = monitor.get_performance_summary(60)
        bottlenecks = performance_summary.get('bottlenecks', [])
        
        return {
            "status": "success",
            "analysis_period_minutes": 60,
            "bottlenecks": {
                "slowest_operations": slowest_ops,
                "memory_intensive_operations": memory_intensive_ops,
                "identified_bottlenecks": bottlenecks[:limit]
            },
            "recommendations": [
                "가장 느린 작업들을 우선적으로 최적화하세요",
                "메모리 사용량이 높은 작업들의 캐싱을 고려하세요",
                "병목 점수가 높은 컴포넌트들의 알고리즘을 개선하세요"
            ]
        }
        
    except Exception as e:
        logger.error(f"병목 지점 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"병목 지점 조회 실패: {str(e)}")

@router.get("/cache", response_model=Dict[str, Any])
async def get_cache_info():
    """
    캐시 시스템 정보 조회
    
    Returns:
        Dict: 캐시 시스템 상태 및 통계
    """
    try:
        cache_manager = get_cache_manager()
        cache_info = await cache_manager.cache.get_cache_info()
        cache_stats = await cache_manager.cache.get_stats()
        
        return {
            "status": "success",
            "cache_info": cache_info,
            "cache_stats": {
                level.value: {
                    "hit_rate": stats.hit_rate,
                    "miss_rate": stats.miss_rate,
                    "total_requests": stats.total_requests,
                    "hits": stats.hits,
                    "misses": stats.misses,
                    "entry_count": stats.entry_count,
                    "size_mb": stats.size_bytes / 1024 / 1024
                }
                for level, stats in cache_stats.items()
            }
        }
        
    except Exception as e:
        logger.error(f"캐시 정보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"캐시 정보 조회 실패: {str(e)}")

@router.post("/cache/clear", response_model=Dict[str, Any])
async def clear_cache(
    level: Optional[str] = Query(None, description="삭제할 캐시 레벨 (전체 삭제 시 생략)")
):
    """
    캐시 삭제
    
    Args:
        level: 삭제할 특정 캐시 레벨 (선택사항)
    
    Returns:
        Dict: 삭제 결과
    """
    try:
        cache_manager = get_cache_manager()
        
        if level:
            # 특정 레벨만 삭제 (구현 필요)
            cleared_count = 0
            message = f"특정 레벨 캐시 삭제는 아직 구현되지 않음: {level}"
        else:
            # 전체 캐시 삭제
            clear_results = await cache_manager.cache.clear_all()
            cleared_count = sum(clear_results.values())
            message = f"전체 캐시 삭제 완료: {cleared_count}개 엔트리"
        
        logger.info(message)
        
        return {
            "status": "success",
            "message": message,
            "cleared_entries": cleared_count,
            "level": level or "all"
        }
        
    except Exception as e:
        logger.error(f"캐시 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"캐시 삭제 실패: {str(e)}")

@router.get("/concurrency", response_model=Dict[str, Any])
async def get_concurrency_stats():
    """
    동시성 처리 통계 조회
    
    Returns:
        Dict: 동시성 처리 통계
    """
    try:
        concurrency_optimizer = get_concurrency_optimizer()
        stats = await concurrency_optimizer.get_optimization_stats()
        
        return {
            "status": "success",
            "concurrency_stats": stats
        }
        
    except Exception as e:
        logger.error(f"동시성 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"동시성 통계 조회 실패: {str(e)}")

@router.post("/optimize", response_model=Dict[str, Any])
async def optimize_for_load(
    expected_concurrent_users: int = Query(..., ge=1, le=1000, description="예상 동시 사용자 수")
):
    """
    부하에 따른 동적 최적화
    
    Args:
        expected_concurrent_users: 예상 동시 사용자 수
    
    Returns:
        Dict: 최적화 결과
    """
    try:
        engine = get_personalization_engine()
        await engine.optimize_for_load(expected_concurrent_users)
        
        return {
            "status": "success",
            "message": f"{expected_concurrent_users}명 동시 사용자에 대한 최적화 완료",
            "expected_concurrent_users": expected_concurrent_users,
            "optimization_applied": True
        }
        
    except Exception as e:
        logger.error(f"부하 최적화 실패: {e}")
        raise HTTPException(status_code=500, detail=f"부하 최적화 실패: {str(e)}")

@router.get("/health", response_model=Dict[str, Any])
async def get_system_health():
    """
    시스템 헬스체크 (성능 관점)
    
    Returns:
        Dict: 시스템 건강 상태
    """
    try:
        engine = get_personalization_engine()
        health_status = await engine.get_engine_health()
        
        # 성능 기준 건강 상태 추가
        monitor = get_performance_monitor()
        recent_summary = monitor.get_performance_summary(10)  # 최근 10분
        
        # 건강 상태 판단
        performance_health = "healthy"
        warnings = []
        
        summary = recent_summary.get('summary', {})
        avg_execution_time = summary.get('avg_execution_time_ms', 0)
        success_rate = summary.get('success_rate_percent', 100)
        
        if avg_execution_time > 2000:  # 2초 초과
            performance_health = "degraded"
            warnings.append(f"평균 응답시간이 높음: {avg_execution_time:.1f}ms")
        
        if success_rate < 95:  # 성공률 95% 미만
            performance_health = "degraded"
            warnings.append(f"성공률이 낮음: {success_rate:.1f}%")
        
        health_status["performance_health"] = performance_health
        health_status["performance_warnings"] = warnings
        health_status["recent_performance"] = summary
        
        return {
            "status": "success",
            "health_status": health_status
        }
        
    except Exception as e:
        logger.error(f"시스템 헬스체크 실패: {e}")
        raise HTTPException(status_code=500, detail=f"시스템 헬스체크 실패: {str(e)}")

@router.post("/test/integration", response_model=Dict[str, Any])
async def run_integration_test(background_tasks: BackgroundTasks):
    """
    성능 통합 테스트 실행 (백그라운드)
    
    Returns:
        Dict: 테스트 시작 확인
    """
    try:
        # 백그라운드에서 테스트 실행
        background_tasks.add_task(run_performance_integration_test)
        
        return {
            "status": "success",
            "message": "성능 통합 테스트가 백그라운드에서 시작되었습니다",
            "test_started": True,
            "note": "테스트 결과는 로그에서 확인하세요"
        }
        
    except Exception as e:
        logger.error(f"통합 테스트 시작 실패: {e}")
        raise HTTPException(status_code=500, detail=f"통합 테스트 시작 실패: {str(e)}")

@router.get("/alerts", response_model=Dict[str, Any])
async def get_performance_alerts(
    time_window_minutes: int = Query(60, ge=1, le=1440, description="조회할 시간 윈도우 (분)")
):
    """
    성능 알림 조회
    
    Args:
        time_window_minutes: 조회할 시간 윈도우 (분)
    
    Returns:
        Dict: 성능 알림 정보
    """
    try:
        monitor = get_performance_monitor()
        performance_summary = monitor.get_performance_summary(time_window_minutes)
        
        alerts = performance_summary.get('alerts', [])
        
        # 알림 분류
        critical_alerts = []
        warning_alerts = []
        info_alerts = []
        
        for alert in alerts:
            if "초과" in alert or "실패" in alert:
                critical_alerts.append(alert)
            elif "높음" in alert or "지연" in alert:
                warning_alerts.append(alert)
            else:
                info_alerts.append(alert)
        
        return {
            "status": "success",
            "time_window_minutes": time_window_minutes,
            "total_alerts": len(alerts),
            "alerts": {
                "critical": critical_alerts,
                "warning": warning_alerts,
                "info": info_alerts
            },
            "alert_summary": {
                "critical_count": len(critical_alerts),
                "warning_count": len(warning_alerts),
                "info_count": len(info_alerts)
            }
        }
        
    except Exception as e:
        logger.error(f"성능 알림 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"성능 알림 조회 실패: {str(e)}")

@router.post("/monitoring/enable", response_model=Dict[str, Any])
async def enable_monitoring():
    """성능 모니터링 활성화"""
    try:
        monitor = get_performance_monitor()
        monitor.enable_monitoring()
        
        return {
            "status": "success",
            "message": "성능 모니터링이 활성화되었습니다",
            "monitoring_enabled": True
        }
        
    except Exception as e:
        logger.error(f"모니터링 활성화 실패: {e}")
        raise HTTPException(status_code=500, detail=f"모니터링 활성화 실패: {str(e)}")

@router.post("/monitoring/disable", response_model=Dict[str, Any])
async def disable_monitoring():
    """성능 모니터링 비활성화"""
    try:
        monitor = get_performance_monitor()
        monitor.disable_monitoring()
        
        return {
            "status": "success",
            "message": "성능 모니터링이 비활성화되었습니다",
            "monitoring_enabled": False
        }
        
    except Exception as e:
        logger.error(f"모니터링 비활성화 실패: {e}")
        raise HTTPException(status_code=500, detail=f"모니터링 비활성화 실패: {str(e)}")