"""
고도화된 캐싱 시스템
다층 캐싱 구조, 캐시 무효화 전략, 일관성 보장
"""

import asyncio
import json
import time
import logging
import hashlib
from typing import Optional, Dict, Any, List, Set, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict, defaultdict
from abc import ABC, abstractmethod
from enum import Enum
import threading
import pickle

logger = logging.getLogger(__name__)

class CacheLevel(Enum):
    """캐시 레벨"""
    L1_MEMORY = "l1_memory"      # 메모리 캐시 (가장 빠름)
    L2_REDIS = "l2_redis"        # Redis 캐시 (선택사항)
    L3_DATABASE = "l3_database"  # 데이터베이스 캐시

class InvalidationStrategy(Enum):
    """캐시 무효화 전략"""
    TTL = "ttl"                  # Time To Live
    LRU = "lru"                  # Least Recently Used
    LFU = "lfu"                  # Least Frequently Used
    MANUAL = "manual"            # 수동 무효화
    TAG_BASED = "tag_based"      # 태그 기반 무효화

@dataclass
class CacheEntry:
    """고도화된 캐시 엔트리"""
    key: str
    data: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    tags: Set[str] = field(default_factory=set)
    size_bytes: int = 0
    version: int = 1
    dependencies: Set[str] = field(default_factory=set)
    
    @property
    def is_expired(self) -> bool:
        """TTL 기반 만료 확인"""
        if self.ttl_seconds is None:
            return False
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl_seconds)
    
    @property
    def age_seconds(self) -> int:
        """생성 후 경과 시간"""
        return int((datetime.now() - self.created_at).total_seconds())
    
    def touch(self):
        """접근 시간 및 횟수 업데이트"""
        self.last_accessed = datetime.now()
        self.access_count += 1

@dataclass
class CacheStats:
    """캐시 통계"""
    level: CacheLevel
    total_requests: int = 0
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    invalidations: int = 0
    size_bytes: int = 0
    entry_count: int = 0
    
    @property
    def hit_rate(self) -> float:
        """히트율 (%)"""
        if self.total_requests == 0:
            return 0.0
        return (self.hits / self.total_requests) * 100
    
    @property
    def miss_rate(self) -> float:
        """미스율 (%)"""
        return 100.0 - self.hit_rate

class CacheBackend(ABC):
    """캐시 백엔드 인터페이스"""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """데이터 조회"""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """데이터 저장"""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> bool:
        """데이터 삭제"""
        pass
    
    @abstractmethod
    async def clear(self) -> int:
        """모든 데이터 삭제"""
        pass
    
    @abstractmethod
    async def exists(self, key: str) -> bool:
        """키 존재 확인"""
        pass

