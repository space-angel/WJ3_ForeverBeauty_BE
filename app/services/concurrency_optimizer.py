"""
동시성 처리 최적화
비동기 처리, 데이터베이스 연결 풀 최적화, 리소스 경합 최소화
"""

import asyncio
import logging
import time
import threading
from typing import Dict, List, Optional, Any, Callable, Awaitable, TypeVar, Generic
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
import weakref
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar('T')

class TaskPriority(Enum):
    """작업 우선순위"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class TaskMetrics:
    """작업 메트릭"""
    task_id: str
    priority: TaskPriority
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    execution_time_ms: float = 0.0
    queue_time_ms: float = 0.0
    success: bool = True
    error_message: Optional[str] = None

@dataclass
class ConcurrencyStats:
    """동시성 통계"""
    active_tasks: int = 0
    queued_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_execution_time_ms: float = 0.0
    avg_queue_time_ms: float = 0.0
    max_concurrent_tasks: int = 0
    total_throughput: float = 0.0  # tasks per second

class AsyncTaskQueue:
    """비동기 작업 큐 (우선순위 지원)"""
    
    def __init__(self, max_concurrent_tasks: int = 100):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.task_queues: Dict[TaskPriority, asyncio.Queue] = {
            priority: asyncio.Queue() for priority in TaskPriority
        }
        self.task_metrics: Dict[str, TaskMetrics] = {}
        self.stats = ConcurrencyStats()
        
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []
        self._lock = asyncio.Lock()
        
        # AsyncTaskQueue 초기화
    
    async def start(self):
        """작업 큐 시작"""
        if self._running:
            return
        
        self._running = True
        
        # 우선순위별 워커 생성
        for priority in TaskPriority:
            worker_count = self._get_worker_count(priority)
            for i in range(worker_count):
                worker = asyncio.create_task(
                    self._worker(priority, f"{priority.name}_worker_{i}")
                )
                self._worker_tasks.append(worker)
        
        # 작업 큐 시작
    
    async def stop(self):
        """작업 큐 중지"""
        self._running = False
        
        # 모든 워커 취소
        for worker in self._worker_tasks:
            worker.cancel()
        
        # 워커 완료 대기
        if self._worker_tasks:
            await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        
        self._worker_tasks.clear()
        # 작업 큐 중지 완료
    
    async def submit_task(
        self,
        coro: Awaitable[T],
        priority: TaskPriority = TaskPriority.NORMAL,
        task_id: Optional[str] = None
    ) -> str:
        """작업 제출"""
        if not self._running:
            await self.start()
        
        task_id = task_id or f"task_{int(time.time() * 1000000)}"
        
        # 메트릭 생성
        metric = TaskMetrics(
            task_id=task_id,
            priority=priority,
            created_at=datetime.now()
        )
        
        async with self._lock:
            self.task_metrics[task_id] = metric
            await self.task_queues[priority].put((task_id, coro))
            self.stats.queued_tasks += 1
        
        logger.debug(f"작업 제출: {task_id} (우선순위: {priority.name})")
        return task_id
    
    async def wait_for_task(self, task_id: str, timeout: Optional[float] = None) -> Any:
        """특정 작업 완료 대기"""
        start_time = time.time()
        
        while True:
            if task_id in self.task_metrics:
                metric = self.task_metrics[task_id]
                if metric.completed_at is not None:
                    if metric.success:
                        return metric  # 성공 시 메트릭 반환
                    else:
                        raise Exception(metric.error_message)
            
            if timeout and (time.time() - start_time) > timeout:
                raise asyncio.TimeoutError(f"작업 대기 시간 초과: {task_id}")
            
            await asyncio.sleep(0.1)
    
    async def cancel_task(self, task_id: str) -> bool:
        """작업 취소"""
        async with self._lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                task.cancel()
                del self.active_tasks[task_id]
                
                # 메트릭 업데이트
                if task_id in self.task_metrics:
                    metric = self.task_metrics[task_id]
                    metric.completed_at = datetime.now()
                    metric.success = False
                    metric.error_message = "작업 취소됨"
                
                # 작업 취소
                return True
        
        return False
    
    async def get_stats(self) -> ConcurrencyStats:
        """동시성 통계 조회"""
        async with self._lock:
            # 실시간 통계 업데이트
            self.stats.active_tasks = len(self.active_tasks)
            self.stats.queued_tasks = sum(
                queue.qsize() for queue in self.task_queues.values()
            )
            
            # 완료된 작업들의 평균 실행 시간 계산
            completed_metrics = [
                m for m in self.task_metrics.values()
                if m.completed_at is not None
            ]
            
            if completed_metrics:
                self.stats.avg_execution_time_ms = sum(
                    m.execution_time_ms for m in completed_metrics
                ) / len(completed_metrics)
                
                self.stats.avg_queue_time_ms = sum(
                    m.queue_time_ms for m in completed_metrics
                ) / len(completed_metrics)
            
            return self.stats
    
    async def _worker(self, priority: TaskPriority, worker_name: str):
        """워커 코루틴"""
        logger.debug(f"워커 시작: {worker_name}")
        
        while self._running:
            try:
                # 작업 대기 (타임아웃으로 주기적 체크)
                try:
                    task_id, coro = await asyncio.wait_for(
                        self.task_queues[priority].get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # 동시 실행 제한 확인
                async with self._lock:
                    if len(self.active_tasks) >= self.max_concurrent_tasks:
                        # 큐에 다시 넣기
                        await self.task_queues[priority].put((task_id, coro))
                        await asyncio.sleep(0.1)
                        continue
                
                # 작업 실행
                await self._execute_task(task_id, coro, worker_name)
                
            except asyncio.CancelledError:
                logger.debug(f"워커 취소: {worker_name}")
                break
            except Exception as e:
                logger.error(f"워커 오류 ({worker_name}): {e}")
                await asyncio.sleep(0.1)
        
        logger.debug(f"워커 종료: {worker_name}")
    
    async def _execute_task(self, task_id: str, coro: Awaitable, worker_name: str):
        """작업 실행"""
        metric = self.task_metrics.get(task_id)
        if not metric:
            return
        
        # 실행 시작
        start_time = time.time()
        metric.started_at = datetime.now()
        metric.queue_time_ms = (metric.started_at - metric.created_at).total_seconds() * 1000
        
        async with self._lock:
            self.stats.queued_tasks -= 1
            self.stats.active_tasks += 1
            self.stats.max_concurrent_tasks = max(
                self.stats.max_concurrent_tasks,
                len(self.active_tasks)
            )
        
        try:
            # 작업 실행
            task = asyncio.create_task(coro)
            self.active_tasks[task_id] = task
            
            result = await task
            
            # 성공 처리
            metric.success = True
            logger.debug(f"작업 완료: {task_id} (워커: {worker_name})")
            
        except asyncio.CancelledError:
            metric.success = False
            metric.error_message = "작업 취소됨"
            logger.debug(f"작업 취소: {task_id}")
            
        except Exception as e:
            metric.success = False
            metric.error_message = str(e)
            logger.error(f"작업 실패: {task_id} - {e}")
            
        finally:
            # 정리
            end_time = time.time()
            metric.completed_at = datetime.now()
            metric.execution_time_ms = (end_time - start_time) * 1000
            
            async with self._lock:
                if task_id in self.active_tasks:
                    del self.active_tasks[task_id]
                self.stats.active_tasks -= 1
                
                if metric.success:
                    self.stats.completed_tasks += 1
                else:
                    self.stats.failed_tasks += 1
    
    def _get_worker_count(self, priority: TaskPriority) -> int:
        """우선순위별 워커 수 결정"""
        worker_counts = {
            TaskPriority.CRITICAL: max(2, self.max_concurrent_tasks // 10),
            TaskPriority.HIGH: max(2, self.max_concurrent_tasks // 20),
            TaskPriority.NORMAL: max(1, self.max_concurrent_tasks // 50),
            TaskPriority.LOW: 1
        }
        return worker_counts[priority]

class ConnectionPool:
    """데이터베이스 연결 풀 최적화"""
    
    def __init__(
        self,
        min_connections: int = 5,
        max_connections: int = 20,
        connection_timeout: float = 30.0,
        idle_timeout: float = 300.0
    ):
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.idle_timeout = idle_timeout
        
        self.available_connections: asyncio.Queue = asyncio.Queue(maxsize=max_connections)
        self.active_connections: Dict[str, Any] = {}
        self.connection_stats: Dict[str, Dict[str, Any]] = {}
        
        self._lock = asyncio.Lock()
        self._connection_id_counter = 0
        self._cleanup_task: Optional[asyncio.Task] = None
        
        # ConnectionPool 초기화
    
    async def initialize(self, connection_factory: Callable[[], Awaitable[Any]]):
        """연결 풀 초기화"""
        self.connection_factory = connection_factory
        
        # 최소 연결 수만큼 미리 생성
        for _ in range(self.min_connections):
            conn = await self._create_connection()
            await self.available_connections.put(conn)
        
        # 정리 작업 시작
        self._cleanup_task = asyncio.create_task(self._cleanup_idle_connections())
        
        # 연결 풀 초기화 완료
    
    @asynccontextmanager
    async def get_connection(self):
        """연결 획득 (컨텍스트 매니저)"""
        conn = None
        conn_id = None
        
        try:
            # 연결 획득
            conn, conn_id = await self._acquire_connection()
            yield conn
            
        finally:
            # 연결 반환
            if conn and conn_id:
                await self._release_connection(conn, conn_id)
    
    async def _acquire_connection(self) -> tuple[Any, str]:
        """연결 획득"""
        start_time = time.time()
        
        try:
            # 사용 가능한 연결 대기
            conn = await asyncio.wait_for(
                self.available_connections.get(),
                timeout=self.connection_timeout
            )
            
            # 연결 ID 생성
            async with self._lock:
                self._connection_id_counter += 1
                conn_id = f"conn_{self._connection_id_counter}"
                
                # 활성 연결로 이동
                self.active_connections[conn_id] = conn
                
                # 통계 업데이트
                self.connection_stats[conn_id] = {
                    'acquired_at': datetime.now(),
                    'acquire_time_ms': (time.time() - start_time) * 1000,
                    'query_count': 0
                }
            
            logger.debug(f"연결 획득: {conn_id} ({(time.time() - start_time) * 1000:.1f}ms)")
            return conn, conn_id
            
        except asyncio.TimeoutError:
            logger.error(f"연결 획득 시간 초과: {self.connection_timeout}s")
            raise
        except Exception as e:
            logger.error(f"연결 획득 실패: {e}")
            raise
    
    async def _release_connection(self, conn: Any, conn_id: str):
        """연결 반환"""
        async with self._lock:
            if conn_id in self.active_connections:
                del self.active_connections[conn_id]
                
                # 통계 업데이트
                if conn_id in self.connection_stats:
                    stats = self.connection_stats[conn_id]
                    stats['released_at'] = datetime.now()
                    stats['usage_time_ms'] = (
                        stats['released_at'] - stats['acquired_at']
                    ).total_seconds() * 1000
                    
                    # 통계 보관 (최근 1000개만)
                    if len(self.connection_stats) > 1000:
                        oldest_key = min(
                            self.connection_stats.keys(),
                            key=lambda k: self.connection_stats[k]['acquired_at']
                        )
                        del self.connection_stats[oldest_key]
        
        # 연결을 사용 가능 풀로 반환
        try:
            await self.available_connections.put(conn)
            logger.debug(f"연결 반환: {conn_id}")
        except Exception as e:
            logger.error(f"연결 반환 실패: {conn_id} - {e}")
    
    async def _create_connection(self) -> Any:
        """새 연결 생성"""
        try:
            conn = await self.connection_factory()
            logger.debug("새 데이터베이스 연결 생성")
            return conn
        except Exception as e:
            logger.error(f"연결 생성 실패: {e}")
            raise
    
    async def _cleanup_idle_connections(self):
        """유휴 연결 정리"""
        while True:
            try:
                await asyncio.sleep(60)  # 1분마다 정리
                
                current_time = datetime.now()
                idle_threshold = current_time - timedelta(seconds=self.idle_timeout)
                
                # 유휴 연결 식별 및 정리
                connections_to_close = []
                
                async with self._lock:
                    for conn_id, stats in list(self.connection_stats.items()):
                        if 'released_at' in stats and stats['released_at'] < idle_threshold:
                            connections_to_close.append(conn_id)
                
                # 유휴 연결 정리 (최소 연결 수 유지)
                current_pool_size = self.available_connections.qsize()
                if current_pool_size > self.min_connections:
                    cleanup_count = min(
                        len(connections_to_close),
                        current_pool_size - self.min_connections
                    )
                    
                    for _ in range(cleanup_count):
                        try:
                            # 타임아웃 없이 즉시 확인
                            conn = self.available_connections.get_nowait()
                            # 연결 종료 (실제 구현에서는 conn.close() 등 호출)
                            logger.debug("유휴 연결 정리")
                        except asyncio.QueueEmpty:
                            break
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"연결 정리 오류: {e}")
    
    async def get_pool_stats(self) -> Dict[str, Any]:
        """연결 풀 통계"""
        async with self._lock:
            recent_stats = [
                stats for stats in self.connection_stats.values()
                if 'released_at' in stats and 
                stats['released_at'] > datetime.now() - timedelta(hours=1)
            ]
            
            avg_acquire_time = 0.0
            avg_usage_time = 0.0
            total_queries = 0
            
            if recent_stats:
                avg_acquire_time = sum(
                    stats['acquire_time_ms'] for stats in recent_stats
                ) / len(recent_stats)
                
                avg_usage_time = sum(
                    stats.get('usage_time_ms', 0) for stats in recent_stats
                ) / len(recent_stats)
                
                total_queries = sum(
                    stats['query_count'] for stats in recent_stats
                )
            
            return {
                'available_connections': self.available_connections.qsize(),
                'active_connections': len(self.active_connections),
                'total_connections': self.available_connections.qsize() + len(self.active_connections),
                'max_connections': self.max_connections,
                'min_connections': self.min_connections,
                'avg_acquire_time_ms': avg_acquire_time,
                'avg_usage_time_ms': avg_usage_time,
                'total_queries_last_hour': total_queries,
                'connection_utilization': (len(self.active_connections) / self.max_connections) * 100
            }
    
    async def close_all(self):
        """모든 연결 종료"""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        
        # 모든 연결 종료 (실제 구현에서는 각 연결의 close() 메서드 호출)
        async with self._lock:
            while not self.available_connections.empty():
                try:
                    conn = self.available_connections.get_nowait()
                    # conn.close() 호출
                except asyncio.QueueEmpty:
                    break
            
            self.active_connections.clear()
            self.connection_stats.clear()
        
        # 모든 데이터베이스 연결 종료

class ResourceLock:
    """리소스 경합 최소화를 위한 고급 락"""
    
    def __init__(self, max_readers: int = 10):
        self.max_readers = max_readers
        self.readers = 0
        self.writers = 0
        self.read_ready = asyncio.Condition()
        self.write_ready = asyncio.Condition()
        self._lock = asyncio.Lock()
    
    @asynccontextmanager
    async def read_lock(self):
        """읽기 락 획득"""
        async with self._lock:
            async with self.read_ready:
                await self.read_ready.wait_for(
                    lambda: self.writers == 0 and self.readers < self.max_readers
                )
                self.readers += 1
        
        try:
            yield
        finally:
            async with self._lock:
                self.readers -= 1
                if self.readers == 0:
                    async with self.write_ready:
                        self.write_ready.notify_all()
    
    @asynccontextmanager
    async def write_lock(self):
        """쓰기 락 획득"""
        async with self._lock:
            async with self.write_ready:
                await self.write_ready.wait_for(
                    lambda: self.writers == 0 and self.readers == 0
                )
                self.writers += 1
        
        try:
            yield
        finally:
            async with self._lock:
                self.writers -= 1
                async with self.read_ready:
                    self.read_ready.notify_all()
                async with self.write_ready:
                    self.write_ready.notify_all()

class ConcurrencyOptimizer:
    """동시성 최적화 관리자"""
    
    def __init__(
        self,
        max_concurrent_tasks: int = 100,
        max_db_connections: int = 20,
        enable_task_queue: bool = True
    ):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.max_db_connections = max_db_connections
        
        # 컴포넌트 초기화
        self.task_queue = AsyncTaskQueue(max_concurrent_tasks) if enable_task_queue else None
        self.connection_pool: Optional[ConnectionPool] = None
        self.resource_locks: Dict[str, ResourceLock] = {}
        
        # 통계
        self.optimization_stats = {
            'total_optimized_operations': 0,
            'avg_response_time_improvement': 0.0,
            'concurrent_request_peak': 0,
            'resource_contention_events': 0
        }
        
        # ConcurrencyOptimizer 초기화
    
    async def initialize(self, db_connection_factory: Optional[Callable] = None):
        """동시성 최적화 시스템 초기화"""
        # 작업 큐 시작
        if self.task_queue:
            await self.task_queue.start()
        
        # 연결 풀 초기화
        if db_connection_factory:
            self.connection_pool = ConnectionPool(
                min_connections=5,
                max_connections=self.max_db_connections
            )
            await self.connection_pool.initialize(db_connection_factory)
        
        # 동시성 최적화 시스템 초기화 완료
    
    async def optimize_batch_processing(
        self,
        items: List[Any],
        processor: Callable[[Any], Awaitable[Any]],
        batch_size: int = 10,
        priority: TaskPriority = TaskPriority.NORMAL
    ) -> List[Any]:
        """배치 처리 최적화"""
        if not self.task_queue:
            # 작업 큐가 없으면 기본 병렬 처리
            return await asyncio.gather(*[processor(item) for item in items])
        
        results = []
        
        # 배치 단위로 작업 제출
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            # 배치 처리 코루틴 생성
            async def process_batch(batch_items):
                return await asyncio.gather(*[processor(item) for item in batch_items])
            
            # 작업 큐에 제출
            task_id = await self.task_queue.submit_task(
                process_batch(batch),
                priority=priority
            )
            
            # 결과 대기
            batch_result = await self.task_queue.wait_for_task(task_id)
            if isinstance(batch_result, list):
                results.extend(batch_result)
            else:
                results.append(batch_result)
        
        return results
    
    async def optimize_database_operations(
        self,
        operations: List[Callable[[], Awaitable[Any]]]
    ) -> List[Any]:
        """데이터베이스 작업 최적화"""
        if not self.connection_pool:
            # 연결 풀이 없으면 순차 실행
            return [await op() for op in operations]
        
        results = []
        
        # 연결 풀을 사용한 병렬 실행
        async def execute_with_pool(operation):
            async with self.connection_pool.get_connection() as conn:
                return await operation()
        
        # 병렬 실행
        results = await asyncio.gather(*[
            execute_with_pool(op) for op in operations
        ])
        
        return results
    
    def get_resource_lock(self, resource_name: str, max_readers: int = 10) -> ResourceLock:
        """리소스별 락 획득"""
        if resource_name not in self.resource_locks:
            self.resource_locks[resource_name] = ResourceLock(max_readers)
        return self.resource_locks[resource_name]
    
    async def get_optimization_stats(self) -> Dict[str, Any]:
        """최적화 통계 조회"""
        stats = {
            'optimization_stats': self.optimization_stats.copy(),
            'task_queue_stats': None,
            'connection_pool_stats': None,
            'resource_locks': len(self.resource_locks)
        }
        
        # 작업 큐 통계
        if self.task_queue:
            stats['task_queue_stats'] = await self.task_queue.get_stats()
        
        # 연결 풀 통계
        if self.connection_pool:
            stats['connection_pool_stats'] = await self.connection_pool.get_pool_stats()
        
        return stats
    
    async def cleanup(self):
        """리소스 정리"""
        # 작업 큐 중지
        if self.task_queue:
            await self.task_queue.stop()
        
        # 연결 풀 종료
        if self.connection_pool:
            await self.connection_pool.close_all()
        
        # 리소스 락 정리
        self.resource_locks.clear()
        
        # 동시성 최적화 시스템 정리 완료

# 전역 동시성 최적화 인스턴스
_concurrency_optimizer: Optional[ConcurrencyOptimizer] = None

def get_concurrency_optimizer() -> ConcurrencyOptimizer:
    """동시성 최적화 인스턴스 반환 (싱글톤)"""
    global _concurrency_optimizer
    if _concurrency_optimizer is None:
        _concurrency_optimizer = ConcurrencyOptimizer()
        # ConcurrencyOptimizer 인스턴스 생성
    return _concurrency_optimizer

async def init_concurrency_system(
    max_concurrent_tasks: int = 100,
    max_db_connections: int = 20,
    db_connection_factory: Optional[Callable] = None
):
    """동시성 시스템 초기화"""
    global _concurrency_optimizer
    
    _concurrency_optimizer = ConcurrencyOptimizer(
        max_concurrent_tasks=max_concurrent_tasks,
        max_db_connections=max_db_connections
    )
    
    await _concurrency_optimizer.initialize(db_connection_factory)
    # 동시성 시스템 초기화 완료
    return _concurrency_optimizer

async def cleanup_concurrency_system():
    """동시성 시스템 정리"""
    global _concurrency_optimizer
    if _concurrency_optimizer:
        await _concurrency_optimizer.cleanup()
        _concurrency_optimizer = None
        # 동시성 시스템 정리 완료