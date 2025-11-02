"""
성분 분석 캐싱 시스템
TTL 기반 메모리 캐시 및 성능 모니터링
"""

import time
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import OrderedDict
import threading

from app.models.personalization_models import ProductIngredientAnalysis

logger = logging.getLogger(__name__)

@dataclass
class CacheEntry:
    """캐시 엔트리"""
    data: Any
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl_seconds: int = 3600
    
    @property
    def is_expired(self) -> bool:
        """캐시 만료 여부 확인"""
        return datetime.now() > self.created_at + timedelta(seconds=self.ttl_seconds)
    
    @property
    def age_seconds(self) -> int:
        """캐시 생성 후 경과 시간 (초)"""
        return int((datetime.now() - self.created_at).total_seconds())

@dataclass
class CacheStats:
    """캐시 통계"""
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    evictions: int = 0
    expired_entries: int = 0
    
    @property
    def hit_rate(self) -> float:
        """캐시 히트율 (%)"""
        if self.total_requests == 0:
            return 0.0
        return (self.cache_hits / self.total_requests) * 100
    
    @property
    def miss_rate(self) -> float:
        """캐시 미스율 (%)"""
        return 100.0 - self.hit_rate

class IngredientCache:
    """성분 분석 결과 캐싱 시스템"""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600):
        """
        캐시 초기화
        
        Args:
            max_size: 최대 캐시 엔트리 수
            default_ttl: 기본 TTL (초)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = CacheStats()
        self._lock = threading.RLock()  # 스레드 안전성
        
        logger.info(f"IngredientCache 초기화: max_size={max_size}, default_ttl={default_ttl}s")
    
    def get(self, key: str) -> Optional[Any]:
        """
        캐시에서 데이터 조회
        
        Args:
            key: 캐시 키
            
        Returns:
            Optional[Any]: 캐시된 데이터 (없거나 만료된 경우 None)
        """
        with self._lock:
            self._stats.total_requests += 1
            
            if key not in self._cache:
                self._stats.cache_misses += 1
                logger.debug(f"캐시 미스: {key}")
                return None
            
            entry = self._cache[key]
            
            # 만료 확인
            if entry.is_expired:
                logger.debug(f"캐시 만료: {key} (생성 후 {entry.age_seconds}초)")
                del self._cache[key]
                self._stats.cache_misses += 1
                self._stats.expired_entries += 1
                return None
            
            # 히트 처리
            entry.last_accessed = datetime.now()
            entry.access_count += 1
            self._stats.cache_hits += 1
            
            # LRU 순서 업데이트
            self._cache.move_to_end(key)
            
            logger.debug(f"캐시 히트: {key} (접근 횟수: {entry.access_count})")
            return entry.data
    
    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """
        캐시에 데이터 저장
        
        Args:
            key: 캐시 키
            data: 저장할 데이터
            ttl: TTL (초, None이면 기본값 사용)
            
        Returns:
            bool: 저장 성공 여부
        """
        with self._lock:
            try:
                ttl = ttl or self.default_ttl
                
                # 기존 엔트리 업데이트 또는 새 엔트리 생성
                if key in self._cache:
                    # 기존 엔트리 업데이트
                    entry = self._cache[key]
                    entry.data = data
                    entry.created_at = datetime.now()
                    entry.last_accessed = datetime.now()
                    entry.ttl_seconds = ttl
                    self._cache.move_to_end(key)
                else:
                    # 새 엔트리 생성
                    entry = CacheEntry(
                        data=data,
                        created_at=datetime.now(),
                        last_accessed=datetime.now(),
                        ttl_seconds=ttl
                    )
                    self._cache[key] = entry
                
                # 캐시 크기 제한 확인
                self._evict_if_needed()
                
                logger.debug(f"캐시 저장: {key} (TTL: {ttl}s)")
                return True
                
            except Exception as e:
                logger.error(f"캐시 저장 오류: {key} - {e}")
                return False
    
    def delete(self, key: str) -> bool:
        """
        캐시에서 특정 키 삭제
        
        Args:
            key: 삭제할 캐시 키
            
        Returns:
            bool: 삭제 성공 여부
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"캐시 삭제: {key}")
                return True
            return False
    
    def clear(self) -> int:
        """
        모든 캐시 삭제
        
        Returns:
            int: 삭제된 엔트리 수
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"캐시 전체 삭제: {count}개 엔트리")
            return count
    
    def cleanup_expired(self) -> int:
        """
        만료된 캐시 엔트리 정리
        
        Returns:
            int: 정리된 엔트리 수
        """
        with self._lock:
            expired_keys = []
            
            for key, entry in self._cache.items():
                if entry.is_expired:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
                self._stats.expired_entries += 1
            
            if expired_keys:
                logger.info(f"만료된 캐시 정리: {len(expired_keys)}개 엔트리")
            
            return len(expired_keys)
    
    def get_stats(self) -> CacheStats:
        """캐시 통계 반환"""
        with self._lock:
            return CacheStats(
                total_requests=self._stats.total_requests,
                cache_hits=self._stats.cache_hits,
                cache_misses=self._stats.cache_misses,
                evictions=self._stats.evictions,
                expired_entries=self._stats.expired_entries
            )
    
    def get_cache_info(self) -> Dict[str, Any]:
        """캐시 상태 정보 반환"""
        with self._lock:
            stats = self.get_stats()
            
            # 메모리 사용량 추정 (대략적)
            memory_usage_mb = len(self._cache) * 0.01  # 엔트리당 약 10KB 추정
            
            return {
                'cache_size': len(self._cache),
                'max_size': self.max_size,
                'usage_percentage': (len(self._cache) / self.max_size) * 100,
                'hit_rate': stats.hit_rate,
                'miss_rate': stats.miss_rate,
                'total_requests': stats.total_requests,
                'cache_hits': stats.cache_hits,
                'cache_misses': stats.cache_misses,
                'evictions': stats.evictions,
                'expired_entries': stats.expired_entries,
                'estimated_memory_mb': round(memory_usage_mb, 2),
                'default_ttl': self.default_ttl
            }
    
    def get_top_accessed_keys(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        가장 많이 접근된 캐시 키 목록
        
        Args:
            limit: 반환할 키 개수
            
        Returns:
            List[Dict]: 접근 통계가 포함된 키 정보
        """
        with self._lock:
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: x[1].access_count,
                reverse=True
            )
            
            return [
                {
                    'key': key,
                    'access_count': entry.access_count,
                    'age_seconds': entry.age_seconds,
                    'last_accessed': entry.last_accessed.isoformat(),
                    'ttl_seconds': entry.ttl_seconds
                }
                for key, entry in sorted_entries[:limit]
            ]
    
    def _evict_if_needed(self):
        """필요시 캐시 엔트리 제거 (LRU)"""
        while len(self._cache) > self.max_size:
            # 가장 오래된 엔트리 제거 (LRU)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
            self._stats.evictions += 1
            logger.debug(f"캐시 제거 (LRU): {oldest_key}")