class MemoryCacheBackend(CacheBackend):
    """메모리 캐시 백엔드"""
    
    def __init__(self, max_size: int = 1000, max_memory_mb: int = 100):
        self.max_size = max_size
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self.lock = threading.RLock()
        self.stats = CacheStats(CacheLevel.L1_MEMORY)
    
    async def get(self, key: str) -> Optional[Any]:
        with self.lock:
            self.stats.total_requests += 1
            
            if key not in self.cache:
                self.stats.misses += 1
                return None
            
            entry = self.cache[key]
            
            # 만료 확인
            if entry.is_expired:
                del self.cache[key]
                self.stats.misses += 1
                self.stats.evictions += 1
                return None
            
            # 히트 처리
            entry.touch()
            self.cache.move_to_end(key)  # LRU 업데이트
            self.stats.hits += 1
            
            return entry.data
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        with self.lock:
            try:
                # 데이터 크기 계산
                size_bytes = len(pickle.dumps(value))
                
                # 메모리 제한 확인
                if size_bytes > self.max_memory_bytes:
                    logger.warning(f"데이터 크기가 메모리 제한을 초과: {size_bytes} bytes")
                    return False
                
                # 기존 엔트리 업데이트 또는 새 엔트리 생성
                if key in self.cache:
                    entry = self.cache[key]
                    entry.data = value
                    entry.created_at = datetime.now()
                    entry.last_accessed = datetime.now()
                    entry.ttl_seconds = ttl
                    entry.size_bytes = size_bytes
                    entry.version += 1
                else:
                    entry = CacheEntry(
                        key=key,
                        data=value,
                        created_at=datetime.now(),
                        last_accessed=datetime.now(),
                        ttl_seconds=ttl,
                        size_bytes=size_bytes
                    )
                    self.cache[key] = entry
                
                # 캐시 크기 제한 확인
                self._evict_if_needed()
                
                # 통계 업데이트
                self._update_stats()
                
                return True
                
            except Exception as e:
                logger.error(f"메모리 캐시 저장 오류: {key} - {e}")
                return False
    
    async def delete(self, key: str) -> bool:
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                self.stats.invalidations += 1
                self._update_stats()
                return True
            return False
    
    async def clear(self) -> int:
        with self.lock:
            count = len(self.cache)
            self.cache.clear()
            self._update_stats()
            return count
    
    async def exists(self, key: str) -> bool:
        with self.lock:
            return key in self.cache and not self.cache[key].is_expired
    
    def _evict_if_needed(self):
        """필요시 캐시 엔트리 제거"""
        # 크기 제한 확인
        while len(self.cache) > self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
            self.stats.evictions += 1
        
        # 메모리 제한 확인
        total_size = sum(entry.size_bytes for entry in self.cache.values())
        while total_size > self.max_memory_bytes and self.cache:
            oldest_key = next(iter(self.cache))
            total_size -= self.cache[oldest_key].size_bytes
            del self.cache[oldest_key]
            self.stats.evictions += 1
    
    def _update_stats(self):
        """통계 업데이트"""
        self.stats.entry_count = len(self.cache)
        self.stats.size_bytes = sum(entry.size_bytes for entry in self.cache.values())

