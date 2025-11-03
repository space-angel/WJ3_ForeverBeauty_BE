"""
시간 측정 유틸리티
정확한 실행 시간 측정 및 성능 모니터링
"""
import time
from typing import Dict, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class TimeMetrics:
    """시간 측정 결과"""
    start_time: datetime
    end_time: Optional[datetime] = None
    total_seconds: float = 0.0
    total_ms: float = 0.0
    step_times: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, float]:
        """딕셔너리로 변환"""
        return {
            'total_seconds': self.total_seconds,
            'total_ms': self.total_ms,
            **{f"{step}_ms": ms for step, ms in self.step_times.items()}
        }

class TimeTracker:
    """
    시간 측정기
    
    Usage:
        tracker = TimeTracker()
        tracker.start()
        
        tracker.step('query')
        # ... 쿼리 실행
        tracker.step('processing')
        # ... 처리 로직
        
        metrics = tracker.finish()
    """
    
    def __init__(self, name: str = "operation"):
        self.name = name
        self.start_timestamp: Optional[float] = None
        self.last_step_time: Optional[float] = None
        self.step_times: Dict[str, float] = {}
        self.start_datetime: Optional[datetime] = None
        
    def start(self) -> 'TimeTracker':
        """시간 측정 시작"""
        self.start_timestamp = time.time()
        self.last_step_time = self.start_timestamp
        self.start_datetime = datetime.now()
        
        logger.debug(f"⏱️  {self.name} 시간 측정 시작")
        return self
    
    def step(self, step_name: str) -> float:
        """단계별 시간 측정"""
        if self.start_timestamp is None:
            raise ValueError("start()를 먼저 호출해야 합니다")
        
        current_time = time.time()
        step_duration = (current_time - self.last_step_time) * 1000  # ms
        
        self.step_times[step_name] = step_duration
        self.last_step_time = current_time
        
        logger.debug(f"📊 {self.name}.{step_name}: {step_duration:.2f}ms")
        return step_duration
    
    def finish(self) -> TimeMetrics:
        """시간 측정 완료"""
        if self.start_timestamp is None:
            raise ValueError("start()를 먼저 호출해야 합니다")
        
        end_time = datetime.now()
        total_seconds = time.time() - self.start_timestamp
        total_ms = total_seconds * 1000
        
        metrics = TimeMetrics(
            start_time=self.start_datetime,
            end_time=end_time,
            total_seconds=total_seconds,
            total_ms=total_ms,
            step_times=self.step_times.copy()
        )
        
        logger.info(f"✅ {self.name} 완료: {total_ms:.2f}ms")
        return metrics
    
    def get_current_duration_ms(self) -> float:
        """현재까지의 실행 시간 (ms)"""
        if self.start_timestamp is None:
            return 0.0
        return (time.time() - self.start_timestamp) * 1000

class PerformanceMonitor:
    """성능 모니터링 헬퍼"""
    
    @staticmethod
    def measure_async_function(func_name: str):
        """비동기 함수 실행 시간 측정 데코레이터"""
        def decorator(func):
            async def wrapper(*args, **kwargs):
                tracker = TimeTracker(func_name).start()
                try:
                    result = await func(*args, **kwargs)
                    metrics = tracker.finish()
                    
                    # 성능 로그
                    if metrics.total_ms > 1000:  # 1초 이상
                        logger.warning(f"🐌 느린 함수: {func_name} ({metrics.total_ms:.2f}ms)")
                    elif metrics.total_ms > 500:  # 0.5초 이상
                        logger.info(f"⚠️  주의 함수: {func_name} ({metrics.total_ms:.2f}ms)")
                    
                    return result
                except Exception as e:
                    tracker.finish()
                    logger.error(f"❌ {func_name} 실행 오류: {e}")
                    raise
            return wrapper
        return decorator
    
    @staticmethod
    def measure_sync_function(func_name: str):
        """동기 함수 실행 시간 측정 데코레이터"""
        def decorator(func):
            def wrapper(*args, **kwargs):
                tracker = TimeTracker(func_name).start()
                try:
                    result = func(*args, **kwargs)
                    metrics = tracker.finish()
                    
                    # 성능 로그
                    if metrics.total_ms > 500:  # 0.5초 이상
                        logger.warning(f"🐌 느린 동기 함수: {func_name} ({metrics.total_ms:.2f}ms)")
                    
                    return result
                except Exception as e:
                    tracker.finish()
                    logger.error(f"❌ {func_name} 실행 오류: {e}")
                    raise
            return wrapper
        return decorator

# 편의 함수들
def create_tracker(name: str) -> TimeTracker:
    """TimeTracker 생성 편의 함수"""
    return TimeTracker(name)

def measure_time(name: str):
    """컨텍스트 매니저로 시간 측정"""
    class TimeMeasureContext:
        def __init__(self, operation_name: str):
            self.tracker = TimeTracker(operation_name)
            self.metrics: Optional[TimeMetrics] = None
        
        def __enter__(self):
            self.tracker.start()
            return self.tracker
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            self.metrics = self.tracker.finish()
    
    return TimeMeasureContext(name)

# 사용 예시
if __name__ == "__main__":
    # 기본 사용법
    tracker = TimeTracker("test_operation").start()
    
    time.sleep(0.1)
    tracker.step("step1")
    
    time.sleep(0.05)
    tracker.step("step2")
    
    metrics = tracker.finish()
    print(f"총 시간: {metrics.total_ms:.2f}ms")
    print(f"단계별: {metrics.step_times}")
    
    # 컨텍스트 매니저 사용법
    with measure_time("context_test") as t:
        time.sleep(0.1)
        t.step("processing")
        time.sleep(0.05)