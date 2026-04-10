"""
Query 重写服务 - 使用 LLM 将自然语言查询重写为简洁的搜索关键词

例如：
- "搜索关于 Reinforcement Learning 的论文" → "Reinforcement Learning"
- "帮我找一下 transformer 的最新研究" → "transformer"
- "我想看 deep learning 在医疗领域的应用" → "deep learning medical application"
"""

import os
import re
from typing import Optional


class QueryRewriterLLM:
    """
    基于 LLM 的 Query 重写器

    使用大语言模型理解用户意图，提取核心研究主题关键词
    """

    SYSTEM_PROMPT = """You are a research topic extraction expert. Your task is to rewrite user queries into concise English search keywords.

Rules:
1. Extract core research topics/techniques/method names
2. Remove all redundant words (such as "search", "about", "paper", "help me find", etc.)
3. If the input contains Chinese, must translate to core English technical terms
4. For unknown Chinese terms, translate them into concise English keywords, never keep Chinese
5. Keep it concise, usually 1-5 words, prioritize "method + domain" format
6. Do not output complete sentences or natural language, only return search keyword combinations
7. Do not add any prefixes (such as "keywords:", "Query:"), directly return English keywords
8. Output must be all lowercase English letters, do not include any Chinese characters

Examples:
- "搜索关于 Reinforcement Learning 的论文" -> "reinforcement learning"
- "帮我找一下 transformer 的最新研究" -> "transformer"
- "我想看 deep learning 在医疗领域的应用" -> "deep learning medical application"
- "search papers about machine learning" -> "machine learning"
- "find me the latest research on NLP" -> "nlp"
- "GAN 在图像生成领域的应用" -> "gan image generation"
- "关于深度学习的综述" -> "deep learning review"
- "卷积神经网络" -> "convolutional neural network"
- "强化学习在机器人控制中的应用" -> "reinforcement learning robot control"
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: str = "qwen3.5-plus",
    ):
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
        self.base_url = base_url or os.environ.get(
            "ANTHROPIC_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model_name = model_name

        # 常见中文研究主题到英文检索词的映射
        self.topic_map = {
            "强化学习": "reinforcement learning",
            "深度学习": "deep learning",
            "机器学习": "machine learning",
            "注意力机制": "attention mechanism",
            "自然语言处理": "natural language processing",
            "大语言模型": "large language model",
            "语言模型": "language model",
            "计算机视觉": "computer vision",
            "图像识别": "image recognition",
            "图像分类": "image classification",
            "目标检测": "object detection",
            "图像生成": "image generation",
            "图像增强": "image enhancement",
            "推荐系统": "recommendation system",
            "迁移学习": "transfer learning",
            "联邦学习": "federated learning",
            "对比学习": "contrastive learning",
            "生成对抗网络": "generative adversarial networks",
            "卷积神经网络": "convolutional neural network",
            "transformer": "transformer",
            "bert": "BERT",
            "gpt": "GPT",
            "nlp": "NLP",
        }
        self.method_terms = {
            "强化学习": "reinforcement learning",
            "深度学习": "deep learning",
            "机器学习": "machine learning",
            "注意力机制": "attention mechanism",
            "attention mechanism": "attention mechanism",
            "大语言模型": "large language model",
            "语言模型": "language model",
            "迁移学习": "transfer learning",
            "联邦学习": "federated learning",
            "对比学习": "contrastive learning",
            "生成对抗网络": "GAN",
            "gan": "GAN",
            "transformer": "transformer",
            "bert": "BERT",
            "gpt": "GPT",
            "nlp": "NLP",
            "图像增强": "image enhancement",
        }
        self.domain_terms = {
            "图像生成": "image generation",
            "计算机视觉": "computer vision",
            "图像识别": "image recognition",
            "图像分类": "image classification",
            "目标检测": "object detection",
            "医疗": "medical application",
            "医学": "medical application",
            "机器人控制": "robot control",
            "推荐系统": "recommendation system",
            "机器人": "robot",
            "控制": "control",
        }

    async def rewrite(self, query: str) -> str:
        """
        使用 LLM 重写查询

        Args:
            query: 原始查询（可能包含自然语言）

        Returns:
            重写后的简洁查询
        """
        if not query or not query.strip():
            return query

        query = query.strip()
        locally_cleaned = self._rule_based_rewrite(query)
        has_chinese = self._has_chinese(query)

        # 中文查询优先交给 LLM 做语义提炼，避免未知术语必须手工加映射
        if has_chinese:
            print(f"[QueryRewriter] 原始查询：{query}")
            try:
                rewritten = await self._call_llm(query)
                print(f"[QueryRewriter] LLM 输出：{rewritten}")
                rewritten = self._postprocess_rewritten_query(rewritten, original_query=query)
                print(f"[QueryRewriter] 清洗后：{rewritten}")
                if self._is_usable_rewrite(rewritten):
                    result = self._merge_with_local_hint(rewritten, locally_cleaned)
                    print(f"[QueryRewriter] 最终查询：{result}")
                    return result
                if locally_cleaned and locally_cleaned != query and not self._has_chinese(locally_cleaned):
                    print(f"[QueryRewriter] 使用本地规则结果：{locally_cleaned}")
                    return locally_cleaned
                # 如果本地规则也返回中文，使用安全翻译
                if locally_cleaned and self._has_chinese(locally_cleaned):
                    result = self._safe_translate_chinese(query)
                    print(f"[QueryRewriter] 安全翻译结果：{result}")
                    return result
                result = rewritten or self._safe_translate_chinese(query)
                print(f"[QueryRewriter] 最终查询：{result}")
                return result
            except Exception as e:
                print(f"[QueryRewriter] 中文查询 LLM 调用失败：{e}，回退本地规则")
                # LLM 失败时，如果本地规则返回中文，使用安全翻译
                if not locally_cleaned or self._has_chinese(locally_cleaned):
                    result = self._safe_translate_chinese(query)
                    print(f"[QueryRewriter] 安全翻译结果：{result}")
                    return result
                print(f"[QueryRewriter] 使用本地规则结果：{locally_cleaned}")
                return locally_cleaned

        # 如果查询已经很简洁（少于 3 个词），直接返回
        if len(query.split()) <= 3 and not self._has_chinese(query):
            # 检查是否包含明显的冗余词
            redundant_words = ["search", "find", "paper", "about", "research"]
            if not any(word in query.lower() for word in redundant_words):
                return query

        try:
            print(f"[QueryRewriter] 英文查询优化：{query}")
            rewritten = await self._call_llm(query)
            print(f"[QueryRewriter] LLM 输出：{rewritten}")
            rewritten = self._postprocess_rewritten_query(rewritten, original_query=query)
            print(f"[QueryRewriter] 清洗后：{rewritten}")
            if rewritten and rewritten != query:
                print(f"[QueryRewriter] 最终查询：{rewritten}")
                return rewritten
            print(f"[QueryRewriter] 使用本地规则结果：{locally_cleaned or query}")
            return locally_cleaned or query
        except Exception as e:
            print(f"[QueryRewriter] LLM 调用失败：{e}，返回原始查询")
            return locally_cleaned or query

    async def _call_llm(self, query: str) -> str:
        """调用 LLM 重写查询"""
        from tools.http_client import HttpClient

        messages = [
            {"role": "user", "content": f"Please rewrite this research topic query: {query}"}
        ]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload = {
            "model": self.model_name,
            "messages": [{"role": "system", "content": self.SYSTEM_PROMPT}] + messages,
            "temperature": 0.3,
            "max_tokens": 100,
        }

        # 使用 HttpClient 发送请求（支持 SSL 配置）
        client = HttpClient(verify_ssl=False, timeout=30)
        success, response_text, error = await client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
        )

        if not success:
            raise Exception(f"LLM API error: {error}")

        import json
        result = json.loads(response_text)

        if result.get("choices") and len(result["choices"]) > 0:
            return result["choices"][0]["message"]["content"].strip()
        else:
            raise Exception("No response from LLM")

    def _has_chinese(self, text: str) -> bool:
        """检查文本是否包含中文"""
        for char in text:
            if '\u4e00' <= char <= '\u9fff':
                return True
        return False

    def _rule_based_rewrite(self, query: str) -> str:
        """本地规则清洗，避免直接把指令句原样送去搜索"""
        cleaned = query.strip()

        # 注意：| 两边不能有空格，否则匹配的是带空格的词
        patterns = [
            r"^(请|麻烦|帮我|帮忙|帮我找一下|帮我搜索|帮我查找|帮我查一下|我想看|我想找|我想搜索|我需要|请帮我搜索|请帮我找)+",
            r"^(搜索|查找|查一下|找一下|找|检索|搜一下|搜)+",
            r"(有关|关于|相关的|相关)+",
            r"(的研究|的论文|论文|文献|研究|相关文章|综述|资料)+$",
            r"^(topic|search|find|look for)\s+",
            r"^(papers?\s+about|research\s+on|studies\s+on)\s+",
        ]
        for pattern in patterns:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()

        cleaned = re.sub(r"[，。！？、,.!?]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        lowered = cleaned.lower()

        # 按长度排序，优先匹配长术语（避免"机器人控制"被拆成"机器人"+"控制"）
        all_terms = []
        for zh, en in self.topic_map.items():
            all_terms.append((zh, en.lower()))
        for zh, en in self.method_terms.items():
            all_terms.append((zh, en.lower()))
        for zh, en in self.domain_terms.items():
            all_terms.append((zh, en.lower()))

        # 按中文长度降序排序
        all_terms.sort(key=lambda x: len(x[0]), reverse=True)

        # 去重：如果同一个中文术语出现多次，只保留第一个
        unique_terms = []
        seen_zh = set()
        for zh, en in all_terms:
            if zh not in seen_zh:
                unique_terms.append((zh, en))
                seen_zh.add(zh)

        # 优先匹配长术语，去重
        matched = []
        seen = set()
        remaining = cleaned
        remaining_lowered = remaining.lower()
        for zh, en in unique_terms:
            if zh in remaining or zh in remaining_lowered:
                if en.lower() not in seen:
                    matched.append(en.lower())
                    seen.add(en.lower())
                remaining = remaining.replace(zh, " ")
                remaining_lowered = remaining.lower()

        if matched:
            return " ".join(matched).strip()

        return cleaned

    def _postprocess_rewritten_query(self, rewritten: str, original_query: str) -> str:
        """清洗 LLM 输出，防止把整句原样返回"""
        cleaned = rewritten.strip().strip('"').strip("'")
        cleaned = re.sub(r"^(关键词[:：]|query[:：]| 搜索词 [:：])", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"^(rewritten query[:：]|keywords?[:：])", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = self._compress_keyword_phrase(cleaned)

        # 如果 LLM 输出仍然是中文，使用安全翻译（确保返回英文）
        if self._has_chinese(cleaned):
            return self._safe_translate_chinese(cleaned)

        # 如果 LLM 只是机械复读原句，则退回本地规则
        if cleaned == original_query.strip():
            return self._rule_based_rewrite(original_query)

        # 如果输出里仍带完整指令句，继续按本地规则裁剪
        if self._looks_like_instruction(cleaned):
            return self._rule_based_rewrite(cleaned)

        return cleaned

    def _is_usable_rewrite(self, text: str) -> bool:
        """判断 LLM 输出是否可直接用于检索"""
        if not text:
            return False
        if self._has_chinese(text):
            return False
        if self._looks_like_instruction(text):
            return False
        if len(text.split()) > 8:
            return False
        return True

    def _merge_with_local_hint(self, rewritten: str, locally_cleaned: str) -> str:
        """在不拉长 query 的前提下，保留本地规则已经识别出的稳定方法词"""
        if not locally_cleaned or self._has_chinese(locally_cleaned):
            return rewritten

        merged_tokens = []
        seen = set()
        for source in (locally_cleaned, rewritten):
            for token in source.split():
                norm = token.lower()
                if norm not in seen:
                    seen.add(norm)
                    merged_tokens.append(token)

        merged = " ".join(merged_tokens)
        if len(merged.split()) <= 6:
            return merged
        return rewritten

    def _compress_keyword_phrase(self, text: str) -> str:
        """将解释型长串压缩为更适合检索的关键词组合"""
        lowered = text.lower()
        replacements = [
            ("generative adversarial networks", "GAN"),
            ("natural language processing", "NLP"),
            ("large language models", "large language model"),
        ]
        compressed = text
        for src, dst in replacements:
            compressed = re.sub(src, dst, compressed, flags=re.IGNORECASE)

        tokens = compressed.split()
        deduped = []
        seen = set()
        for token in tokens:
            norm = token.lower()
            if norm not in seen:
                seen.add(norm)
                deduped.append(token)

        compressed = " ".join(deduped)

        if len(compressed.split()) > 5:
            rule_based = self._rule_based_rewrite(text)
            if rule_based:
                return rule_based

        return compressed

    def _looks_like_instruction(self, text: str) -> bool:
        """判断输出是否仍像用户指令，而不是检索词"""
        instruction_markers = [
            "帮我", "搜索", "查找", "论文", "文献", "研究主题",
            "please", "search", "find", "paper", "papers", "research on",
        ]
        lowered = text.lower()
        return any(marker in text or marker in lowered for marker in instruction_markers)

    def _translate_chinese_query(self, query: str) -> str:
        """将中文查询翻译为英文检索词"""
        tokens = []
        remaining = query

        # 按长度排序，优先匹配长术语（避免"机器人控制"被拆成"机器人"+"控制"）
        all_terms = []
        for zh, en in self.topic_map.items():
            all_terms.append((zh, en.lower()))
        for zh, en in self.method_terms.items():
            all_terms.append((zh, en.lower()))
        for zh, en in self.domain_terms.items():
            all_terms.append((zh, en.lower()))

        # 按中文长度降序排序
        all_terms.sort(key=lambda x: len(x[0]), reverse=True)

        # 优先匹配长术语
        for zh, en in all_terms:
            if zh in remaining:
                tokens.append(en)
                remaining = remaining.replace(zh, " ")

        # 移除常见中文指令词
        instruction_words = ["搜索", "查找", "查询", "论文", "文献", "研究", "关于", "的", "应用", "在", "领域"]
        for word in instruction_words:
            remaining = remaining.replace(word, " ")

        # 清理剩余内容
        remaining = re.sub(r"\s+", " ", remaining).strip()

        # 如果还有非空剩余，移除所有中文字符
        if remaining:
            remaining = re.sub(r"[\u4e00-\u9fff]", "", remaining)
            remaining = re.sub(r"\s+", " ", remaining).strip()
            if remaining:
                tokens.append(remaining.lower())

        # 去重并保持顺序
        seen = set()
        deduped = []
        for token in tokens:
            if token not in seen:
                seen.add(token)
                deduped.append(token)

        result = " ".join(deduped)
        return result.strip() if result else self._rule_based_rewrite(query)

    def _safe_translate_chinese(self, query: str) -> str:
        """安全翻译中文查询，确保返回英文（即使术语表中没有）"""
        # 首先尝试正常翻译
        result = self._translate_chinese_query(query)

        # 如果结果仍然是中文，尝试提取非中文字符
        if self._has_chinese(result):
            # 移除所有中文字符，只保留英文/数字
            english_only = re.sub(r"[\u4e00-\u9fff]", "", result)
            english_only = re.sub(r"\s+", " ", english_only).strip()

            if english_only:
                return english_only.lower()

            # 如果完全没有英文，返回原始查询中的非中文部分
            non_chinese = re.sub(r"[\u4e00-\u9fff]", " ", query)
            non_chinese = re.sub(r"\s+", " ", non_chinese).strip()

            if non_chinese:
                return non_chinese.lower()

            # 极端情况下，返回"research topic"而不是单纯的"research"
            return "research topic"

        return result


_query_rewriter: Optional[QueryRewriterLLM] = None


def get_query_rewriter() -> QueryRewriterLLM:
    """获取 QueryRewriter 单例"""
    global _query_rewriter
    if _query_rewriter is None:
        _query_rewriter = QueryRewriterLLM()
    return _query_rewriter
