"""
pytest 配置
"""
import pytest
import asyncio
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环用于异步测试"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_paper_data():
    """示例论文数据"""
    return {
        "title": "Test Paper",
        "authors": ["Author A", "Author B"],
        "summary": "This is a test abstract",
        "published": "2024-01-01",
        "arxiv_id": "2401.00001",
        "categories": ["cs.AI"],
    }


@pytest.fixture
def sample_workflow_data():
    """示例工作流数据"""
    return {
        "query": "test query",
        "year_range": "2024-2025",
        "max_papers": 5,
        "source": "arxiv",
    }
