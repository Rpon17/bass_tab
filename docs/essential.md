main_server

경로이동
cd C:\BASS_PROJECT\bass_back\main_server
가상환경 키는법
.\.venv\Scripts\activate
fastapi 키는법
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
주소
http://localhost:8000/docs

ml_server

경로이동
cd C:\BASS_PROJECT\bass_back\ml_server
가상환경 키는법
.\.venv\Scripts\activate
fastapi 키는법
uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
주소
http://127.0.0.1:8001/docs

worker모음

main worker
환경변수 설정 하고
$env:STORAGE_ROOT = "C:\bass_project\storage"
$env:YTDLP_COOKIEFILE="C:\bass_project\bass_back\cookie\cookies.txt"
python -m app.worker.submit_worker
submit 워커(제작후 제출)

python -m app.worker.communicate_worker  
communicater워커(불시점검)
python -m app.worker.test_worker
 테스트 워커1

ml_worker

python -m app.worker.ml_worker (마지막에만)
python -m app.worker.test_worker (이거메인)
ml 워커



시작점 고정
uvicorn api.app:app --reload --port 9001
scripts/dev_run.ps1

도커 
docker ps

docker run --name bass-redis -p 6379:6379 -d redis:7-alpine

docker start bass-redis


redis cli 접속
docker exec -it bass-redis redis-cli
KEYS *queue* -> queue가 중간에 있는 키 찾음

DEL bass:queue:youtube

워커
set REDIS_URL=redis://localhost:6379/0
set JOB_KEY_PREFIX=job:
set YOUTUBE_OUTPUT_DIR=./data/youtube
python main_server/app/worker/youtube_worker.py

깃허브 

git add .
git commit -m "워커 거의 끝나고 ml 연결할거임"
git push -u origin master

선언한 이름들
prefix -> job으로
queue -> youtube으로