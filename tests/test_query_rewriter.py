"""
Query 重写器测试
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.app.services.query_rewriter import QueryRewriterLLM


class TestQueryRewriterInitialization:
    """QueryRewriter 初始化测试"""

    def test_default_model(self):
        """测试默认模型"""
        rewriter = QueryRewriterLLM()
        assert rewriter.model_name == "qwen3.5-plus"

    def test_custom_model(self):
        """测试自定义模型"""
        rewriter = QueryRewriterLLM(model_name="test-model")
        assert rewriter.model_name == "test-model"


class TestRuleBasedRewrite:
    """基于规则的重写测试"""

    @pytest.mark.asyncio
    async def test_remove_noise_words(self):
        """测试移除噪音词"""
        rewriter = QueryRewriterLLM()
        result = rewriter._rule_based_rewrite("帮我搜索有关强化学习的论文")
        assert "强化学习" in result or "reinforcement" in result.lower()

    @pytest.mark.asyncio
    async def test_translate_known_terms(self):
        """测试已知术语翻译"""
        rewriter = QueryRewriterLLM()
        result = rewriter._rule_based_rewrite("GAN 在图像生成领域的应用")
        assert "gan" in result.lower() or "image" in result.lower()

    @pytest.mark.asyncio
    async def test_simple_english_query(self):
        """测试简单英文查询"""
        rewriter = QueryRewriterLLM()
        result = rewriter._rule_based_rewrite("machine learning")
        assert "machine learning" in result.lower()


class TestHasChinese:
    """中文检测测试"""

    def test_has_chinese_true(self):
        """测试检测中文（有中文）"""
        rewriter = QueryRewriterLLM()
        assert rewriter._has_chinese("强化学习") is True
        assert rewriter._has_chinese("machine learning 强化学习") is True

    def test_has_chinese_false(self):
        """测试检测中文（无中文）"""
        rewriter = QueryRewriterLLM()
        assert rewriter._has_chinese("machine learning") is False
        assert rewriter._has_chinese("reinforcement learning") is False


class TestPostprocessRewrittenQuery:
    """后处理测试"""

    @pytest.mark.asyncio
    async def test_remove_prefix(self):
        """测试移除前缀"""
        rewriter = QueryRewriterLLM()
        result = rewriter._postprocess_rewritten_query("keywords: machine learning")
        assert "keywords" not in result.lower()

    @pytest.mark.asyncio
    async def test_remove_explanation(self):
        """测试移除解释"""
        rewriter = QueryRewriterLLM()
        result = rewriter._postprocess_rewritten_query(
            "machine learning (机器学习)"
        )
        assert "(" not in result


class TestSafeTranslateChinese:
    """安全翻译测试"""

    @pytest.mark.asyncio
    async def test_translate_known_term(self):
        """测试已知术语翻译"""
        rewriter = QueryRewriterLLM()
        result = rewriter._safe_translate_chinese("图像增强")
        assert result != "图像增强"  # 应该有英文翻译

    @pytest.mark.asyncio
    async def test_translate_unknown_term(self):
        """测试未知术语（fallback）"""
        rewriter = QueryRewriterLLM()
        # 未知术语应该返回某种英文或通用词
        result = rewriter._safe_translate_chinese("未知术语 12345")
        # 不应该包含中文
        assert not rewriter._has_chinese(result)
