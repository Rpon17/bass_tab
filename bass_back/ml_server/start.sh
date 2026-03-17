#!/bin/bash

# 1. ML 분석 워커(ml_worker) 실행
python app/worker/ml_worker.py &

# 2. ML API 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 10000