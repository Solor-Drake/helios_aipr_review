#!/bin/bash
# AI PR Reviewer - 环境配置脚本
# 用法: bash setup.sh

set -e

echo "========================================="
echo " AI PR Reviewer - 环境配置"
echo "========================================="
echo ""

# 1. 检查 Python 版本
echo "[1/5] 检查 Python 版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "  检测到 Python $python_version"

# 检查版本是否 >= 3.11
major=$(echo $python_version | cut -d. -f1)
minor=$(echo $python_version | cut -d. -f2)
if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 11 ]); then
    echo "  ⚠️  需要 Python 3.11+，当前版本: $python_version"
    echo "  请升级 Python 后重试"
    exit 1
fi
echo "  ✅ Python 版本符合要求"
echo ""

# 2. 创建虚拟环境
echo "[2/5] 创建 Python 虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  ✅ 虚拟环境创建完成: ./venv"
else
    echo "  ✅ 虚拟环境已存在: ./venv"
fi
echo ""

# 3. 激活虚拟环境并安装依赖
echo "[3/5] 安装 Python 依赖..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  ✅ 依赖安装完成"
echo ""

# 4. 配置环境变量
echo "[4/5] 配置环境变量..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  ✅ 已从 .env.example 创建 .env 文件"
    echo "  ⚠️  请编辑 .env 文件，填入你的 API Key:"
    echo "     - DASHSCOPE_API_KEY: 阿里云百炼 API Key"
    echo "     - GITHUB_TOKEN: GitHub Personal Access Token"
    echo ""
    echo "  编辑命令: nano .env  (或 vim .env)"
else
    echo "  ✅ .env 文件已存在，跳过"
fi
echo ""

# 5. 验证
echo "[5/5] 验证环境..."
python3 -c "import fastapi; import uvicorn; import httpx; import openai; import github; import aiosqlite; import pydantic; import dotenv; print('所有依赖导入成功')"
echo ""

echo "========================================="
echo " 🎉 环境配置完成！"
echo "========================================="
echo ""
echo "下一步："
echo "  1. 编辑 .env 文件: nano .env"
echo "  2. 启动后端服务: source venv/bin/activate && uvicorn server.app.main:app --reload --port 8000"
echo "  3. 测试健康检查: curl http://localhost:8000/health"
echo "  4. 查看 API 文档: http://localhost:8000/docs"
echo ""