class RedisCacheBackend(CacheBackend):
    """Redis 캐시 백엔드 (선택사항)"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client = None
        self.stats = CacheStats(CacheLevel.L2_REDIS)
        
        # Redis 연결은 실제 사용 시에만 초기화
        logger.info(f"Redis 캐시 백엔드 초기화: {redis_url}")
    
    async def _get_redis_client(self):
        """Redis 클라이언트 지연 초기화"""
        if self.redis_client is None:
            try:
                import redis.asyncio as redis
                self.redis_client = redis.from_url(self.redis_url)
                await self.redis_client.ping()
                logger.info("Redis 연결 성공")
            except ImportError:
                logger.warning("redis 패키지가 설치되지 않음. Redis 캐시 비활성화")
                return None
            except Exception as e:
                logger.error(f"Redis 연결 실패: {e}")
                return None
        
        return self.redis_client
    
    async def get(self, key: str) -> Optional[Any]:
        client = await self._get_redis_client()
        if not client:
            return None
        
        try:
            self.stats.total_requests += 1
            
            data = await client.get(key)
            if data is None:
                self.stats.misses += 1
                return None
            
            self.stats.hits += 1
            return pickle.loads(data)
            
        except Exception as e:
            logger.error(f"Redis 조회 오류: {key} - {e}")
            self.stats.misses += 1
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        client = await self._get_redis_client()
        if not client:
            return False
        
        try:
            data = pickle.dumps(value)
            
            if ttl:
                await client.setex(key, ttl, data)
            else:
                await client.set(key, data)
            
            return True
            
        except Exception as e:
            logger.error(f"Redis 저장 오류: {key} - {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        client = await self._get_redis_client()
        if not client:
            return False
        
        try:
            result = await client.delete(key)
            if result > 0:
                self.stats.invalidations += 1
            return result > 0
            
        except Exception as e:
            logger.error(f"Redis 삭제 오류: {key} - {e}")
            return False
    
    async def clear(self) -> int:
        client = await self._get_redis_client()
        if not client:
            return 0
        
        try:
            # 주의: 전체 Redis DB를 삭제함
            await client.flushdb()
            return 1  # 정확한 개수는 알 수 없음
            
        except Exception as e:
            logger.error(f"Redis 전체 삭제 오류: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        client = await self._get_redis_client()
        if not client:
            return False
        
        try:
            return await client.exists(key) > 0
        except Exception as e:
            logger.error(f"Redis 존재 확인 오류: {key} - {e}")
            return False

class MultiLevelCache:
    """다층 캐시 시스템"""
    
    def __init__(
        self,
        enable_l1_memory: bool = True,
        enable_l2_redis: bool = False,
        l1_max_size: int = 1000,
        l1_max_memory_mb: int = 100,
        redis_url: str = "redis://localhost:6379"
    ):
        self.backends: Dict[CacheLevel, CacheBackend] = {}
        self.cache_hierarchy = []
        
        # L1 메모리 캐시
        if enable_l1_memory:
            self.backends[CacheLevel.L1_MEMORY] = MemoryCacheBackend(
                max_size=l1_max_size,
                max_memory_mb=l1_max_memory_mb
            )
            self.cache_hierarchy.append(CacheLevel.L1_MEMORY)
        
        # L2 Redis 캐시 (선택사항)
        if enable_l2_redis:
            self.backends[CacheLevel.L2_REDIS] = RedisCacheBackend(redis_url)
            self.cache_hierarchy.append(CacheLevel.L2_REDIS)
        
        # 태그 기반 무효화를 위한 태그 매핑
        self.tag_to_keys: Dict[str, Set[str]] = defaultdict(set)
        self.key_to_tags: Dict[str, Set[str]] = defaultdict(set)
        self.lock = threading.RLock()
        
        logger.info(f"다층 캐시 초기화: 레벨={[level.value for level in self.cache_hierarchy]}")
    
    async def get(self, key: str) -> Optional[Any]:
        """다층 캐시에서 데이터 조회"""
        for level in self.cache_hierarchy:
            backend = self.backends[level]
            
            try:
                value = await backend.get(key)
                if value is not None:
                    # 상위 레벨 캐시에 복사 (캐시 승격)
                    await self._promote_to_upper_levels(key, value, level)
                    return value
            except Exception as e:
                logger.error(f"캐시 조회 오류 ({level.value}): {key} - {e}")
                continue
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        level: Optional[CacheLevel] = None
    ) -> bool:
        """다층 캐시에 데이터 저장"""
        success = False
        
        # 특정 레벨 지정 시 해당 레벨에만 저장
        if level and level in self.backends:
            success = await self.backends[level].set(key, value, ttl)
        else:
            # 모든 레벨에 저장
            for cache_level in self.cache_hierarchy:
                backend = self.backends[cache_level]
                try:
                    if await backend.set(key, value, ttl):
                        success = True
                except Exception as e:
                    logger.error(f"캐시 저장 오류 ({cache_level.value}): {key} - {e}")
        
        # 태그 매핑 업데이트
        if success and tags:
            with self.lock:
                self.key_to_tags[key] = tags
                for tag in tags:
                    self.tag_to_keys[tag].add(key)
        
        return success
    
    async def delete(self, key: str) -> bool:
        """다층 캐시에서 데이터 삭제"""
        success = False
        
        for level in self.cache_hierarchy:
            backend = self.backends[level]
            try:
                if await backend.delete(key):
                    success = True
            except Exception as e:
                logger.error(f"캐시 삭제 오류 ({level.value}): {key} - {e}")
        
        # 태그 매핑 정리
        with self.lock:
            if key in self.key_to_tags:
                tags = self.key_to_tags[key]
                for tag in tags:
                    self.tag_to_keys[tag].discard(key)
                del self.key_to_tags[key]
        
        return success
    
    async def invalidate_by_tags(self, tags: Set[str]) -> int:
        """태그 기반 캐시 무효화"""
        invalidated_count = 0
        
        with self.lock:
            keys_to_invalidate = set()
            
            for tag in tags:
                if tag in self.tag_to_keys:
                    keys_to_invalidate.update(self.tag_to_keys[tag])
        
        # 해당 키들 삭제
        for key in keys_to_invalidate:
            if await self.delete(key):
                invalidated_count += 1
        
        logger.info(f"태그 기반 캐시 무효화: {len(tags)}개 태그, {invalidated_count}개 키 삭제")
        return invalidated_count
    
    async def invalidate_by_pattern(self, pattern: str) -> int:
        """패턴 기반 캐시 무효화 (메모리 캐시만 지원)"""
        invalidated_count = 0
        
        # 메모리 캐시에서 패턴 매칭 키 찾기
        if CacheLevel.L1_MEMORY in self.backends:
            memory_backend = self.backends[CacheLevel.L1_MEMORY]
            if isinstance(memory_backend, MemoryCacheBackend):
                with memory_backend.lock:
                    keys_to_delete = []
                    for key in memory_backend.cache.keys():
                        if self._match_pattern(key, pattern):
                            keys_to_delete.append(key)
                    
                    for key in keys_to_delete:
                        if await self.delete(key):
                            invalidated_count += 1
        
        logger.info(f"패턴 기반 캐시 무효화: 패턴={pattern}, {invalidated_count}개 키 삭제")
        return invalidated_count
    
    async def clear_all(self) -> Dict[CacheLevel, int]:
        """모든 캐시 삭제"""
        results = {}
        
        for level in self.cache_hierarchy:
            backend = self.backends[level]
            try:
                count = await backend.clear()
                results[level] = count
            except Exception as e:
                logger.error(f"캐시 전체 삭제 오류 ({level.value}): {e}")
                results[level] = 0
        
        # 태그 매핑 정리
        with self.lock:
            self.tag_to_keys.clear()
            self.key_to_tags.clear()
        
        return results
    
    async def get_stats(self) -> Dict[CacheLevel, CacheStats]:
        """모든 레벨의 캐시 통계"""
        stats = {}
        
        for level, backend in self.backends.items():
            if hasattr(backend, 'stats'):
                stats[level] = backend.stats
            else:
                stats[level] = CacheStats(level)
        
        return stats
    
    async def get_cache_info(self) -> Dict[str, Any]:
        """캐시 상태 정보"""
        stats = await self.get_stats()
        
        info = {
            'levels': [level.value for level in self.cache_hierarchy],
            'total_entries': sum(stat.entry_count for stat in stats.values()),
            'total_size_mb': sum(stat.size_bytes for stat in stats.values()) / 1024 / 1024,
            'overall_hit_rate': 0.0,
            'level_stats': {}
        }
        
        # 전체 히트율 계산
        total_requests = sum(stat.total_requests for stat in stats.values())
        total_hits = sum(stat.hits for stat in stats.values())
        if total_requests > 0:
            info['overall_hit_rate'] = (total_hits / total_requests) * 100
        
        # 레벨별 통계
        for level, stat in stats.items():
            info['level_stats'][level.value] = {
                'hit_rate': stat.hit_rate,
                'total_requests': stat.total_requests,
                'hits': stat.hits,
                'misses': stat.misses,
                'entry_count': stat.entry_count,
                'size_mb': stat.size_bytes / 1024 / 1024
            }
        
        return info
    
    async def _promote_to_upper_levels(self, key: str, value: Any, found_level: CacheLevel):
        """상위 레벨 캐시로 데이터 승격"""
        found_index = self.cache_hierarchy.index(found_level)
        
        # 상위 레벨들에 복사
        for i in range(found_index):
            upper_level = self.cache_hierarchy[i]
            backend = self.backends[upper_level]
            
            try:
                await backend.set(key, value)
            except Exception as e:
                logger.error(f"캐시 승격 오류 ({upper_level.value}): {key} - {e}")
    
    def _match_pattern(self, key: str, pattern: str) -> bool:
        """간단한 패턴 매칭 (와일드카드 지원)"""
        import fnmatch
        return fnmatch.fnmatch(key, pattern)

class CacheManager:
    """캐시 관리자 - 개인화 엔진용 특화"""
    
    def __init__(self, cache: MultiLevelCache):
        self.cache = cache
        self.key_generators = {
            'product_analysis': lambda product_id: f"product_analysis_{product_id}",
            'ingredient_effect': lambda ingredient_id: f"ingredient_effect_{ingredient_id}",
            'user_profile': lambda user_id: f"user_profile_{user_id}",
            'product_score': lambda product_id, user_id: f"product_score_{product_id}_{user_id}",
            'recommendation': lambda intent_hash, user_hash: f"recommendation_{intent_hash}_{user_hash}"
        }
    
    async def get_product_analysis(self, product_id: int):
        """제품 분석 결과 조회"""
        key = self.key_generators['product_analysis'](product_id)
        return await self.cache.get(key)
    
    async def set_product_analysis(self, product_id: int, analysis: Any, ttl: int = 7200):
        """제품 분석 결과 저장"""
        key = self.key_generators['product_analysis'](product_id)
        tags = {'product_analysis', f'product_{product_id}'}
        return await self.cache.set(key, analysis, ttl=ttl, tags=tags)
    
    async def get_user_profile(self, user_id: str):
        """사용자 프로필 조회"""
        key = self.key_generators['user_profile'](user_id)
        return await self.cache.get(key)
    
    async def set_user_profile(self, user_id: str, profile: Any, ttl: int = 3600):
        """사용자 프로필 저장"""
        key = self.key_generators['user_profile'](user_id)
        tags = {'user_profile', f'user_{user_id}'}
        return await self.cache.set(key, profile, ttl=ttl, tags=tags)
    
    async def invalidate_user_data(self, user_id: str):
        """특정 사용자 관련 모든 캐시 무효화"""
        tags = {f'user_{user_id}'}
        return await self.cache.invalidate_by_tags(tags)
    
    async def invalidate_product_data(self, product_id: int):
        """특정 제품 관련 모든 캐시 무효화"""
        tags = {f'product_{product_id}'}
        return await self.cache.invalidate_by_tags(tags)
    
    def generate_cache_key(self, key_type: str, *args) -> str:
        """캐시 키 생성"""
        if key_type in self.key_generators:
            return self.key_generators[key_type](*args)
        else:
            # 기본 키 생성
            return f"{key_type}_{'_'.join(map(str, args))}"
    
    def generate_hash_key(self, data: Any) -> str:
        """데이터 해시 기반 키 생성"""
        if isinstance(data, dict):
            # 딕셔너리를 정렬된 JSON 문자열로 변환
            json_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        else:
            json_str = str(data)
        
        return hashlib.md5(json_str.encode('utf-8')).hexdigest()

# 전역 캐시 인스턴스
_cache_manager: Optional[CacheManager] = None

def get_cache_manager() -> CacheManager:
    """캐시 매니저 인스턴스 반환 (싱글톤)"""
    global _cache_manager
    if _cache_manager is None:
        # 기본 설정으로 다층 캐시 생성
        multi_cache = MultiLevelCache(
            enable_l1_memory=True,
            enable_l2_redis=False,  # Redis는 선택사항
            l1_max_size=2000,
            l1_max_memory_mb=200
        )
        _cache_manager = CacheManager(multi_cache)
        logger.info("CacheManager 인스턴스 생성")
    return _cache_manager

async def init_cache_system(
    enable_redis: bool = False,
    redis_url: str = "redis://localhost:6379",
    l1_max_size: int = 2000,
    l1_max_memory_mb: int = 200
):
    """캐시 시스템 초기화"""
    global _cache_manager
    
    multi_cache = MultiLevelCache(
        enable_l1_memory=True,
        enable_l2_redis=enable_redis,
        l1_max_size=l1_max_size,
        l1_max_memory_mb=l1_max_memory_mb,
        redis_url=redis_url
    )
    
    _cache_manager = CacheManager(multi_cache)
    logger.info(f"캐시 시스템 초기화 완료: Redis={enable_redis}")
    return _cache_manager

async def cleanup_cache_system():
    """캐시 시스템 정리"""
    global _cache_manager
    if _cache_manager:
        await _cache_manager.cache.clear_all()
        _cache_manager = None
        logger.info("캐시 시스템 정리 완료")