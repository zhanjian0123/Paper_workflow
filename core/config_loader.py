"""
配置加载器 - 加载项目配置
"""

import yaml
from pathlib import Path
from typing import Optional, Dict, Any


class ConfigLoader:
    """
    配置加载器 - 从 YAML 文件加载配置
    """

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / "config"
        self.config_dir = Path(config_dir)
        self._cache: Dict[str, Any] = {}

    def load_agents_config(self) -> Dict[str, Any]:
        """加载 Agent 配置"""
        return self._load_yaml("agents.yml")

    def load_mcp_config(self) -> Dict[str, Any]:
        """加载 MCP 服务器配置"""
        return self._load_yaml("mcp_servers.yml")

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        """加载 YAML 文件"""
        cache_key = filename
        if cache_key in self._cache:
            return self._cache[cache_key]

        filepath = self.config_dir / filename
        if not filepath.exists():
            return {}

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        self._cache[cache_key] = data
        return data

    def get_agent_config(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """获取特定 Agent 的配置"""
        agents_config = self.load_agents_config()
        agents = agents_config.get("agents", [])
        for agent in agents:
            if agent.get("name") == agent_name:
                return agent
        return None

    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
