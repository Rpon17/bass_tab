main_server

경로이동
cd C:\BASS_PROJECT\bass_back\main_server
가상환경 키는법
.\.venv\Scripts\activate
fastapi 키는법
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

ml_server

경로이동
cd C:\BASS_PROJECT\bass_back\ml_server
가상환경 키는법
.\.venv\Scripts\activate
fastapi 키는법
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

시작점 고정
uvicorn api.app:app --reload --port 9001
scripts/dev_run.ps1

도커 
docker run --name bass-redis -p 6379:6379 -d redis:7-alpine

워커
set REDIS_URL=redis://localhost:6379/0
set JOB_KEY_PREFIX=job:
set YOUTUBE_OUTPUT_DIR=./data/youtube
python main_server/app/worker/youtube_worker.py

깃허브 

git add .
git commit -m "워커까지 다함 이제 테스트하고 코드 점검 그리고 ml서버 시작"
git push -u origin master

선언한 이름들
prefix -> job으로
queue -> youtube으로