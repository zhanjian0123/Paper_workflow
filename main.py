"""
Multi-Agent 文献工作流系统 - 主程序入口
"""

import asyncio
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from core.message_bus import MessageBus
from core.skill_loader import SkillLoader
from core.llm_client import LLMClient
from core.config_loader import ConfigLoader
from core.workflow_engine import WorkflowEngine
from memory.task_memory import TaskMemory
from memory.agent_memory import AgentMemory
from memory.long_term_memory import LongTermMemory
from mcp.tools_registry import ToolsRegistry
from agents import (
    CoordinatorAgent,
    SearchAgent,
    AnalystAgent,
    WriterAgent,
    ReviewerAgent,
    EditorAgent,
)


class MultiAgentSystem:
    """
    Multi-Agent 系统管理器
    """

    def __init__(
        self,
        api_key: str = None,
        base_url: str = None,
        model_name: str = "qwen3.5-plus",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.model_name = model_name

        # 初始化核心组件
        self.message_bus = MessageBus()
        self.skill_loader = SkillLoader()
        self.task_memory = TaskMemory()
        self.agent_memory = AgentMemory()
        self.long_term_memory = LongTermMemory()
        self.tools_registry = ToolsRegistry()
        self.config_loader = ConfigLoader()

        # LLM 客户端
        self.llm_client = LLMClient(
            api_key=api_key, base_url=base_url, model_name=model_name
        )

        # Agent 实例
        self.agents = {}

    async def initialize(self) -> None:
        """初始化系统"""
        # 初始化工具
        await self.tools_registry.initialize_all()

        # 创建所有 Agent
        self._create_agents()

        print("[System] All agents initialized")

    def _create_agents(self) -> None:
        """创建所有 Agent"""
        common_kwargs = {
            "message_bus": self.message_bus,
            "task_memory": self.task_memory,
            "agent_memory": self.agent_memory,
            "skill_loader": self.skill_loader,
            "model_name": self.model_name,
            "base_url": self.base_url,
            "api_key": self.api_key,
        }

        # Coordinator
        self.agents["coordinator"] = CoordinatorAgent(
            tools_registry=self.tools_registry, **common_kwargs
        )

        # Search Agent
        self.agents["search"] = SearchAgent(
            tools_registry=self.tools_registry, **common_kwargs
        )

        # Analyst Agent
        self.agents["analyst"] = AnalystAgent(
            tools_registry=self.tools_registry, **common_kwargs
        )

        # Writer Agent
        self.agents["writer"] = WriterAgent(
            tools_registry=self.tools_registry, **common_kwargs
        )

        # Reviewer Agent
        self.agents["reviewer"] = ReviewerAgent(**common_kwargs)

        # Editor Agent
        self.agents["editor"] = EditorAgent(
            tools_registry=self.tools_registry, **common_kwargs
        )

        print(f"[System] Created {len(self.agents)} agents")

    async def run_task(self, user_request: str, year_range: Optional[str] = None, max_papers: int = 10, source: str = "arxiv") -> dict:
        """
        运行一个用户任务 - 使用 WorkflowEngine 顺序执行所有 Agent
        """
        print(f"\n[System] Processing request: {user_request[:50]}...")
        print(f"[System] 年份范围：{year_range if year_range else '不限'}")
        print(f"[System] 最大论文数量：{max_papers}")
        print(f"[System] 数据源：{source}")

        # 创建工作流引擎并执行
        workflow = WorkflowEngine(
            search_agent=self.agents["search"],
            analyst_agent=self.agents["analyst"],
            writer_agent=self.agents["writer"],
            reviewer_agent=self.agents["reviewer"],
            editor_agent=self.agents["editor"],
            task_memory=self.task_memory,
            skill_loader=self.skill_loader,
            download_dir="output/papers",
            max_papers=max_papers,
            source=source,
        )

        result = await workflow.run(user_request, year_range)
        return result

    async def run_agent_directly(
        self, agent_name: str, task_content: dict
    ) -> dict:
        """直接运行特定 Agent（跳过 Coordinator）"""
        if agent_name not in self.agents:
            raise ValueError(f"Unknown agent: {agent_name}")

        agent = self.agents[agent_name]
        result = await agent.run_once(task_content)
        return result

    async def shutdown(self) -> None:
        """关闭系统"""
        await self.tools_registry.cleanup_all()
        await self.message_bus.stop()
        print("[System] Shutdown complete")


async def main_async():
    """异步主函数"""
    parser = argparse.ArgumentParser(
        description="Multi-Agent 文献工作流系统"
    )
    parser.add_argument(
        "--request",
        "-r",
        type=str,
        help="用户请求，例如：'搜索关于 transformer 的最新论文'",
    )
    parser.add_argument(
        "--agent",
        "-a",
        type=str,
        choices=[
            "coordinator",
            "search",
            "analyst",
            "writer",
            "reviewer",
            "editor",
        ],
        help="直接运行特定 Agent",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="API Key（覆盖环境变量）",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        help="API Base URL（覆盖环境变量）",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="qwen3.5-plus",
        help="模型名称",
    )
    parser.add_argument(
        "--list-agents",
        action="store_true",
        help="列出所有可用 Agent",
    )
    parser.add_argument(
        "--year-range",
        "-y",
        type=str,
        default=None,
        help="年份范围，如 2020-2024 或 2023",
    )
    parser.add_argument(
        "--max-papers",
        "-m",
        type=int,
        default=10,
        help="搜索并下载的最大论文数量（默认：10）",
    )
    parser.add_argument(
        "--source",
        "-s",
        type=str,
        default="arxiv",
        choices=["arxiv", "google", "both"],
        help="论文数据源：arxiv（仅 ArXiv）, google（仅 Google Scholar）, both（两者）（默认：arxiv）",
    )
    parser.add_argument(
        "--web-search-query",
        type=str,
        help="直接调用 web_search 工具进行联网搜索",
    )
    parser.add_argument(
        "--web-search-max-results",
        type=int,
        default=5,
        help="web_search 工具返回的最大结果数（默认：5）",
    )
    parser.add_argument(
        "--memory",
        type=str,
        choices=["list", "save", "delete", "cleanup"],
        help="长期记忆操作：list（查看）, save（保存）, delete（删除）, cleanup（清理）",
    )
    parser.add_argument(
        "--memory-type",
        type=str,
        choices=["user", "feedback", "project", "reference"],
        help="记忆类型",
    )
    parser.add_argument(
        "--memory-name",
        type=str,
        help="记忆名称（用于 save/delete）",
    )
    parser.add_argument(
        "--memory-content",
        type=str,
        help="记忆内容（用于 save）",
    )
    parser.add_argument(
        "--memory-id",
        type=str,
        help="记忆 ID（用于 delete）",
    )

    args = parser.parse_args()

    # 加载 .env 文件（如果存在）
    load_dotenv()

    # 创建系统
    system = MultiAgentSystem(
        api_key=args.api_key,
        base_url=args.base_url,
        model_name=args.model,
    )

    try:
        await system.initialize()

        # 处理记忆操作
        if args.memory:
            memory = system.long_term_memory

            if args.memory == "list":
                # 列出所有记忆
                print("\n=== 长期记忆列表 ===\n")
                print(memory.get_index_summary())

                # 按类型显示详情
                for mem_type in ["user", "feedback", "project", "reference"]:
                    entries = memory.get(memory_type=mem_type)
                    if entries:
                        print(f"\n--- {mem_type.upper()} ({len(entries)} 条) ---")
                        for entry in entries[:10]:  # 每类型最多显示 10 条
                            stale = f" [过时 {entry.stale_days()}天]" if entry.is_stale() else ""
                            expired = " [已过期]" if entry.is_expired() else ""
                            print(f"  • {entry.name}{stale}{expired}")

                print("\n使用 --memory cleanup 清理过期/过时记忆")

            elif args.memory == "save":
                # 保存记忆
                if not args.memory_type or not args.memory_name or not args.memory_content:
                    print("错误：保存记忆需要 --memory-type, --memory-name, --memory-content")
                    return 1

                entry = memory.save(
                    memory_type=args.memory_type,
                    name=args.memory_name,
                    description=args.memory_content,
                )

                if entry:
                    print(f"\n记忆已保存:")
                    print(f"  类型：{entry.memory_type}")
                    print(f"  名称：{entry.name}")
                    print(f"  ID: {entry.id}")
                else:
                    print("\n记忆保存失败（可能包含敏感信息或不符合保存规则）")

            elif args.memory == "delete":
                # 删除记忆
                if not args.memory_id:
                    print("错误：删除记忆需要 --memory-id")
                    return 1

                success = memory.delete(args.memory_id)
                if success:
                    print(f"记忆 {args.memory_id} 已删除")
                else:
                    print(f"未找到记忆 {args.memory_id}")

            elif args.memory == "cleanup":
                # 清理过期/过时记忆
                print("\n正在清理过期/过时记忆...")
                stats = memory.cleanup()
                print(f"清理完成:")
                print(f"  总记忆数：{stats['total']}")
                print(f"  已删除过期：{stats['expired']}")
                print(f"  已删除过时：{stats['stale']}")

            return 0

        if args.list_agents:
            print("\nAvailable Agents:")
            for name, agent in system.agents.items():
                print(f"  - {name}: {agent.description}")
            return 0

        if args.web_search_query:
            result = await system.tools_registry.execute_tool(
                "web_search",
                "search",
                query=args.web_search_query,
                max_results=args.web_search_max_results,
            )
            print(f"\n{'='*60}")
            print("Web Search 结果")
            print(f"{'='*60}")
            if result.success:
                print(f"搜索引擎：{result.metadata.get('engine', 'N/A')}")
                if result.warning:
                    print(f"警告：{result.warning}")
                for idx, item in enumerate(result.data.get("results", []), 1):
                    print(f"{idx}. {item.get('title', 'N/A')}")
                    print(f"   URL: {item.get('url', '')}")
                    print(f"   摘要: {item.get('snippet', '')}")
            else:
                print(f"错误：{result.error}")
                return 1
            return 0

        if args.agent:
            # 直接运行特定 Agent
            if args.request:
                result = await system.run_agent_directly(
                    args.agent, {"query": args.request}
                )
                print(f"\n{'='*60}")
                print(f"{args.agent} Agent 执行完成")
                print(f"{'='*60}")
                # 只打印关键信息，不打印完整 JSON
                if isinstance(result, dict):
                    for key, value in result.items():
                        if key not in ['papers', 'analysis', 'draft']:  # 跳过大数据字段
                            print(f"{key}: {value}")
                    if 'papers' in result:
                        papers = result['papers']
                        print(f"papers: {len(papers)} 篇")
                        for i, paper in enumerate(papers[:3], 1):
                            title = paper.get('title', 'N/A')
                            print(f"  {i}. {title}")
                else:
                    print(result)
            else:
                print(f"Error: --request is required when using --agent")
                return 1

        elif args.request:
            # 通过 Coordinator 处理完整工作流
            result = await system.run_task(args.request, args.year_range, args.max_papers, args.source)

            # 打印摘要信息（不打印完整 JSON）
            print(f"\n{'='*60}")
            print("工作流完成！")
            print(f"{'='*60}")
            print(f"状态：{result.get('status', 'N/A')}")
            print(f"任务 ID: {result.get('task_id', 'N/A')}")
            print(f"论文数量：{len(result.get('papers', []))}")
            if result.get('papers'):
                print("\n论文列表:")
                for i, paper in enumerate(result.get('papers', [])[:5], 1):
                    title = paper.get('title', 'N/A')
                    published = paper.get('published', 'N/A')[:10] if paper.get('published') else 'N/A'
                    print(f"  {i}. {title} ({published})")
                if len(result.get('papers', [])) > 5:
                    print(f"  ... 还有 {len(result.get('papers', [])) - 5} 篇")

            # 保存结果
            output_dir = Path("output/reports")
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = output_dir / f"result_{timestamp}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\n完整结果已保存至：{output_file}")

            # 如果有最终报告，打印报告预览
            if result.get('final_report'):
                report = result.get('final_report', '')
                print(f"\n{'='*60}")
                print("最终报告预览（前 1000 字符）:")
                print(f"{'='*60}")
                print(report[:1000] if len(report) > 1000 else report)
                if len(report) > 1000:
                    print(f"\n... 完整报告请查看输出目录中的 markdown 文件")

        else:
            # 交互模式
            print("\n=== Multi-Agent 文献工作流系统 ===")
            print("输入 'quit' 或 'exit' 退出")
            print("输入 'help' 查看可用 Agent\n")

            while True:
                try:
                    user_input = input("> ").strip()
                    if not user_input:
                        continue
                    if user_input.lower() in ["quit", "exit"]:
                        break
                    if user_input.lower() == "help":
                        print("\n可用 Agent:")
                        for name, agent in system.agents.items():
                            print(f"  - {name}: {agent.description}")
                        continue

                    # 处理请求
                    result = await system.run_task(user_input)

                    # 打印摘要信息（不打印完整 JSON）
                    print(f"\n{'='*60}")
                    print("工作流完成！")
                    print(f"{'='*60}")
                    print(f"状态：{result.get('status', 'N/A')}")
                    print(f"论文数量：{len(result.get('papers', []))}")
                    if result.get('papers'):
                        print("\n论文列表:")
                        for i, paper in enumerate(result.get('papers', [])[:5], 1):
                            title = paper.get('title', 'N/A')
                            print(f"  {i}. {title}")
                        if len(result.get('papers', [])) > 5:
                            print(f"  ... 还有 {len(result.get('papers', [])) - 5} 篇")

                    # 保存结果
                    output_dir = Path("output/reports")
                    output_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_file = output_dir / f"result_{timestamp}.json"
                    with open(output_file, "w", encoding="utf-8") as f:
                        json.dump(result, f, indent=2, ensure_ascii=False)
                    print(f"\n完整结果已保存至：{output_file}")

                except KeyboardInterrupt:
                    print("\nInterrupted")
                    break
                except Exception as e:
                    print(f"\nError: {e}")

        return 0

    except KeyboardInterrupt:
        print("\nInterrupted by user")
        return 1
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        await system.shutdown()


def load_dotenv():
    """加载 .env 文件"""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    import os

                    os.environ.setdefault(key.strip(), value.strip())


def main():
    """同步主函数入口"""
    sys.exit(asyncio.run(main_async()))


if __name__ == "__main__":
    main()
