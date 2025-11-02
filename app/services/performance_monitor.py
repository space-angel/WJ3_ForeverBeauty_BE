"""
성능 모니터링 시스템
각 컴포넌트별 실행 시간 측정, 메모리 사용량 모니터링, 병목 지점 식별
"""

import time
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False
import asyncio
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from functools import wraps
import traceback

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """성능 메트릭 데이터"""
    component: str
    operation: str
    execution_time_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    timestamp: datetime
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ComponentStats:
    """컴포넌트별 통계"""
    component: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_execution_time_ms: float = 0.0
    avg_execution_time_ms: float = 0.0
    min_execution_time_ms: float = float('inf')
    max_execution_time_ms: float = 0.0
    avg_memory_usage_mb: float = 0.0
    avg_cpu_usage_percent: float = 0.0
    error_rate_percent: float = 0.0
    
    def update(self, metric: PerformanceMetric):
        """메트릭으로 통계 업데이트"""
        self.total_calls += 1
        
        if metric.success:
            self.successful_calls += 1
        else:
            self.failed_calls += 1
        
        self.total_execution_time_ms += metric.execution_time_ms
        self.avg_execution_time_ms = self.total_execution_time_ms / self.total_calls
        
        self.min_execution_time_ms = min(self.min_execution_time_ms, metric.execution_time_ms)
        self.max_execution_time_ms = max(self.max_execution_time_ms, metric.execution_time_ms)
        
        # 이동 평균으로 메모리/CPU 사용량 계산
        alpha = 0.1  # 가중치
        self.avg_memory_usage_mb = (1 - alpha) * self.avg_memory_usage_mb + alpha * metric.memory_usage_mb
        self.avg_cpu_usage_percent = (1 - alpha) * self.avg_cpu_usage_percent + alpha * metric.cpu_usage_percent
        
        self.error_rate_percent = (self.failed_calls / self.total_calls) * 100

@dataclass
class SystemMetrics:
    """시스템 전체 메트릭"""
    timestamp: datetime
    cpu_usage_percent: float
    memory_usage_mb: float
    memory_usage_percent: float
    disk_usage_percent: float
    active_threads: int
    active_connections: int = 0

