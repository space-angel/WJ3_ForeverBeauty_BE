"""
공유 유틸리티 함수들
재사용 가능한 함수들을 중앙 집중 관리
"""
from typing import Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def calculate_execution_time_ms(start_time: datetime, end_time: Optional[datetime] = None) -> float:
    """
    실행 시간을 밀리초로 계산
    
    Args:
        start_time: 시작 시간
        end_time: 종료 시간 (None이면 현재 시간 사용)
    
    Returns:
        실행 시간 (밀리초)
    
    Example:
        >>> start = datetime.now()
        >>> # ... 작업 수행
        >>> execution_ms = calculate_execution_time_ms(start)
        >>> print(f"실행 시간: {execution_ms:.2f}ms")
    """
    if end_time is None:
        end_time = datetime.now()
    
    return (end_time.timestamp() - start_time.timestamp()) * 1000

def safe_dict_get(data: Dict[str, Any], key: str, default: Any = None) -> Any:
    """
    안전한 딕셔너리 값 조회
    
    Args:
        data: 딕셔너리
        key: 키
        default: 기본값
    
    Returns:
        값 또는 기본값
    
    Example:
        >>> data = {'name': 'test', 'count': 5}
        >>> name = safe_dict_get(data, 'name', 'unknown')
        >>> age = safe_dict_get(data, 'age', 0)
    """
    try:
        return data.get(key, default)
    except (AttributeError, TypeError):
        logger.warning(f"딕셔너리 접근 실패: {key}")
        return default

def format_korean_message(template: str, **kwargs) -> str:
    """
    한국어 메시지 포맷팅
    
    Args:
        template: 메시지 템플릿
        **kwargs: 포맷팅 변수들
    
    Returns:
        포맷팅된 메시지
    
    Example:
        >>> msg = format_korean_message("제품 {count}개를 찾았습니다.", count=5)
        >>> print(msg)  # "제품 5개를 찾았습니다."
    """
    try:
        return template.format(**kwargs)
    except (KeyError, ValueError) as e:
        logger.error(f"메시지 포맷팅 실패: {e}")
        return template

# 간단한 테스트
if __name__ == "__main__":
    # 실행 시간 계산 테스트
    import time
    start = datetime.now()
    time.sleep(0.1)  # 100ms 대기
    exec_time = calculate_execution_time_ms(start)
    print(f"테스트 실행 시간: {exec_time:.2f}ms (예상: ~100ms)")
    
    # 안전한 딕셔너리 접근 테스트
    test_data = {'name': '테스트', 'count': 10}
    name = safe_dict_get(test_data, 'name', '알 수 없음')
    age = safe_dict_get(test_data, 'age', 0)
    print(f"이름: {name}, 나이: {age}")
    
    # 메시지 포맷팅 테스트
    msg = format_korean_message("총 {total}개 중 {success}개 성공", total=100, success=95)
    print(f"포맷팅 결과: {msg}")