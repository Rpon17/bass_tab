# 1. 현재 폴더(ml_server)를 파이썬 경로에 추가해!
export PYTHONPATH=$PYTHONPATH:$(pwd)

# 2. 워커 실행
python app/worker/ml_worker.py &

# 3. 메인 서버 실행
uvicorn app.main:app --host 0.0.0.0 --port 10000