class PerformanceMonitor:
    """성능 모니터링 시스템"""
    
    def __init__(self, max_metrics_history: int = 10000):
        """
        성능 모니터 초기화
        
        Args:
            max_metrics_history: 보관할 최대 메트릭 수
        """
        self.max_metrics_history = max_metrics_history
        self.metrics_history: deque[PerformanceMetric] = deque(maxlen=max_metrics_history)
        self.component_stats: Dict[str, ComponentStats] = defaultdict(lambda: ComponentStats(""))
        self.system_metrics_history: deque[SystemMetrics] = deque(maxlen=1000)
        
        self._lock = threading.RLock()
        self._monitoring_enabled = True
        self._alert_thresholds = {
            'execution_time_ms': 1000,  # 1초
            'memory_usage_mb': 500,     # 500MB
            'cpu_usage_percent': 80,    # 80%
            'error_rate_percent': 10    # 10%
        }
        
        # 백그라운드 시스템 메트릭 수집 시작
        self._start_system_monitoring()
        
        logger.info(f"PerformanceMonitor 초기화 완료: max_history={max_metrics_history}")
    
    def record_metric(self, metric: PerformanceMetric):
        """성능 메트릭 기록"""
        if not self._monitoring_enabled:
            return
        
        with self._lock:
            # 메트릭 히스토리에 추가
            self.metrics_history.append(metric)
            
            # 컴포넌트별 통계 업데이트
            component_key = f"{metric.component}.{metric.operation}"
            if component_key not in self.component_stats:
                self.component_stats[component_key] = ComponentStats(component_key)
            
            self.component_stats[component_key].update(metric)
            
            # 임계값 초과 알림
            self._check_thresholds(metric)
            
            # 성능 메트릭 기록 (디버그 로깅 제거)
    
    @asynccontextmanager
    async def measure_async(
        self, 
        component: str, 
        operation: str, 
        metadata: Optional[Dict[str, Any]] = None
    ):
        """비동기 함수 성능 측정 컨텍스트 매니저"""
        start_time = time.time()
        start_memory = self._get_memory_usage()
        start_cpu = self._get_cpu_usage()
        
        success = True
        error_message = None
        
        try:
            yield
        except Exception as e:
            success = False
            error_message = str(e)
            raise
        finally:
            end_time = time.time()
            execution_time_ms = (end_time - start_time) * 1000
            
            end_memory = self._get_memory_usage()
            end_cpu = self._get_cpu_usage()
            
            metric = PerformanceMetric(
                component=component,
                operation=operation,
                execution_time_ms=execution_time_ms,
                memory_usage_mb=end_memory,
                cpu_usage_percent=end_cpu,
                timestamp=datetime.now(),
                success=success,
                error_message=error_message,
                metadata=metadata or {}
            )
            
            self.record_metric(metric)
    
    def measure_sync(
        self, 
        component: str, 
        operation: str, 
        metadata: Optional[Dict[str, Any]] = None
    ):
        """동기 함수 성능 측정 데코레이터"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                start_memory = self._get_memory_usage()
                start_cpu = self._get_cpu_usage()
                
                success = True
                error_message = None
                result = None
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error_message = str(e)
                    raise
                finally:
                    end_time = time.time()
                    execution_time_ms = (end_time - start_time) * 1000
                    
                    end_memory = self._get_memory_usage()
                    end_cpu = self._get_cpu_usage()
                    
                    metric = PerformanceMetric(
                        component=component,
                        operation=operation,
                        execution_time_ms=execution_time_ms,
                        memory_usage_mb=end_memory,
                        cpu_usage_percent=end_cpu,
                        timestamp=datetime.now(),
                        success=success,
                        error_message=error_message,
                        metadata=metadata or {}
                    )
                    
                    self.record_metric(metric)
            
            return wrapper
        return decorator
    
    def get_component_stats(self, component: Optional[str] = None) -> Dict[str, ComponentStats]:
        """컴포넌트별 통계 조회"""
        with self._lock:
            if component:
                # 특정 컴포넌트의 모든 오퍼레이션
                filtered_stats = {
                    key: stats for key, stats in self.component_stats.items()
                    if key.startswith(component)
                }
                return filtered_stats
            else:
                # 모든 컴포넌트 통계
                return dict(self.component_stats)
    
    def get_performance_summary(self, time_window_minutes: int = 60) -> Dict[str, Any]:
        """성능 요약 정보 조회"""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(minutes=time_window_minutes)
            
            # 시간 윈도우 내 메트릭 필터링
            recent_metrics = [
                metric for metric in self.metrics_history
                if metric.timestamp >= cutoff_time
            ]
            
            if not recent_metrics:
                return {"message": "최근 메트릭 데이터가 없습니다."}
            
            # 전체 통계
            total_calls = len(recent_metrics)
            successful_calls = sum(1 for m in recent_metrics if m.success)
            failed_calls = total_calls - successful_calls
            
            execution_times = [m.execution_time_ms for m in recent_metrics]
            memory_usages = [m.memory_usage_mb for m in recent_metrics]
            cpu_usages = [m.cpu_usage_percent for m in recent_metrics]
            
            # 컴포넌트별 통계
            component_breakdown = defaultdict(list)
            for metric in recent_metrics:
                component_breakdown[metric.component].append(metric)
            
            component_summary = {}
            for component, metrics in component_breakdown.items():
                component_summary[component] = {
                    'calls': len(metrics),
                    'success_rate': (sum(1 for m in metrics if m.success) / len(metrics)) * 100,
                    'avg_execution_time_ms': sum(m.execution_time_ms for m in metrics) / len(metrics),
                    'max_execution_time_ms': max(m.execution_time_ms for m in metrics),
                    'avg_memory_usage_mb': sum(m.memory_usage_mb for m in metrics) / len(metrics)
                }
            
            # 병목 지점 식별
            bottlenecks = self._identify_bottlenecks(recent_metrics)
            
            # 최근 시스템 메트릭
            recent_system_metrics = [
                sm for sm in self.system_metrics_history
                if sm.timestamp >= cutoff_time
            ]
            
            system_summary = {}
            if recent_system_metrics:
                system_summary = {
                    'avg_cpu_usage': sum(sm.cpu_usage_percent for sm in recent_system_metrics) / len(recent_system_metrics),
                    'avg_memory_usage_mb': sum(sm.memory_usage_mb for sm in recent_system_metrics) / len(recent_system_metrics),
                    'avg_memory_usage_percent': sum(sm.memory_usage_percent for sm in recent_system_metrics) / len(recent_system_metrics),
                    'max_active_threads': max(sm.active_threads for sm in recent_system_metrics)
                }
            
            return {
                'time_window_minutes': time_window_minutes,
                'summary': {
                    'total_calls': total_calls,
                    'successful_calls': successful_calls,
                    'failed_calls': failed_calls,
                    'success_rate_percent': (successful_calls / total_calls) * 100 if total_calls > 0 else 0,
                    'avg_execution_time_ms': sum(execution_times) / len(execution_times) if execution_times else 0,
                    'max_execution_time_ms': max(execution_times) if execution_times else 0,
                    'avg_memory_usage_mb': sum(memory_usages) / len(memory_usages) if memory_usages else 0,
                    'avg_cpu_usage_percent': sum(cpu_usages) / len(cpu_usages) if cpu_usages else 0
                },
                'component_breakdown': component_summary,
                'bottlenecks': bottlenecks,
                'system_metrics': system_summary,
                'alerts': self._get_recent_alerts(cutoff_time)
            }
    
    def get_slowest_operations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """가장 느린 오퍼레이션 목록"""
        with self._lock:
            # 최근 1시간 메트릭
            cutoff_time = datetime.now() - timedelta(hours=1)
            recent_metrics = [
                metric for metric in self.metrics_history
                if metric.timestamp >= cutoff_time
            ]
            
            # 실행 시간 기준 정렬
            sorted_metrics = sorted(
                recent_metrics,
                key=lambda x: x.execution_time_ms,
                reverse=True
            )
            
            return [
                {
                    'component': metric.component,
                    'operation': metric.operation,
                    'execution_time_ms': metric.execution_time_ms,
                    'memory_usage_mb': metric.memory_usage_mb,
                    'timestamp': metric.timestamp.isoformat(),
                    'success': metric.success,
                    'metadata': metric.metadata
                }
                for metric in sorted_metrics[:limit]
            ]
    
    def get_memory_intensive_operations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """메모리 사용량이 높은 오퍼레이션 목록"""
        with self._lock:
            cutoff_time = datetime.now() - timedelta(hours=1)
            recent_metrics = [
                metric for metric in self.metrics_history
                if metric.timestamp >= cutoff_time
            ]
            
            sorted_metrics = sorted(
                recent_metrics,
                key=lambda x: x.memory_usage_mb,
                reverse=True
            )
            
            return [
                {
                    'component': metric.component,
                    'operation': metric.operation,
                    'memory_usage_mb': metric.memory_usage_mb,
                    'execution_time_ms': metric.execution_time_ms,
                    'timestamp': metric.timestamp.isoformat(),
                    'metadata': metric.metadata
                }
                for metric in sorted_metrics[:limit]
            ]
    
    def _identify_bottlenecks(self, metrics: List[PerformanceMetric]) -> List[Dict[str, Any]]:
        """병목 지점 식별"""
        if not metrics:
            return []
        
        # 컴포넌트별 평균 실행 시간 계산
        component_times = defaultdict(list)
        for metric in metrics:
            component_times[f"{metric.component}.{metric.operation}"].append(metric.execution_time_ms)
        
        # 평균 실행 시간이 긴 순으로 정렬
        avg_times = []
        for component, times in component_times.items():
            avg_time = sum(times) / len(times)
            max_time = max(times)
            call_count = len(times)
            
            # 병목 점수 계산 (평균 시간 * 호출 빈도)
            bottleneck_score = avg_time * call_count
            
            avg_times.append({
                'component': component,
                'avg_execution_time_ms': avg_time,
                'max_execution_time_ms': max_time,
                'call_count': call_count,
                'bottleneck_score': bottleneck_score
            })
        
        # 병목 점수 기준 정렬
        sorted_bottlenecks = sorted(avg_times, key=lambda x: x['bottleneck_score'], reverse=True)
        
        return sorted_bottlenecks[:5]  # 상위 5개 병목 지점
    
    def _check_thresholds(self, metric: PerformanceMetric):
        """임계값 초과 확인 및 알림"""
        alerts = []
        
        if metric.execution_time_ms > self._alert_thresholds['execution_time_ms']:
            alerts.append(f"실행 시간 초과: {metric.component}.{metric.operation} - {metric.execution_time_ms:.1f}ms")
        
        if metric.memory_usage_mb > self._alert_thresholds['memory_usage_mb']:
            alerts.append(f"메모리 사용량 초과: {metric.component}.{metric.operation} - {metric.memory_usage_mb:.1f}MB")
        
        if metric.cpu_usage_percent > self._alert_thresholds['cpu_usage_percent']:
            alerts.append(f"CPU 사용률 초과: {metric.component}.{metric.operation} - {metric.cpu_usage_percent:.1f}%")
        
        # 컴포넌트 에러율 확인
        component_key = f"{metric.component}.{metric.operation}"
        if component_key in self.component_stats:
            error_rate = self.component_stats[component_key].error_rate_percent
            if error_rate > self._alert_thresholds['error_rate_percent']:
                alerts.append(f"에러율 초과: {component_key} - {error_rate:.1f}%")
        
        # 심각한 성능 문제만 로깅 (임계값의 2배 초과 시)
        critical_alerts = []
        for alert in alerts:
            if "실행 시간 초과" in alert and metric.execution_time_ms > self._alert_thresholds['execution_time_ms'] * 2:
                critical_alerts.append(alert)
            elif "에러율 초과" in alert:
                critical_alerts.append(alert)
        
        for alert in critical_alerts:
            logger.error(f"심각한 성능 문제: {alert}")
    
    def _get_recent_alerts(self, cutoff_time: datetime) -> List[str]:
        """최근 알림 목록 (실제 구현에서는 별도 저장소 사용)"""
        # 임시 구현: 최근 메트릭에서 임계값 초과 항목 찾기
        alerts = []
        recent_metrics = [
            metric for metric in self.metrics_history
            if metric.timestamp >= cutoff_time
        ]
        
        for metric in recent_metrics:
            if metric.execution_time_ms > self._alert_thresholds['execution_time_ms']:
                alerts.append(f"실행 시간 초과: {metric.component}.{metric.operation}")
        
        return list(set(alerts))  # 중복 제거
    
    def _get_memory_usage(self) -> float:
        """현재 메모리 사용량 (MB)"""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024  # bytes to MB
        except:
            return 0.0
    
    def _get_cpu_usage(self) -> float:
        """현재 CPU 사용률 (%)"""
        try:
            return psutil.cpu_percent(interval=None)
        except:
            return 0.0
    
    def _start_system_monitoring(self):
        """백그라운드 시스템 메트릭 수집 시작"""
        def collect_system_metrics():
            while self._monitoring_enabled:
                try:
                    cpu_usage = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage('/')
                    
                    system_metric = SystemMetrics(
                        timestamp=datetime.now(),
                        cpu_usage_percent=cpu_usage,
                        memory_usage_mb=memory.used / 1024 / 1024,
                        memory_usage_percent=memory.percent,
                        disk_usage_percent=disk.percent,
                        active_threads=threading.active_count()
                    )
                    
                    with self._lock:
                        self.system_metrics_history.append(system_metric)
                    
                except Exception as e:
                    logger.error(f"시스템 메트릭 수집 오류: {e}")
                
                time.sleep(30)  # 30초마다 수집
        
        # 백그라운드 스레드로 실행
        monitor_thread = threading.Thread(target=collect_system_metrics, daemon=True)
        monitor_thread.start()
        logger.info("시스템 메트릭 수집 시작")
    
    def set_alert_thresholds(self, thresholds: Dict[str, float]):
        """알림 임계값 설정"""
        self._alert_thresholds.update(thresholds)
        logger.info(f"알림 임계값 업데이트: {thresholds}")
    
    def enable_monitoring(self):
        """모니터링 활성화"""
        self._monitoring_enabled = True
        logger.info("성능 모니터링 활성화")
    
    def disable_monitoring(self):
        """모니터링 비활성화"""
        self._monitoring_enabled = False
        logger.info("성능 모니터링 비활성화")
    
    def clear_metrics(self):
        """모든 메트릭 데이터 삭제"""
        with self._lock:
            self.metrics_history.clear()
            self.component_stats.clear()
            self.system_metrics_history.clear()
        logger.info("성능 메트릭 데이터 삭제 완료")
    
    def export_metrics(self, format: str = 'json') -> Dict[str, Any]:
        """메트릭 데이터 내보내기"""
        with self._lock:
            if format == 'json':
                return {
                    'metrics_history': [
                        {
                            'component': m.component,
                            'operation': m.operation,
                            'execution_time_ms': m.execution_time_ms,
                            'memory_usage_mb': m.memory_usage_mb,
                            'cpu_usage_percent': m.cpu_usage_percent,
                            'timestamp': m.timestamp.isoformat(),
                            'success': m.success,
                            'error_message': m.error_message,
                            'metadata': m.metadata
                        }
                        for m in self.metrics_history
                    ],
                    'component_stats': {
                        key: {
                            'component': stats.component,
                            'total_calls': stats.total_calls,
                            'successful_calls': stats.successful_calls,
                            'failed_calls': stats.failed_calls,
                            'avg_execution_time_ms': stats.avg_execution_time_ms,
                            'min_execution_time_ms': stats.min_execution_time_ms,
                            'max_execution_time_ms': stats.max_execution_time_ms,
                            'avg_memory_usage_mb': stats.avg_memory_usage_mb,
                            'error_rate_percent': stats.error_rate_percent
                        }
                        for key, stats in self.component_stats.items()
                    }
                }
            else:
                raise ValueError(f"지원하지 않는 형식: {format}")

# 전역 성능 모니터 인스턴스
_performance_monitor: Optional[PerformanceMonitor] = None

def get_performance_monitor() -> PerformanceMonitor:
    """성능 모니터 인스턴스 반환 (싱글톤)"""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
        logger.info("PerformanceMonitor 인스턴스 생성")
    return _performance_monitor

def cleanup_performance_monitor():
    """성능 모니터 정리"""
    global _performance_monitor
    if _performance_monitor:
        _performance_monitor.disable_monitoring()
        _performance_monitor = None
        logger.info("PerformanceMonitor 정리 완료")