# Render 배포 가이드

## 1. 사전 준비

### GitHub 저장소 준비
- 코드를 GitHub에 푸시해야 합니다
- `render.yaml` 파일이 루트 디렉토리에 있어야 합니다

### Supabase 데이터베이스 확인
- Supabase 프로젝트가 생성되어 있어야 합니다
- 데이터베이스 연결 문자열을 확인해두세요

## 2. Render 배포 단계

### 2.1 Render 계정 생성 및 로그인
1. [render.com](https://render.com)에서 계정 생성
2. GitHub 계정으로 연결

### 2.2 새 웹 서비스 생성
1. Render 대시보드에서 "New +" 클릭
2. "Web Service" 선택
3. GitHub 저장소 연결

### 2.3 서비스 설정
- **Name**: `cosmetic-recommendation-api`
- **Environment**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `./start.sh` 또는 `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Instance Type**: `Free` (시작용) 또는 `Starter` (프로덕션용)

### 2.4 환경 변수 설정
Render 대시보드의 Environment 탭에서 다음 변수들을 설정:

```
DATABASE_URL=your_supabase_connection_string
DEBUG=False
API_V1_STR=/api/v1
PROJECT_NAME=Cosmetic Recommendation API
ENVIRONMENT=production
PYTHON_VERSION=3.11
```

### 2.5 배포 실행
- "Create Web Service" 클릭
- 자동으로 빌드 및 배포가 시작됩니다

## 3. 배포 후 확인

### 3.1 서비스 상태 확인
- Render 대시보드에서 서비스 상태 확인
- 로그에서 에러가 없는지 확인

### 3.2 API 테스트
```bash
# 헬스체크
curl https://your-app-name.onrender.com/health

# API 문서 확인
https://your-app-name.onrender.com/docs
```

### 3.3 데이터베이스 연결 확인
```bash
# 관리자 헬스체크 (데이터베이스 연결 포함)
curl https://your-app-name.onrender.com/api/v1/admin/health
```

## 4. 도메인 설정 (선택사항)

### 4.1 커스텀 도메인 연결
1. Render 대시보드에서 "Settings" 탭
2. "Custom Domains" 섹션에서 도메인 추가
3. DNS 설정에서 CNAME 레코드 추가

### 4.2 SSL 인증서
- Render에서 자동으로 Let's Encrypt SSL 인증서 제공
- 커스텀 도메인도 자동으로 SSL 적용

## 5. 모니터링 및 로그

### 5.1 로그 확인
- Render 대시보드의 "Logs" 탭에서 실시간 로그 확인
- 에러 발생 시 로그에서 원인 파악

### 5.2 메트릭 모니터링
- CPU, 메모리 사용량 모니터링
- 응답 시간 및 에러율 확인

## 6. 자동 배포 설정

### 6.1 GitHub 연동
- main 브랜치에 푸시할 때마다 자동 배포
- Pull Request 미리보기 배포 (Pro 플랜)

### 6.2 배포 알림
- Slack, Discord 등으로 배포 알림 설정 가능

## 7. 트러블슈팅

### 7.1 일반적인 문제들

#### 빌드 실패
- `requirements.txt` 파일 확인
- Python 버전 호환성 확인

#### 시작 실패
- 환경 변수 설정 확인
- 포트 설정 확인 (`$PORT` 환경 변수 사용)

#### 데이터베이스 연결 실패
- Supabase 연결 문자열 확인
- 방화벽 설정 확인

### 7.2 성능 최적화
- Gunicorn worker 수 조정
- 인스턴스 타입 업그레이드
- 캐싱 전략 구현

## 8. 비용 관리

### 8.1 Free Tier 제한
- 750시간/월 (약 한 달)
- 15분 비활성 후 슬립 모드
- 512MB RAM, 0.1 CPU

### 8.2 Starter Plan ($7/월)
- 항상 활성 상태
- 더 많은 리소스
- 커스텀 도메인 지원

## 9. 보안 고려사항

### 9.1 환경 변수 보안
- 민감한 정보는 환경 변수로 관리
- `.env` 파일은 `.gitignore`에 추가

### 9.2 CORS 설정
- 프로덕션에서는 특정 도메인만 허용
- 불필요한 HTTP 메서드 제한

### 9.3 HTTPS 강제
- 모든 트래픽을 HTTPS로 리다이렉트
- 보안 헤더 추가