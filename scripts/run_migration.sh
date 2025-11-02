#!/bin/bash

# PostgreSQL 마이그레이션 실행 스크립트

echo "🚀 PostgreSQL 마이그레이션 시작"

# 환경변수 확인
if [ -z "$DATABASE_URL" ]; then
    echo "❌ DATABASE_URL 환경변수가 설정되지 않았습니다."
    echo "   .env 파일을 확인하거나 다음과 같이 설정하세요:"
    echo "   export DATABASE_URL='postgresql://user:password@host:port/database'"
    exit 1
fi

echo "✅ 환경변수 확인 완료"

# 1. PostgreSQL 스키마 생성
echo "📋 1단계: PostgreSQL 스키마 생성"
if command -v psql &> /dev/null; then
    psql "$DATABASE_URL" -f scripts/postgresql_schema.sql
    if [ $? -eq 0 ]; then
        echo "✅ 스키마 생성 완료"
    else
        echo "❌ 스키마 생성 실패"
        exit 1
    fi
else
    echo "⚠️  psql이 설치되지 않았습니다. 수동으로 스키마를 생성해주세요:"
    echo "   psql \$DATABASE_URL -f scripts/postgresql_schema.sql"
fi

# 2. Python 의존성 설치
echo "📦 2단계: Python 의존성 설치"
pip install asyncpg
if [ $? -eq 0 ]; then
    echo "✅ asyncpg 설치 완료"
else
    echo "❌ asyncpg 설치 실패"
    exit 1
fi

# 3. 데이터 마이그레이션 실행
echo "🔄 3단계: 데이터 마이그레이션 실행"
python scripts/migrate_sqlite_to_postgresql.py
if [ $? -eq 0 ]; then
    echo "✅ 데이터 마이그레이션 완료"
else
    echo "❌ 데이터 마이그레이션 실패"
    exit 1
fi

# 4. 마이그레이션 검증
echo "🔍 4단계: 마이그레이션 검증"
python scripts/verify_migration.py
if [ $? -eq 0 ]; then
    echo "✅ 마이그레이션 검증 완료"
else
    echo "❌ 마이그레이션 검증 실패"
    exit 1
fi

echo ""
echo "🎉 PostgreSQL 마이그레이션이 성공적으로 완료되었습니다!"
echo ""
echo "📊 다음 단계:"
echo "   1. 애플리케이션 재시작: python -m app.main"
echo "   2. 헬스체크 확인: curl http://localhost:8000/health"
echo "   3. PostgreSQL 연결 테스트: curl http://localhost:8000/api/v1/admin/health"
echo ""