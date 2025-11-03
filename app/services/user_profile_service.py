"""
사용자 프로필 서비스
Supabase에서 실제 사용자 데이터를 조회하여 경로 B 테스트에 활용
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from uuid import UUID
import logging
import json

from app.database.postgres_sync import get_postgres_sync_db
from app.models.personalization_models import (
    ProfileMatchResult, ProductIngredientAnalysis, 
    IngredientEffect, SafetyLevel, EffectType, MatchLevel
)

logger = logging.getLogger(__name__)

@dataclass
class UserProfileData:
    """사용자 프로필 데이터"""
    user_id: str
    age_group: Optional[str] = None
    skin_type: Optional[str] = None
    skin_concerns: List[str] = None
    allergies: List[str] = None
    preferences: Dict[str, Any] = None
    created_at: Optional[str] = None
    
    def __post_init__(self):
        if self.skin_concerns is None:
            self.skin_concerns = []
        if self.allergies is None:
            self.allergies = []
        if self.preferences is None:
            self.preferences = {}

class UserProfileService:
    """사용자 프로필 서비스"""
    
    def __init__(self):
        self.db = get_postgres_sync_db()
    
    def get_sample_users(self, limit: int = 10) -> List[UserProfileData]:
        """샘플 사용자 프로필 조회"""
        try:
            # Supabase에서 실제 사용자 데이터 조회
            query = """
            SELECT user_id, age_group, skin_type, skin_concerns, allergies, preferences, created_at
            FROM user_profiles 
            WHERE age_group IS NOT NULL 
            AND skin_type IS NOT NULL
            ORDER BY created_at DESC
            LIMIT %s
            """
            
            rows = self.db._execute_sync(query, (limit,))
            
            users = []
            for row in rows:
                # JSON 필드 파싱
                skin_concerns = []
                if row.get('skin_concerns'):
                    try:
                        skin_concerns = json.loads(row['skin_concerns']) if isinstance(row['skin_concerns'], str) else row['skin_concerns']
                    except (json.JSONDecodeError, TypeError):
                        skin_concerns = []
                
                allergies = []
                if row.get('allergies'):
                    try:
                        allergies = json.loads(row['allergies']) if isinstance(row['allergies'], str) else row['allergies']
                    except (json.JSONDecodeError, TypeError):
                        allergies = []
                
                preferences = {}
                if row.get('preferences'):
                    try:
                        preferences = json.loads(row['preferences']) if isinstance(row['preferences'], str) else row['preferences']
                    except (json.JSONDecodeError, TypeError):
                        preferences = {}
                
                user = UserProfileData(
                    user_id=str(row['user_id']),
                    age_group=row.get('age_group'),
                    skin_type=row.get('skin_type'),
                    skin_concerns=skin_concerns,
                    allergies=allergies,
                    preferences=preferences,
                    created_at=str(row.get('created_at', ''))
                )
                users.append(user)
            
            logger.info(f"실제 사용자 프로필 {len(users)}개 조회 완료")
            return users
            
        except Exception as e:
            logger.warning(f"실제 사용자 데이터 조회 실패: {e}")
            # 폴백: 목업 데이터 반환
            return self._get_fallback_users(limit)
    
    def _get_fallback_users(self, limit: int) -> List[UserProfileData]:
        """폴백용 목업 사용자 데이터"""
        mock_users = [
            UserProfileData(
                user_id="mock_user_001",
                age_group="20s",
                skin_type="dry",
                skin_concerns=["dryness", "sensitivity"],
                allergies=["fragrance"],
                preferences={"budget_range": "mid", "brand_preference": "korean"}
            ),
            UserProfileData(
                user_id="mock_user_002", 
                age_group="30s",
                skin_type="oily",
                skin_concerns=["acne", "large_pores"],
                allergies=[],
                preferences={"budget_range": "high", "ingredient_focus": "natural"}
            ),
            UserProfileData(
                user_id="mock_user_003",
                age_group="40s", 
                skin_type="combination",
                skin_concerns=["wrinkles", "pigmentation"],
                allergies=["alcohol", "parabens"],
                preferences={"budget_range": "premium", "anti_aging_focus": True}
            ),
            UserProfileData(
                user_id="mock_user_004",
                age_group="10s",
                skin_type="oily",
                skin_concerns=["acne", "blackheads"],
                allergies=[],
                preferences={"budget_range": "low", "simple_routine": True}
            ),
            UserProfileData(
                user_id="mock_user_005",
                age_group="50s",
                skin_type="dry",
                skin_concerns=["wrinkles", "sagging", "dryness"],
                allergies=["retinol", "strong_acids"],
                preferences={"budget_range": "premium", "gentle_products": True}
            ),
            UserProfileData(
                user_id="mock_user_006",
                age_group="30s",
                skin_type="sensitive",
                skin_concerns=["sensitivity", "redness", "irritation"],
                allergies=["fragrance", "alcohol", "essential_oils"],
                preferences={"budget_range": "mid", "hypoallergenic": True}
            ),
            UserProfileData(
                user_id="mock_user_007",
                age_group="20s",
                skin_type="normal",
                skin_concerns=["prevention", "hydration"],
                allergies=[],
                preferences={"budget_range": "mid", "daily_routine": True}
            ),
            UserProfileData(
                user_id="mock_user_008",
                age_group="40s",
                skin_type="dry",
                skin_concerns=["wrinkles", "dryness", "dullness"],
                allergies=["salicylic_acid"],
                preferences={"budget_range": "high", "luxury_brands": True}
            )
        ]
        
        logger.info(f"목업 사용자 프로필 {min(limit, len(mock_users))}개 반환")
        return mock_users[:limit]
    
    def get_user_by_id(self, user_id: str) -> Optional[UserProfileData]:
        """특정 사용자 프로필 조회"""
        try:
            query = """
            SELECT user_id, age_group, skin_type, skin_concerns, allergies, preferences, created_at
            FROM user_profiles 
            WHERE user_id = %s
            """
            
            rows = self.db._execute_sync(query, (user_id,))
            row = rows[0] if rows else None
            
            if row:
                # JSON 필드 파싱 (위와 동일한 로직)
                skin_concerns = []
                if row.get('skin_concerns'):
                    try:
                        skin_concerns = json.loads(row['skin_concerns']) if isinstance(row['skin_concerns'], str) else row['skin_concerns']
                    except (json.JSONDecodeError, TypeError):
                        skin_concerns = []
                
                allergies = []
                if row.get('allergies'):
                    try:
                        allergies = json.loads(row['allergies']) if isinstance(row['allergies'], str) else row['allergies']
                    except (json.JSONDecodeError, TypeError):
                        allergies = []
                
                preferences = {}
                if row.get('preferences'):
                    try:
                        preferences = json.loads(row['preferences']) if isinstance(row['preferences'], str) else row['preferences']
                    except (json.JSONDecodeError, TypeError):
                        preferences = {}
                
                return UserProfileData(
                    user_id=str(row['user_id']),
                    age_group=row.get('age_group'),
                    skin_type=row.get('skin_type'),
                    skin_concerns=skin_concerns,
                    allergies=allergies,
                    preferences=preferences,
                    created_at=str(row.get('created_at', ''))
                )
            
            return None
            
        except Exception as e:
            logger.error(f"사용자 프로필 조회 실패 (user_id: {user_id}): {e}")
            return None
    
    def create_profile_matches_from_users(
        self, 
        users: List[UserProfileData], 
        products: List, 
        intent_tags: List[str]
    ) -> Dict[int, ProfileMatchResult]:
        """실제 사용자 데이터 기반 프로필 매칭 결과 생성"""
        profile_matches = {}
        
        # 첫 번째 사용자의 프로필을 기준으로 모든 제품 평가
        if not users:
            return profile_matches
        
        primary_user = users[0]  # 첫 번째 사용자 사용
        
        for product in products:
            # 연령대 매칭 점수
            age_score = self._calculate_age_match_score(product, primary_user.age_group)
            
            # 피부타입 매칭 점수  
            skin_score = self._calculate_skin_type_match_score(product, primary_user.skin_type)
            
            # 선호도 매칭 점수
            preference_score = self._calculate_preference_match_score(
                product, primary_user.preferences, intent_tags
            )
            
            # 전체 점수 계산
            overall_score = (age_score * 0.4 + skin_score * 0.4 + preference_score * 0.2)
            
            # 매칭 이유 생성
            reasons = []
            if age_score > 75:
                reasons.append(f"{primary_user.age_group} 연령대에 적합")
            if skin_score > 75:
                reasons.append(f"{primary_user.skin_type} 피부타입에 맞음")
            if preference_score > 75:
                reasons.append("사용자 선호도 높음")
            
            # 알레르기 경고
            mismatch_reasons = []
            if primary_user.allergies:
                product_name_lower = product.name.lower()
                for allergy in primary_user.allergies:
                    if allergy.lower() in product_name_lower:
                        mismatch_reasons.append(f"알레르기 성분 주의: {allergy}")
                        overall_score -= 20  # 알레르기 성분 발견 시 큰 감점
            
            if not reasons:
                reasons.append("기본 매칭")
            
            profile_matches[product.product_id] = ProfileMatchResult(
                user_id=primary_user.user_id,
                product_id=product.product_id,
                age_match_score=age_score,
                skin_type_match_score=skin_score,
                preference_match_score=preference_score,
                overall_match_score=max(0, overall_score),  # 음수 방지
                match_reasons=reasons,
                mismatch_reasons=mismatch_reasons
            )
        
        return profile_matches
    
    def _calculate_age_match_score(self, product, age_group: str) -> float:
        """연령대 매칭 점수 계산"""
        if not age_group:
            return 70.0
        
        product_name = product.name.lower()
        product_tags = [tag.lower() for tag in (product.tags or [])]
        
        # 연령대별 키워드 매칭
        age_keywords = {
            "10s": {
                "positive": ["teen", "young", "mild", "gentle", "basic"],
                "negative": ["anti-aging", "wrinkle", "mature", "intensive"]
            },
            "20s": {
                "positive": ["young", "fresh", "daily", "prevention", "hydrating"],
                "negative": ["anti-aging", "intensive", "mature"]
            },
            "30s": {
                "positive": ["anti-aging", "prevention", "firming", "brightening"],
                "negative": ["teen", "basic"]
            },
            "40s": {
                "positive": ["anti-aging", "wrinkle", "firming", "intensive", "lifting"],
                "negative": ["teen", "young", "basic"]
            },
            "50s": {
                "positive": ["anti-aging", "wrinkle", "intensive", "nourishing", "regenerating"],
                "negative": ["teen", "young", "light"]
            }
        }
        
        keywords = age_keywords.get(age_group, {"positive": [], "negative": []})
        score = 70.0
        
        # 긍정적 키워드 매칭
        for keyword in keywords["positive"]:
            if any(keyword in tag for tag in product_tags) or keyword in product_name:
                score += 15
                break
        
        # 부정적 키워드 페널티
        for keyword in keywords["negative"]:
            if any(keyword in tag for tag in product_tags) or keyword in product_name:
                score -= 10
                break
        
        return max(30.0, min(95.0, score))
    
    def _calculate_skin_type_match_score(self, product, skin_type: str) -> float:
        """피부타입 매칭 점수 계산"""
        if not skin_type:
            return 70.0
        
        product_name = product.name.lower()
        product_tags = [tag.lower() for tag in (product.tags or [])]
        
        # 피부타입별 키워드 매칭
        skin_keywords = {
            "dry": {
                "positive": ["moistur", "hydrat", "nourish", "rich", "cream"],
                "negative": ["oil-control", "mattify", "sebum"]
            },
            "oily": {
                "positive": ["oil-control", "mattify", "sebum", "pore", "gel"],
                "negative": ["rich", "heavy", "nourish"]
            },
            "combination": {
                "positive": ["balance", "combination", "dual", "gel-cream"],
                "negative": ["extreme", "intensive"]
            },
            "sensitive": {
                "positive": ["gentle", "mild", "soothing", "calming", "hypoallergenic"],
                "negative": ["strong", "active", "exfoliat", "acid"]
            },
            "normal": {
                "positive": ["balance", "daily", "maintenance"],
                "negative": []
            }
        }
        
        keywords = skin_keywords.get(skin_type, {"positive": [], "negative": []})
        score = 70.0
        
        # 긍정적 키워드 매칭
        for keyword in keywords["positive"]:
            if any(keyword in tag for tag in product_tags) or keyword in product_name:
                score += 12
                break
        
        # 부정적 키워드 페널티
        for keyword in keywords["negative"]:
            if any(keyword in tag for tag in product_tags) or keyword in product_name:
                score -= 15
                break
        
        return max(30.0, min(95.0, score))
    
    def _calculate_preference_match_score(
        self, 
        product, 
        preferences: Dict[str, Any], 
        intent_tags: List[str]
    ) -> float:
        """선호도 매칭 점수 계산"""
        score = 70.0
        
        # 예산 범위 매칭 (가격 정보가 있다면)
        budget_range = preferences.get("budget_range", "mid")
        if budget_range == "premium" and "luxury" in product.name.lower():
            score += 10
        elif budget_range == "low" and any(brand in product.brand_name.lower() for brand in ["innisfree", "etude", "tonymoly"]):
            score += 8
        
        # 브랜드 선호도
        brand_pref = preferences.get("brand_preference", "")
        if brand_pref == "korean" and any(brand in product.brand_name.lower() for brand in ["innisfree", "etude", "laneige"]):
            score += 8
        
        # 성분 포커스
        ingredient_focus = preferences.get("ingredient_focus", "")
        if ingredient_focus == "natural" and any(keyword in product.name.lower() for keyword in ["natural", "organic", "botanical"]):
            score += 10
        
        # 의도 태그와의 매칭
        product_tags = [tag.lower() for tag in (product.tags or [])]
        intent_match_count = 0
        for intent in intent_tags:
            if intent.lower() in [tag.lower() for tag in product_tags]:
                intent_match_count += 1
        
        if intent_match_count > 0:
            score += intent_match_count * 5
        
        return max(30.0, min(95.0, score))
    
    def insert_mock_users_to_supabase(self) -> Dict[str, Any]:
        """목업 사용자 데이터를 Supabase에 추가"""
        try:
            # 목업 사용자 데이터 생성
            mock_users = [
                {
                    "user_id": "test_user_001",
                    "age_group": "20s",
                    "skin_type": "dry",
                    "skin_concerns": json.dumps(["dryness", "sensitivity"]),
                    "allergies": json.dumps(["fragrance"]),
                    "preferences": json.dumps({"budget_range": "mid", "brand_preference": "korean"})
                },
                {
                    "user_id": "test_user_002", 
                    "age_group": "30s",
                    "skin_type": "oily",
                    "skin_concerns": json.dumps(["acne", "large_pores"]),
                    "allergies": json.dumps([]),
                    "preferences": json.dumps({"budget_range": "high", "ingredient_focus": "natural"})
                },
                {
                    "user_id": "test_user_003",
                    "age_group": "40s", 
                    "skin_type": "combination",
                    "skin_concerns": json.dumps(["wrinkles", "pigmentation"]),
                    "allergies": json.dumps(["alcohol", "parabens"]),
                    "preferences": json.dumps({"budget_range": "premium", "anti_aging_focus": True})
                },
                {
                    "user_id": "test_user_004",
                    "age_group": "10s",
                    "skin_type": "oily",
                    "skin_concerns": json.dumps(["acne", "blackheads"]),
                    "allergies": json.dumps([]),
                    "preferences": json.dumps({"budget_range": "low", "simple_routine": True})
                },
                {
                    "user_id": "test_user_005",
                    "age_group": "50s",
                    "skin_type": "dry",
                    "skin_concerns": json.dumps(["wrinkles", "sagging", "dryness"]),
                    "allergies": json.dumps(["retinol", "strong_acids"]),
                    "preferences": json.dumps({"budget_range": "premium", "gentle_products": True})
                },
                {
                    "user_id": "test_user_006",
                    "age_group": "30s",
                    "skin_type": "sensitive",
                    "skin_concerns": json.dumps(["sensitivity", "redness", "irritation"]),
                    "allergies": json.dumps(["fragrance", "alcohol", "essential_oils"]),
                    "preferences": json.dumps({"budget_range": "mid", "hypoallergenic": True})
                },
                {
                    "user_id": "test_user_007",
                    "age_group": "20s",
                    "skin_type": "normal",
                    "skin_concerns": json.dumps(["prevention", "hydration"]),
                    "allergies": json.dumps([]),
                    "preferences": json.dumps({"budget_range": "mid", "daily_routine": True})
                },
                {
                    "user_id": "test_user_008",
                    "age_group": "40s",
                    "skin_type": "dry",
                    "skin_concerns": json.dumps(["wrinkles", "dryness", "dullness"]),
                    "allergies": json.dumps(["salicylic_acid"]),
                    "preferences": json.dumps({"budget_range": "high", "luxury_brands": True})
                }
            ]
            
            # 새 테이블이므로 기존 데이터 삭제 불필요
            logger.info("새 테이블에 목업 데이터 추가 시작")
            
            # 새 목업 사용자 추가
            insert_query = """
            INSERT INTO user_profiles (user_id, age_group, skin_type, skin_concerns, allergies, preferences, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """
            
            inserted_count = 0
            for user in mock_users:
                try:
                    self.db._execute_sync(insert_query, (
                        user["user_id"],
                        user["age_group"],
                        user["skin_type"],
                        user["skin_concerns"],
                        user["allergies"],
                        user["preferences"]
                    ))
                    inserted_count += 1
                except Exception as e:
                    logger.warning(f"사용자 {user['user_id']} 추가 실패: {e}")
            
            logger.info(f"목업 사용자 {inserted_count}개 Supabase에 추가 완료")
            
            return {
                "success": True,
                "inserted_count": inserted_count,
                "total_mock_users": len(mock_users),
                "message": f"{inserted_count}개의 목업 사용자가 Supabase에 추가되었습니다"
            }
            
        except Exception as e:
            logger.error(f"목업 사용자 추가 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "목업 사용자 추가에 실패했습니다"
            }
    
    def check_user_table_structure(self) -> Dict[str, Any]:
        """사용자 테이블 구조 확인"""
        try:
            # 테이블 구조 조회
            structure_query = """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'user_profiles'
            ORDER BY ordinal_position
            """
            
            columns = self.db._execute_sync(structure_query)
            
            # 샘플 데이터 조회
            sample_query = "SELECT * FROM user_profiles LIMIT 3"
            sample_data = self.db._execute_sync(sample_query)
            
            # 테이블 존재 여부 확인
            table_exists_query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'user_profiles'
            )
            """
            table_exists_result = self.db._execute_sync(table_exists_query)
            table_exists = table_exists_result[0] if table_exists_result else None
            
            return {
                "table_exists": table_exists.get("exists", False) if table_exists else False,
                "columns": columns,
                "sample_data": sample_data,
                "total_records": len(sample_data)
            }
            
        except Exception as e:
            logger.error(f"테이블 구조 확인 실패: {e}")
            return {
                "table_exists": False,
                "error": str(e),
                "message": "테이블 구조 확인에 실패했습니다"
            }
    
    def create_user_profiles_table(self) -> Dict[str, Any]:
        """사용자 프로필 테이블 생성 (없는 경우)"""
        try:
            # 기존 테이블 삭제 (테스트용)
            drop_table_query = "DROP TABLE IF EXISTS user_profiles CASCADE"
            self.db._execute_sync(drop_table_query)
            logger.info("기존 user_profiles 테이블 삭제 완료")
            
            create_table_query = """
            CREATE TABLE user_profiles (
                id SERIAL PRIMARY KEY,
                user_id TEXT UNIQUE NOT NULL,
                age_group VARCHAR(10),
                skin_type VARCHAR(20),
                skin_concerns JSONB,
                allergies JSONB,
                preferences JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
            
            self.db._execute_sync(create_table_query)
            
            # 인덱스 생성
            index_queries = [
                "CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id)",
                "CREATE INDEX IF NOT EXISTS idx_user_profiles_age_group ON user_profiles(age_group)",
                "CREATE INDEX IF NOT EXISTS idx_user_profiles_skin_type ON user_profiles(skin_type)"
            ]
            
            for index_query in index_queries:
                self.db._execute_sync(index_query)
            
            logger.info("user_profiles 테이블 및 인덱스 생성 완료")
            
            return {
                "success": True,
                "message": "user_profiles 테이블이 성공적으로 생성되었습니다"
            }
            
        except Exception as e:
            logger.error(f"테이블 생성 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "테이블 생성에 실패했습니다"
            }

    def get_user_statistics(self) -> Dict[str, Any]:
        """사용자 통계 정보"""
        try:
            stats_query = """
            SELECT 
                COUNT(*) as total_users,
                COUNT(CASE WHEN age_group IS NOT NULL THEN 1 END) as users_with_age,
                COUNT(CASE WHEN skin_type IS NOT NULL THEN 1 END) as users_with_skin_type,
                COUNT(CASE WHEN skin_concerns IS NOT NULL THEN 1 END) as users_with_concerns
            FROM user_profiles
            """
            
            result_rows = self.db._execute_sync(stats_query)
            result = result_rows[0] if result_rows else {}
            
            return {
                "total_users": result.get("total_users", 0),
                "users_with_age": result.get("users_with_age", 0), 
                "users_with_skin_type": result.get("users_with_skin_type", 0),
                "users_with_concerns": result.get("users_with_concerns", 0),
                "data_completeness": {
                    "age_group": f"{(result.get('users_with_age', 0) / max(result.get('total_users', 1), 1)) * 100:.1f}%",
                    "skin_type": f"{(result.get('users_with_skin_type', 0) / max(result.get('total_users', 1), 1)) * 100:.1f}%",
                    "skin_concerns": f"{(result.get('users_with_concerns', 0) / max(result.get('total_users', 1), 1)) * 100:.1f}%"
                }
            }
            
        except Exception as e:
            logger.error(f"사용자 통계 조회 실패: {e}")
            return {
                "total_users": 0,
                "users_with_age": 0,
                "users_with_skin_type": 0, 
                "users_with_concerns": 0,
                "data_completeness": {
                    "age_group": "0.0%",
                    "skin_type": "0.0%", 
                    "skin_concerns": "0.0%"
                },
                "error": str(e)
            }