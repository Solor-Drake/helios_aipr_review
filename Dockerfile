# ── 构建阶段 ──
FROM python:3.11-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# ── 运行阶段 ──
FROM python:3.11-slim

WORKDIR /app

# 从 builder 复制已安装的依赖
COPY --from=builder /root/.local /root/.local

# 复制项目文件
COPY server/ ./server/
COPY server/prompts/ ./server/prompts/
COPY pyproject.toml .
COPY .env.example .

# 确保 pip 安装的包在 PATH 中
ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "server.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
