#!/bin/bash
# 测试脚本

set -e

echo "========================================"
echo " 文献分析工作流系统 - 测试脚本"
echo "========================================"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试计数
TESTS_PASSED=0
TESTS_FAILED=0

# 测试函数
run_test() {
    local name="$1"
    local cmd="$2"

    echo -n "测试：$name ... "

    if eval "$cmd" > /dev/null 2>&1; then
        echo -e "${GREEN}通过${NC}"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}失败${NC}"
        ((TESTS_FAILED++))
        return 1
    fi
}

# 检查服务状态
echo ""
echo "1. 服务状态检查"
echo "----------------------------------------"

run_test "后端服务运行" "curl -s http://localhost:8000/health"
run_test "前端服务运行" "curl -s http://localhost:5173/ > /dev/null"
run_test "Swagger 文档可用" "curl -s http://localhost:8000/docs | grep -q 'Swagger'"

# API 测试
echo ""
echo "2. API 功能测试"
echo "----------------------------------------"

run_test "健康检查接口" "curl -s http://localhost:8000/health | grep -q 'healthy'"
run_test "获取工作流列表" "curl -s http://localhost:8000/api/workflows | grep -q 'items'"
run_test "获取论文列表" "curl -s http://localhost:8000/api/papers | grep -q 'items'"
run_test "获取报告列表" "curl -s http://localhost:8000/api/reports | grep -q 'items'"
run_test "获取记忆列表" "curl -s http://localhost:8000/api/memory | grep -q 'items'"

# 创建工作流测试
echo ""
echo "3. 工作流创建测试"
echo "----------------------------------------"

WORKFLOW_RESPONSE=$(curl -s -X POST http://localhost:8000/api/workflows \
  -H "Content-Type: application/json" \
  -d '{"query": "test workflow", "year_range": "2024-2026", "max_papers": 1, "source": "arxiv"}')

WORKFLOW_ID=$(echo "$WORKFLOW_RESPONSE" | grep -o '"id":"[^"]*"' | cut -d'"' -f4)

if [ -n "$WORKFLOW_ID" ]; then
    echo -e "${GREEN}工作流创建成功：$WORKFLOW_ID${NC}"
    ((TESTS_PASSED++))

    # 检查工作流状态
    sleep 2
    run_test "获取工作流详情" "curl -s http://localhost:8000/api/workflows/$WORKFLOW_ID | grep -q 'status'"
else
    echo -e "${RED}工作流创建失败${NC}"
    ((TESTS_FAILED++))
fi

# 数据库检查
echo ""
echo "4. 数据库检查"
echo "----------------------------------------"

if [ -f "output/workflow_store.db" ]; then
    echo -e "${GREEN}SQLite 数据库存在${NC}"
    ((TESTS_PASSED++))
else
    echo -e "${YELLOW}SQLite 数据库不存在 (首次运行时创建)${NC}"
fi

# 输出目录检查
echo ""
echo "5. 输出目录检查"
echo "----------------------------------------"

run_test "输出目录存在" "test -d output"
run_test "papers 目录存在" "test -d output/papers"
run_test "reports 目录存在" "test -d output/reports"

# 总结
echo ""
echo "========================================"
echo " 测试总结"
echo "========================================"
echo -e "通过：${GREEN}$TESTS_PASSED${NC}"
echo -e "失败：${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}所有测试通过！${NC}"
    exit 0
else
    echo -e "${RED}部分测试失败，请检查日志。${NC}"
    exit 1
fi
