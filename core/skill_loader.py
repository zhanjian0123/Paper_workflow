"""
技能加载器 - 支持 YAML 文件和 clawbot SKILL.md 格式

支持两种格式：
1. 旧版 YAML: config/skills/task_management.yml
2. Clawbot 格式：config/skills/task-management/SKILL.md
"""

import yaml
import re
from pathlib import Path
from typing import Optional


class SkillLoader:
    """
    技能加载器 - 从 config/skills 目录加载技能配置
    支持 YAML 文件和 clawbot SKILL.md 格式
    """

    # 旧版 YAML 技能名到新版文件夹名的映射
    SKILL_NAME_MAP = {
        "task_management": "task-management",
        "literature_search": "literature-search",
        "critical_analysis": "critical-analysis",
        "academic_writing": "academic-writing",
        "comparison_analysis": "comparison-analysis",
        "innovation_detection": "innovation-detection",
        "peer_review": "peer-review",
        "document_processing": "document-processing",
    }

    def __init__(self, skills_dir: Optional[Path] = None):
        if skills_dir is None:
            skills_dir = Path(__file__).parent.parent / "config" / "skills"
        self.skills_dir = Path(skills_dir)
        self._skills_cache: dict[str, dict] = {}

    def _normalize_skill_name(self, skill_name: str) -> str:
        """将技能名转换为文件夹格式 (snake_case → kebab-case)"""
        return skill_name.replace("_", "-")

    def _find_skill_file(self, skill_name: str) -> Optional[Path]:
        """
        查找技能文件，支持两种格式：
        1. 优先查找 clawbot 格式：skill-name/SKILL.md
        2. 回退到旧版格式：skill_name.yml
        """
        # 尝试 clawbot 格式
        folder_name = self.SKILL_NAME_MAP.get(skill_name, self._normalize_skill_name(skill_name))
        skill_md = self.skills_dir / folder_name / "SKILL.md"
        if skill_md.exists():
            return skill_md

        # 回退到旧版 YAML 格式
        skill_yml = self.skills_dir / f"{skill_name}.yml"
        if skill_yml.exists():
            return skill_yml

        return None

    def _parse_skill_md(self, file_path: Path) -> dict:
        """
        解析 clawbot SKILL.md 格式
        提取 YAML frontmatter 和内容
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 提取 YAML frontmatter (在 --- 之间)
        if not content.startswith("---"):
            return {"system": content.strip()}

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {"system": content.strip()}

        yaml_content = parts[1].strip()
        markdown_content = parts[2].strip()

        # 解析 YAML frontmatter
        frontmatter = yaml.safe_load(yaml_content) or {}

        # 构建技能数据结构，保持与旧版 YAML 兼容
        return {
            "name": frontmatter.get("name", file_path.parent.name),
            "description": frontmatter.get("description", ""),
            "version": frontmatter.get("version", "1.0.0"),
            "prompts": {
                "system": markdown_content
            },
            "raw_markdown": markdown_content  # 保留原始 markdown 内容
        }

    def load_skill(self, skill_name: str) -> Optional[dict]:
        """
        加载单个技能配置
        从缓存读取，如果没有则从文件加载
        """
        if skill_name in self._skills_cache:
            return self._skills_cache[skill_name]

        skill_file = self._find_skill_file(skill_name)
        if not skill_file:
            return None

        # 根据文件扩展名选择解析方式
        if skill_file.suffix == ".md":
            skill_data = self._parse_skill_md(skill_file)
        else:
            with open(skill_file, "r", encoding="utf-8") as f:
                skill_data = yaml.safe_load(f)

        self._skills_cache[skill_name] = skill_data
        return skill_data

    def load_all_skills(self) -> dict[str, dict]:
        """
        加载所有技能配置
        返回 {skill_name: skill_data} 字典
        """
        skills = {}
        if not self.skills_dir.exists():
            return skills

        # 加载 clawbot 格式 (文件夹/SKILL.md)
        for folder in self.skills_dir.iterdir():
            if folder.is_dir():
                skill_md = folder / "SKILL.md"
                if skill_md.exists():
                    # 从文件夹名推断技能名 (kebab-case → snake_case)
                    skill_name = folder.name.replace("-", "_")
                    skill_data = self._parse_skill_md(skill_md)
                    skills[skill_name] = skill_data

        # 加载旧版 YAML 格式 (不覆盖 clawbot 格式)
        for skill_file in self.skills_dir.glob("*.yml"):
            skill_name = skill_file.stem
            if skill_name not in skills:
                skill_data = self.load_skill(skill_name)
                if skill_data:
                    skills[skill_name] = skill_data

        return skills

    def get_skill_prompt(self, skill_name: str) -> Optional[str]:
        """
        获取技能的 system prompt
        """
        skill_data = self.load_skill(skill_name)
        if skill_data and "prompts" in skill_data:
            return skill_data["prompts"].get("system")
        return None

    def reload_skill(self, skill_name: str) -> Optional[dict]:
        """
        重新加载技能配置（跳过缓存）
        """
        skill_file = self._find_skill_file(skill_name)
        if not skill_file:
            return None

        # 根据文件扩展名选择解析方式
        if skill_file.suffix == ".md":
            skill_data = self._parse_skill_md(skill_file)
        else:
            with open(skill_file, "r", encoding="utf-8") as f:
                skill_data = yaml.safe_load(f)

        self._skills_cache[skill_name] = skill_data
        return skill_data

    def clear_cache(self) -> None:
        """清空缓存"""
        self._skills_cache.clear()
