# 1. Python 베이스 이미지
FROM python:3.10-slim

# 2. OpenCV 등 필요한 시스템 라이브러리 설치
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 3. 작업 디렉토리 설정
WORKDIR /app

# 4. 파이썬 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. 프로젝트 파일 전체 복사
COPY . .

# 6. 서버 포트
EXPOSE 8080

# 7. Gunicorn을 사용해 Flask 실행
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
