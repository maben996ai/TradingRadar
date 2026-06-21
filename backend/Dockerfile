FROM python:3.12-slim

WORKDIR /app

# 内容分析的下载/转码/转写依赖系统 ffmpeg（yt-dlp 合并音视频、转 mp3、Whisper 读音频）。
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码（本地开发时会被 volume 覆盖）
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
