# ==========================================
# 第一阶段: 构建前端 (Builder)
# ==========================================
FROM node:lts-slim as frontend-builder

# 可通过构建参数覆盖 npm 源以避免网络问题
ARG NPM_REGISTRY=https://registry.npmmirror.com

# 设置前端构建的工作目录
WORKDIR /app/client

# 复制依赖定义文件
COPY client/package*.json ./

# 安装依赖
# 使用 npm ci 以确保构建环境的一致性 (Reproducible builds)
# --mount=type=cache:利用 Docker 缓存挂载点，避免重复下载 npm 包
RUN --mount=type=cache,target=/root/.npm \
    npm config set registry ${NPM_REGISTRY} && \
    npm ci

# 复制前端源代码
COPY client/ .

# 编译应用
RUN npm run build

# ==========================================
# 第二阶段: 运行时环境 (Runtime)
# ==========================================
FROM python:3.12-slim

WORKDIR /app

# 设置环境变量
# 防止 Python 生成 .pyc 文件
ENV PYTHONDONTWRITEBYTECODE=1
# 防止 Python 缓冲 stdout 和 stderr
ENV PYTHONUNBUFFERED=1

# 安装后端依赖
COPY requirements.txt .
# --mount=type=cache:利用 Docker 缓存挂载点，加速 pip 安装
# 移除 --no-cache-dir 以允许 pip 使用挂载的缓存
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# 复制后端代码
COPY server/ ./server/

# 从构建阶段复制编译好的前端静态资源
COPY --from=frontend-builder /app/client/dist ./client/dist

# 备份会被 Volume 挂载覆盖的代码目录（用于启动时同步）
# 这样即使 Volume 中保留了旧代码，每次启动都能刷新为镜像中的最新版本
RUN cp -r /app/server/llm/llm_mgr /_pristine_code/llm_mgr

# 创建数据持久化目录
RUN mkdir -p /app/server/_userdata /app/server/data

# 复制并设置启动入口脚本
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# 暴露端口
EXPOSE 6688

# 切换工作目录到 server 以运行应用
WORKDIR /app/server

# 入口脚本负责在启动前同步代码文件
ENTRYPOINT ["/entrypoint.sh"]
# 启动命令（作为参数传递给 entrypoint）
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "6688", "--log-config", "uvicorn_log_config.json"]
