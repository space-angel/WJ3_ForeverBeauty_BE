"""
PostgreSQL 기반 사용자 서비스
UUID 기반 사용자 관리 및 JSONB 최적화 선호도 관리
"""

import logging
from typing import List, Dict, Optional, Any
from uuid import UUID, uuid4
from datetime import datetime

from app.database.postgres_db import get_postgres_db
from app.models.postgres_models import (
    User, UserProfile, UserPreference, CompleteUserProfile,
    RecommendationHistory, UserFeedback
)

logger = logging.getLogger(__name__)

class UserService:
    """사용자 관리 서비스"""
    
    def __init__(self):
        self.db = get_postgres_db()
    
    # === 사용자 기본 관리 ===
    
    async def create_user(self, email: Optional[str] = None, name: Optional[str] = None) -> User:
        """새 사용자 생성"""
        user_id = uuid4()
        
        query = """
            INSERT INTO users (user_id, email, name, created_at, updated_at)
            VALUES ($1, $2, $3, NOW(), NOW())
            RETURNING user_id, email, name, created_at, updated_at
        """
        
        try:
            row = await self.db.execute_single(query, user_id, email, name)
            if not row:
                raise Exception("사용자 생성 실패")
            
            user = User.from_db_row(row)
            logger.info(f"새 사용자 생성: {user_id}")
            return user
            
        except Exception as e:
            logger.error(f"사용자 생성 오류: {e}")
            raise
    
    async def get_user(self, user_id: UUID) -> Optional[User]:
        """사용자 조회"""
        query = """
            SELECT user_id, email, name, created_at, updated_at
            FROM users
            WHERE user_id = $1
        """
        
        try:
            row = await self.db.execute_single(query, user_id)
            return User.from_db_row(row) if row else None
        except Exception as e:
            logger.error(f"사용자 조회 오류: {e}")
            return None
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """이메일로 사용자 조회"""
        query = """
            SELECT user_id, email, name, created_at, updated_at
            FROM users
            WHERE email = $1
        """
        
        try:
            row = await self.db.execute_single(query, email)
            return User.from_db_row(row) if row else None
        except Exception as e:
            logger.error(f"이메일로 사용자 조회 오류: {e}")
            return None
    
    async def update_user(self, user_id: UUID, email: Optional[str] = None, name: Optional[str] = None) -> Optional[User]:
        """사용자 정보 수정"""
        # 동적 쿼리 생성
        updates = []
        params = []
        param_count = 1
        
        if email is not None:
            updates.append(f"email = ${param_count}")
            params.append(email)
            param_count += 1
        
        if name is not None:
            updates.append(f"name = ${param_count}")
            params.append(name)
            param_count += 1
        
        if not updates:
            return await self.get_user(user_id)
        
        updates.append(f"updated_at = NOW()")
        params.append(user_id)
        
        query = f"""
            UPDATE users
            SET {', '.join(updates)}
            WHERE user_id = ${param_count}
            RETURNING user_id, email, name, created_at, updated_at
        """
        
        try:
            row = await self.db.execute_single(query, *params)
            if row:
                logger.info(f"사용자 정보 수정: {user_id}")
                return User.from_db_row(row)
            return None
        except Exception as e:
            logger.error(f"사용자 수정 오류: {e}")
            return None
    
    async def delete_user(self, user_id: UUID) -> bool:
        """사용자 삭제 (CASCADE로 관련 데이터 모두 삭제)"""
        query = "DELETE FROM users WHERE user_id = $1"
        
        try:
            result = await self.db.execute_command(query, user_id)
            success = "DELETE 1" in result
            if success:
                logger.info(f"사용자 삭제: {user_id}")
            return success
        except Exception as e:
            logger.error(f"사용자 삭제 오류: {e}")
            return False
    
    # === 사용자 프로필 관리 ===
    
    async def create_or_update_profile(
        self,
        user_id: UUID,
        age_group: Optional[str] = None,
        skin_type: Optional[str] = None,
        gender: Optional[str] = None,
        skin_concerns: Optional[List[str]] = None
    ) -> Optional[UserProfile]:
        """사용자 프로필 생성 또는 수정"""
        
        # JSONB 데이터 준비
        skin_concerns_json = skin_concerns or []
        
        query = """
            INSERT INTO user_profiles (user_id, age_group, skin_type, gender, skin_concerns, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW(), NOW())
            ON CONFLICT (user_id) DO UPDATE SET
                age_group = COALESCE(EXCLUDED.age_group, user_profiles.age_group),
                skin_type = COALESCE(EXCLUDED.skin_type, user_profiles.skin_type),
                gender = COALESCE(EXCLUDED.gender, user_profiles.gender),
                skin_concerns = EXCLUDED.skin_concerns,
                updated_at = NOW()
            RETURNING user_id, age_group, skin_type, gender, skin_concerns, created_at, updated_at
        """
        
        try:
            row = await self.db.execute_single(
                query, user_id, age_group, skin_type, gender, skin_concerns_json
            )
            if row:
                logger.info(f"사용자 프로필 업데이트: {user_id}")
                return UserProfile.from_db_row(row)
            return None
        except Exception as e:
            logger.error(f"프로필 생성/수정 오류: {e}")
            return None
    
    async def get_user_profile(self, user_id: UUID) -> Optional[UserProfile]:
        """사용자 프로필 조회"""
        query = """
            SELECT user_id, age_group, skin_type, gender, skin_concerns, created_at, updated_at
            FROM user_profiles
            WHERE user_id = $1
        """
        
        try:
            row = await self.db.execute_single(query, user_id)
            return UserProfile.from_db_row(row) if row else None
        except Exception as e:
            logger.error(f"프로필 조회 오류: {e}")
            return None
    
    # === 사용자 선호도 관리 ===
    
    async def add_preference(
        self,
        user_id: UUID,
        preference_type: str,
        preference_value: str,
        is_preferred: bool = True,
        confidence_score: float = 1.0
    ) -> bool:
        """사용자 선호도 추가"""
        query = """
            INSERT INTO user_preferences (user_id, preference_type, preference_value, is_preferred, confidence_score, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            ON CONFLICT (user_id, preference_type, preference_value) DO UPDATE SET
                is_preferred = EXCLUDED.is_preferred,
                confidence_score = EXCLUDED.confidence_score,
                created_at = NOW()
        """
        
        try:
            await self.db.execute_command(query, user_id, preference_type, preference_value, is_preferred, confidence_score)
            logger.info(f"선호도 추가: {user_id} - {preference_type}:{preference_value}")
            return True
        except Exception as e:
            logger.error(f"선호도 추가 오류: {e}")
            return False
    
    async def get_user_preferences(self, user_id: UUID, preference_type: Optional[str] = None) -> List[UserPreference]:
        """사용자 선호도 조회"""
        if preference_type:
            query = """
                SELECT user_id, preference_type, preference_value, is_preferred, confidence_score, created_at
                FROM user_preferences
                WHERE user_id = $1 AND preference_type = $2
                ORDER BY confidence_score DESC, created_at DESC
            """
            params = [user_id, preference_type]
        else:
            query = """
                SELECT user_id, preference_type, preference_value, is_preferred, confidence_score, created_at
                FROM user_preferences
                WHERE user_id = $1
                ORDER BY preference_type, confidence_score DESC, created_at DESC
            """
            params = [user_id]
        
        try:
            rows = await self.db.execute_query(query, *params)
            return [UserPreference.from_db_row(row) for row in rows]
        except Exception as e:
            logger.error(f"선호도 조회 오류: {e}")
            return []
    
    async def remove_preference(self, user_id: UUID, preference_type: str, preference_value: str) -> bool:
        """사용자 선호도 삭제"""
        query = """
            DELETE FROM user_preferences
            WHERE user_id = $1 AND preference_type = $2 AND preference_value = $3
        """
        
        try:
            result = await self.db.execute_command(query, user_id, preference_type, preference_value)
            success = "DELETE 1" in result
            if success:
                logger.info(f"선호도 삭제: {user_id} - {preference_type}:{preference_value}")
            return success
        except Exception as e:
            logger.error(f"선호도 삭제 오류: {e}")
            return False
    
    async def batch_update_preferences(
        self,
        user_id: UUID,
        preferences: List[Dict[str, Any]]
    ) -> bool:
        """선호도 배치 업데이트"""
        
        # 기존 선호도 삭제
        delete_query = "DELETE FROM user_preferences WHERE user_id = $1"
        
        # 새 선호도 삽입
        insert_query = """
            INSERT INTO user_preferences (user_id, preference_type, preference_value, is_preferred, confidence_score, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
        """
        
        try:
            async with self.db.get_connection() as conn:
                # 트랜잭션 시작
                async with conn.transaction():
                    # 기존 데이터 삭제
                    await conn.execute(delete_query, user_id)
                    
                    # 새 데이터 삽입
                    for pref in preferences:
                        await conn.execute(
                            insert_query,
                            user_id,
                            pref['preference_type'],
                            pref['preference_value'],
                            pref.get('is_preferred', True),
                            pref.get('confidence_score', 1.0)
                        )
            
            logger.info(f"선호도 배치 업데이트: {user_id} - {len(preferences)}개")
            return True
            
        except Exception as e:
            logger.error(f"선호도 배치 업데이트 오류: {e}")
            return False
    
    # === 완전한 사용자 프로필 조회 (최적화된 조인) ===
    
    async def get_complete_user_profile(self, user_id: UUID) -> Optional[CompleteUserProfile]:
        """사용자 완전 프로필 조회 (한 번의 쿼리로 모든 데이터)"""
        query = """
            SELECT 
                u.user_id, u.email, u.name, u.created_at as user_created_at, u.updated_at as user_updated_at,
                up.age_group, up.skin_type, up.gender, up.skin_concerns,
                up.created_at as profile_created_at, up.updated_at as profile_updated_at,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'preference_type', pref.preference_type,
                            'preference_value', pref.preference_value,
                            'is_preferred', pref.is_preferred,
                            'confidence_score', pref.confidence_score,
                            'created_at', pref.created_at
                        ) ORDER BY pref.preference_type, pref.confidence_score DESC
                    ) FILTER (WHERE pref.user_id IS NOT NULL), 
                    '[]'::json
                ) as preferences
            FROM users u
            LEFT JOIN user_profiles up ON u.user_id = up.user_id
            LEFT JOIN user_preferences pref ON u.user_id = pref.user_id
            WHERE u.user_id = $1
            GROUP BY u.user_id, u.email, u.name, u.created_at, u.updated_at,
                     up.age_group, up.skin_type, up.gender, up.skin_concerns,
                     up.created_at, up.updated_at
        """
        
        try:
            row = await self.db.execute_single(query, user_id)
            if not row:
                return None
            
            # User 객체 생성
            user = User(
                user_id=row['user_id'],
                email=row['email'],
                name=row['name'],
                created_at=row['user_created_at'],
                updated_at=row['user_updated_at']
            )
            
            # UserProfile 객체 생성 (있는 경우)
            profile = None
            if row['age_group'] or row['skin_type']:
                profile = UserProfile(
                    user_id=row['user_id'],
                    age_group=row['age_group'],
                    skin_type=row['skin_type'],
                    gender=row['gender'],
                    skin_concerns=row['skin_concerns'] or [],
                    created_at=row['profile_created_at'],
                    updated_at=row['profile_updated_at']
                )
            
            # UserPreference 객체들 생성
            preferences = []
            if row['preferences']:
                for pref_data in row['preferences']:
                    preferences.append(UserPreference(
                        user_id=user_id,
                        preference_type=pref_data['preference_type'],
                        preference_value=pref_data['preference_value'],
                        is_preferred=pref_data['is_preferred'],
                        confidence_score=pref_data['confidence_score'],
                        created_at=pref_data['created_at']
                    ))
            
            return CompleteUserProfile(
                user=user,
                profile=profile,
                preferences=preferences
            )
            
        except Exception as e:
            logger.error(f"완전 프로필 조회 오류: {e}")
            return None
    
    # === 추천 이력 관리 ===
    
    async def save_recommendation_history(
        self,
        user_id: Optional[UUID],
        session_id: Optional[str],
        intent_tags: List[str],
        recommended_products: List[Dict[str, Any]],
        execution_time_ms: float
    ) -> Optional[int]:
        """추천 이력 저장"""
        query = """
            INSERT INTO recommendation_history (user_id, session_id, intent_tags, recommended_products, execution_time_ms, created_at)
            VALUES ($1, $2, $3, $4, $5, NOW())
            RETURNING id
        """
        
        try:
            result = await self.db.execute_scalar(
                query, user_id, session_id, intent_tags, recommended_products, execution_time_ms
            )
            logger.info(f"추천 이력 저장: {result}")
            return result
        except Exception as e:
            logger.error(f"추천 이력 저장 오류: {e}")
            return None
    
    async def get_recommendation_history(
        self,
        user_id: Optional[UUID] = None,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[RecommendationHistory]:
        """추천 이력 조회"""
        if user_id:
            query = """
                SELECT id, user_id, session_id, intent_tags, recommended_products, execution_time_ms, created_at
                FROM recommendation_history
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            params = [user_id, limit]
        elif session_id:
            query = """
                SELECT id, user_id, session_id, intent_tags, recommended_products, execution_time_ms, created_at
                FROM recommendation_history
                WHERE session_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """
            params = [session_id, limit]
        else:
            return []
        
        try:
            rows = await self.db.execute_query(query, *params)
            return [RecommendationHistory.from_db_row(row) for row in rows]
        except Exception as e:
            logger.error(f"추천 이력 조회 오류: {e}")
            return []
    
    # === 사용자 피드백 관리 ===
    
    async def save_user_feedback(
        self,
        user_id: UUID,
        product_id: int,
        feedback_type: str,
        rating: Optional[int] = None
    ) -> Optional[int]:
        """사용자 피드백 저장"""
        query = """
            INSERT INTO user_feedback (user_id, product_id, feedback_type, rating, created_at)
            VALUES ($1, $2, $3, $4, NOW())
            RETURNING id
        """
        
        try:
            result = await self.db.execute_scalar(query, user_id, product_id, feedback_type, rating)
            logger.info(f"피드백 저장: {user_id} - {product_id} - {feedback_type}")
            return result
        except Exception as e:
            logger.error(f"피드백 저장 오류: {e}")
            return None
    
    async def get_user_feedback(self, user_id: UUID, limit: int = 50) -> List[UserFeedback]:
        """사용자 피드백 조회"""
        query = """
            SELECT id, user_id, product_id, feedback_type, rating, created_at
            FROM user_feedback
            WHERE user_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        """
        
        try:
            rows = await self.db.execute_query(query, user_id, limit)
            return [UserFeedback.from_db_row(row) for row in rows]
        except Exception as e:
            logger.error(f"피드백 조회 오류: {e}")
            return []
    
    # === 통계 및 분석 ===
    
    async def get_user_statistics(self) -> Dict[str, Any]:
        """사용자 통계 조회"""
        queries = {
            'total_users': "SELECT COUNT(*) FROM users",
            'users_with_profiles': "SELECT COUNT(*) FROM user_profiles",
            'total_preferences': "SELECT COUNT(*) FROM user_preferences",
            'total_recommendations': "SELECT COUNT(*) FROM recommendation_history",
            'total_feedback': "SELECT COUNT(*) FROM user_feedback"
        }
        
        stats = {}
        
        try:
            for key, query in queries.items():
                stats[key] = await self.db.execute_scalar(query)
            
            # 추가 통계
            stats['avg_preferences_per_user'] = (
                stats['total_preferences'] / stats['users_with_profiles'] 
                if stats['users_with_profiles'] > 0 else 0
            )
            
            return stats
            
        except Exception as e:
            logger.error(f"사용자 통계 조회 오류: {e}")
            return {}
    
    async def get_preference_distribution(self) -> Dict[str, Dict[str, int]]:
        """선호도 분포 조회"""
        query = """
            SELECT preference_type, preference_value, COUNT(*) as count
            FROM user_preferences
            WHERE is_preferred = true
            GROUP BY preference_type, preference_value
            ORDER BY preference_type, count DESC
        """
        
        try:
            rows = await self.db.execute_query(query)
            
            distribution = {}
            for row in rows:
                pref_type = row['preference_type']
                if pref_type not in distribution:
                    distribution[pref_type] = {}
                distribution[pref_type][row['preference_value']] = row['count']
            
            return distribution
            
        except Exception as e:
            logger.error(f"선호도 분포 조회 오류: {e}")
            return {}