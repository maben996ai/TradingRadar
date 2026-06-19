FROM python:3.12-slim

WORKDIR /app

# 注：内容分析的下载/转码需要系统 ffmpeg。当前网络无法从 deb.debian.org 安装，
# 暂不在镜像内安装；登录/cookies 校验仅需 pip 的 yt-dlp，不依赖 ffmpeg。
# 待网络可用或换镜像源后，再加回：
#   RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# 先复制依赖文件，利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码（本地开发时会被 volume 覆盖）
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
