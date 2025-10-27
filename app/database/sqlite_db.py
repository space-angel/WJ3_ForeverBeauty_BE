"""
SQLite 데이터베이스 연결 관리
cosmetics.db 파일 연결
"""
import sqlite3
import os
from typing import List, Dict, Any, Optional

class SQLiteDB:
    """SQLite 데이터베이스 연결 클래스"""
    
    def __init__(self, db_path: str = "cosmetics.db"):
        """
        SQLite 데이터베이스 초기화
        
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self._connection = None
    
    def get_connection(self) -> sqlite3.Connection:
        """데이터베이스 연결 반환"""
        if self._connection is None:
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(f"SQLite 데이터베이스 파일을 찾을 수 없습니다: {self.db_path}")
            
            self._connection = sqlite3.connect(self.db_path)
            self._connection.row_factory = sqlite3.Row  # 딕셔너리 형태로 결과 반환
        
        return self._connection
    
    def test_connection(self) -> bool:
        """데이터베이스 연결 테스트"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            return True
        except Exception as e:
            print(f"SQLite 연결 테스트 실패: {e}")
            return False
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """쿼리 실행 및 결과 반환"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            # SELECT 쿼리인 경우 결과 반환
            if query.strip().upper().startswith('SELECT'):
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            else:
                conn.commit()
                return []
                
        except Exception as e:
            print(f"쿼리 실행 오류: {e}")
            print(f"쿼리: {query}")
            print(f"파라미터: {params}")
            return []
    
    def execute_single(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """단일 결과 쿼리 실행"""
        results = self.execute_query(query, params)
        return results[0] if results else None
    
    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """테이블 정보 조회"""
        return self.execute_query(f"PRAGMA table_info({table_name})")
    
    def get_table_names(self) -> List[str]:
        """모든 테이블 이름 조회"""
        results = self.execute_query(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        return [row['name'] for row in results]
    
    def close(self):
        """연결 종료"""
        if self._connection:
            self._connection.close()
            self._connection = None

def get_sqlite_db() -> SQLiteDB:
    """SQLite 데이터베이스 인스턴스 반환"""
    return SQLiteDB()