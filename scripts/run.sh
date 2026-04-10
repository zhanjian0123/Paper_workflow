#!/bin/bash
# 科研文献工作流 - 运行脚本

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 激活虚拟环境（如果存在）
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
fi

# 检查环境配置
if [ ! -f ".env" ]; then
    echo "警告：.env 文件不存在"
    echo "请复制 .env.example 并配置 API Key"
    echo "  cp .env.example .env"
    echo ""
fi

# 运行工作流
echo ""
python main.py "$@"
