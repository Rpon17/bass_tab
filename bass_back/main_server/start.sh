#!/bin/bash

# 1. 현재 폴더 위치를 파이썬 경로에 추가 (main_server 내의 app 폴더 인식)
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 2. 제출 워커(submit_worker) 실행 
# (사용자가 올린 유튜브 링크를 DB에 넣고 Redis에 신호 보내는 역할)
python app/worker/submit_worker.py &

# 3. 통신 워커(communicate_worker) 실행 
# (ML 서버가 분석 끝냈다는 소식을 듣고 DB를 업데이트하는 역할)
python app/worker/communicate_worker.py &

# 4. 메인 API 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 10000 --proxy-headers