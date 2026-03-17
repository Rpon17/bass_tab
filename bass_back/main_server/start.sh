#!/bin/bash

# 1. 제출 워커(submit_worker) 실행
python app/worker/submit_worker.py &

# 2. 통신 워커(communicate_worker) 실행
python app/worker/communicate_worker.py &

# 3. 메인 API 서버 실행 (포트 10000 고정)
uvicorn app.main:app --host 0.0.0.0 --port 10000