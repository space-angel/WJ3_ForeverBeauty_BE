#!/bin/bash

# 프로덕션 환경에서 FastAPI 앱 시작
if [ "$DEBUG" = "True" ]; then
    echo "개발 모드로 시작..."
    uvicorn app.main:app --host 0.0.0.0 --port $PORT --reload
else
    echo "프로덕션 모드로 시작..."
    gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
fi