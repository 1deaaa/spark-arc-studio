# 使用官方 Python 3.12 瘦身版镜像作为基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
# 防止 Python 生成 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE=1
# 防止 Python 缓冲 stdout 和 stderr
ENV PYTHONUNBUFFERED=1

# 复制 requirements.txt 并安装依赖
# 先复制依赖文件可以利用 Docker 层缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制整个 server 目录到容器中
# 注意：这里假设构建上下文是项目根目录，或者需要根据实际情况调整 COPY 路径
# 根据项目结构，server 代码在 ./server 目录下
COPY server/ ./server/
# 同时需要 client/dist 如果需要后端提供前端静态文件服务，这里暂时只关注后端
# COPY client/dist/ ./client/dist/

# 暴露端口，与 uvicorn 配置一致
EXPOSE 6688

# 启动命令
# 切换到 server 目录执行，或者调整 uvicorn 的 app 路径
WORKDIR /app/server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "6688"]