class ProductAnalysisCache:
    """제품 성분 분석 전용 캐시"""
    
    def __init__(self, max_size: int = 500, ttl: int = 7200):  # 2시간 TTL
        """
        제품 분석 캐시 초기화
        
        Args:
            max_size: 최대 캐시 크기
            ttl: TTL (초)
        """
        self.cache = IngredientCache(max_size=max_size, default_ttl=ttl)
        
    def get_product_analysis(self, product_id: int) -> Optional[ProductIngredientAnalysis]:
        """제품 성분 분석 결과 조회"""
        key = f"product_analysis_{product_id}"
        return self.cache.get(key)
    
    def set_product_analysis(
        self, 
        product_id: int, 
        analysis: ProductIngredientAnalysis,
        ttl: Optional[int] = None
    ) -> bool:
        """제품 성분 분석 결과 저장"""
        key = f"product_analysis_{product_id}"
        return self.cache.set(key, analysis, ttl)
    
    def invalidate_product(self, product_id: int) -> bool:
        """특정 제품의 캐시 무효화"""
        key = f"product_analysis_{product_id}"
        return self.cache.delete(key)
    
    def get_ingredient_effect(self, ingredient_id: int) -> Optional[Any]:
        """개별 성분 효과 분석 결과 조회"""
        key = f"ingredient_effect_{ingredient_id}"
        return self.cache.get(key)
    
    def set_ingredient_effect(
        self, 
        ingredient_id: int, 
        effect: Any,
        ttl: Optional[int] = None
    ) -> bool:
        """개별 성분 효과 분석 결과 저장"""
        key = f"ingredient_effect_{ingredient_id}"
        return self.cache.set(key, effect, ttl)

# 전역 캐시 인스턴스
_product_analysis_cache: Optional[ProductAnalysisCache] = None

def get_product_analysis_cache() -> ProductAnalysisCache:
    """제품 분석 캐시 인스턴스 반환 (싱글톤)"""
    global _product_analysis_cache
    if _product_analysis_cache is None:
        _product_analysis_cache = ProductAnalysisCache()
        logger.info("ProductAnalysisCache 인스턴스 생성")
    return _product_analysis_cache

def cleanup_all_caches():
    """모든 캐시 정리 (주기적 실행용)"""
    global _product_analysis_cache
    if _product_analysis_cache:
        expired_count = _product_analysis_cache.cache.cleanup_expired()
        logger.info(f"캐시 정리 완료: {expired_count}개 만료 엔트리 삭제")
        return expired_count
    return 0