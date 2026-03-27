FROM python:3.9-slim

# 오디오 분석 필수 패키지 설치
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. 라이브러리 설치 (ml_server 안의 requirements.txt 기준)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. 모든 코드와 실행 스크립트 복사
COPY . .

# 3. 실행 권한 부여 및 스크립트 실행
# start.sh 파일에 실행 권한을 줘야 서버가 켜집니다.
RUN chmod +x start.sh

# Render와 달리 포트 7860을 사용하도록 start.sh가 실행됩니다.
CMD ["./start.sh"]