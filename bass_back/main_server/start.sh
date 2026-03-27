#!/bin/bash

# 1. 경로 설정
export PYTHONPATH=$PYTHONPATH:$(pwd)

echo "[System] 서비스 기동 시퀀스 시작..."

# 2. submit_worker 실행 & 로그 강제 출력
echo "[System] Submit Worker 기동 중..."
stdbuf -oL python app/worker/submit_worker.py 2>&1 | sed "s/^/[SUBMIT] /" &

# 3. communicate_worker 실행 & 로그 강제 출력
echo "[System] Communicate Worker 기동 중..."
stdbuf -oL python app/worker/communicate_worker.py 2>&1 | sed "s/^/[COMMUNICATE] /" &

sleep 2

echo "[System] API Server 실행..."
# 4. 메인 API 서버 실행
exec uvicorn app.main:app --host 0.0.0.0 --port 10000 --proxy-headers