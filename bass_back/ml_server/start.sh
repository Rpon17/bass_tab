#!/bin/bash

# 1. 현재 스크립트가 있는 폴더(ml_server)로 확실히 이동!
cd /opt/render/project/src/bass_back/ml_server

# 2. 파이썬한테 "여기가 진짜 루트다!"라고 주소 박아주기
export PYTHONPATH=$PYTHONPATH:/opt/render/project/src/bass_back/ml_server

# 3. 워커 실행 (절대 경로로 실행해서 실수 없게!)
python app/worker/ml_worker.py &

# 4. 메인 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 10000