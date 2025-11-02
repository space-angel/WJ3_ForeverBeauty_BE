-- PostgreSQL 통합 스키마 생성 스크립트
-- 기존 SQLite 테이블 + 새로운 사용자 관련 테이블

-- UUID 확장 활성화 (PostgreSQL 13+ 기본 포함)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 기존 제품 테이블 (SQLite에서 마이그레이션)
CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    brand_name TEXT NOT NULL,
    category_code TEXT NOT NULL,
    category_name TEXT NOT NULL,
    primary_attr TEXT,
    tags JSONB DEFAULT '[]'::jsonb,
    image_url TEXT,
    sub_product_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 기존 성분 테이블 (SQLite에서 마이그레이션)
CREATE TABLE IF NOT EXISTS ingredients (
    ingredient_id SERIAL PRIMARY KEY,
    korean TEXT NOT NULL,
    english TEXT,
    ewg_grade TEXT CHECK (ewg_grade IN ('1','1_2','2','2_3','3','4','5','6','7','8','9','10','unknown')),
    is_allergy BOOLEAN DEFAULT FALSE,
    is_twenty BOOLEAN DEFAULT FALSE,
    skin_type_code TEXT,
    skin_good TEXT,
    skin_bad TEXT,
    limitation TEXT,
    forbidden TEXT,
    purposes JSONB DEFAULT '[]'::jsonb,
    tags JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 기존 제품-성분 관계 테이블 (SQLite에서 마이그레이션)
CREATE TABLE IF NOT EXISTS product_ingredients (
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(ingredient_id) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY (product_id, ingredient_id),
    UNIQUE (product_id, ordinal)
);

-- 기존 상품 테이블 (SQLite에서 마이그레이션)
CREATE TABLE IF NOT EXISTS goods (
    goods_id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    price DECIMAL(12,2) NOT NULL CHECK (price >= 0),
    capacity TEXT,
    sale_status TEXT NOT NULL DEFAULT 'SELNG' CHECK (sale_status IN ('SELNG', 'SOLDOUT', 'DISCONTINUED')),
    partner_name TEXT,
    thumbnail_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 기존 제품 메트릭 테이블 (SQLite에서 마이그레이션)
CREATE TABLE IF NOT EXISTS product_metrics (
    product_id INTEGER PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
    rating_avg DECIMAL(4,2) CHECK (rating_avg >= 0 AND rating_avg <= 5),
    review_count INTEGER DEFAULT 0 CHECK (review_count >= 0),
    category_overall_rank INTEGER CHECK (category_overall_rank > 0),
    by_attribute_rank INTEGER CHECK (by_attribute_rank > 0),
    rank_attribute_name TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 기존 리뷰 토픽 테이블 (SQLite에서 마이그레이션)
CREATE TABLE IF NOT EXISTS review_topics (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    sentiment TEXT NOT NULL CHECK (sentiment IN ('POS','NEG')),
    name TEXT NOT NULL,
    sentence TEXT,
    review_count INTEGER DEFAULT 0 CHECK (review_count >= 0),
    score DECIMAL(10,3) DEFAULT 0 CHECK (score >= 0),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (product_id, sentiment, name)
);

-- 사용자 기본 정보 (신규)
CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE,
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 사용자 개인화 프로필 (신규)
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    age_group TEXT CHECK (age_group IN ('10s','20s','30s','40s','50s')),
    skin_type TEXT CHECK (skin_type IN ('dry','oily','sensitive','combination')),
    gender TEXT CHECK (gender IN ('male','female','other')),
    skin_concerns JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 사용자 선호도 (신규)
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    preference_type TEXT CHECK (preference_type IN ('brand','ingredient','category')),
    preference_value TEXT,
    is_preferred BOOLEAN DEFAULT TRUE,
    confidence_score FLOAT DEFAULT 1.0 CHECK (confidence_score >= 0 AND confidence_score <= 1.0),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, preference_type, preference_value)
);

-- 추천 이력 (신규)
CREATE TABLE IF NOT EXISTS recommendation_history (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    session_id TEXT,
    intent_tags JSONB,
    recommended_products JSONB,
    execution_time_ms FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 사용자 피드백 (신규)
CREATE TABLE IF NOT EXISTS user_feedback (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(user_id) ON DELETE CASCADE,
    product_id INTEGER REFERENCES products(product_id) ON DELETE CASCADE,
    feedback_type TEXT CHECK (feedback_type IN ('like','dislike','purchase','view')),
    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 성능 최적화 인덱스 생성

-- 기존 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_products_brand_category ON products(brand_name, category_code);
CREATE INDEX IF NOT EXISTS idx_products_tags ON products USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_products_primary_attr ON products(primary_attr);

CREATE INDEX IF NOT EXISTS idx_ingredients_korean ON ingredients(korean);
CREATE INDEX IF NOT EXISTS idx_ingredients_ewg_grade ON ingredients(ewg_grade);
CREATE INDEX IF NOT EXISTS idx_ingredients_tags ON ingredients USING GIN(tags);
CREATE INDEX IF NOT EXISTS idx_ingredients_purposes ON ingredients USING GIN(purposes);

CREATE INDEX IF NOT EXISTS idx_product_ingredients_product ON product_ingredients(product_id);
CREATE INDEX IF NOT EXISTS idx_product_ingredients_ingredient ON product_ingredients(ingredient_id);
CREATE INDEX IF NOT EXISTS idx_product_ingredients_ordinal ON product_ingredients(product_id, ordinal);

CREATE INDEX IF NOT EXISTS idx_goods_product ON goods(product_id);
CREATE INDEX IF NOT EXISTS idx_goods_price ON goods(price);
CREATE INDEX IF NOT EXISTS idx_goods_sale_status ON goods(sale_status);

CREATE INDEX IF NOT EXISTS idx_metrics_rating ON product_metrics(rating_avg DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_review_count ON product_metrics(review_count DESC);

CREATE INDEX IF NOT EXISTS idx_review_topics_product_sentiment ON review_topics(product_id, sentiment);
CREATE INDEX IF NOT EXISTS idx_review_topics_score ON review_topics(product_id, sentiment, score DESC);

-- 새로운 사용자 테이블 인덱스
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

CREATE INDEX IF NOT EXISTS idx_user_profiles_age_skin ON user_profiles(age_group, skin_type);
CREATE INDEX IF NOT EXISTS idx_user_profiles_skin_concerns ON user_profiles USING GIN(skin_concerns);

CREATE INDEX IF NOT EXISTS idx_user_preferences_user ON user_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_user_preferences_type_value ON user_preferences(preference_type, preference_value);

CREATE INDEX IF NOT EXISTS idx_recommendation_history_user ON recommendation_history(user_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_history_session ON recommendation_history(session_id);
CREATE INDEX IF NOT EXISTS idx_recommendation_history_created ON recommendation_history(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_user_feedback_user_product ON user_feedback(user_id, product_id);
CREATE INDEX IF NOT EXISTS idx_user_feedback_type ON user_feedback(feedback_type);
CREATE INDEX IF NOT EXISTS idx_user_feedback_created ON user_feedback(created_at DESC);

-- 트리거 함수: updated_at 자동 업데이트
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- updated_at 트리거 생성
CREATE TRIGGER update_products_updated_at BEFORE UPDATE ON products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_ingredients_updated_at BEFORE UPDATE ON ingredients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_goods_updated_at BEFORE UPDATE ON goods
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_product_metrics_updated_at BEFORE UPDATE ON product_metrics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_review_topics_updated_at BEFORE UPDATE ON review_topics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE ON user_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 스키마 생성 완료 메시지
DO $$
BEGIN
    RAISE NOTICE 'PostgreSQL 통합 스키마 생성이 완료되었습니다.';
    RAISE NOTICE '- 기존 테이블: products, ingredients, product_ingredients, goods, product_metrics, review_topics';
    RAISE NOTICE '- 신규 테이블: users, user_profiles, user_preferences, recommendation_history, user_feedback';
    RAISE NOTICE '- JSONB 최적화: tags, purposes, skin_concerns, intent_tags, recommended_products';
    RAISE NOTICE '- GIN 인덱스: JSONB 필드 검색 최적화';
    RAISE NOTICE '- UUID 기반 사용자 식별자 적용';
    RAISE NOTICE '- TIMESTAMPTZ 타임스탬프 적용';
END $$;