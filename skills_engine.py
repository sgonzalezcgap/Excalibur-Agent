"""
skills_engine.py — Skill Files Loader & Indexer.

Skills are the "Gold Standard" .md files that document established
migration patterns. The agent MUST strictly adhere to these guidelines.

Skills are loaded from excalibur-agent/skills/*.md with YAML frontmatter.
"""

import os
import re
from pathlib import Path
from typing import Optional
from config import SKILLS_DIR


class Skill:
    """A single migration skill document."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.id = ""
        self.title = ""
        self.category = ""
        self.severity = "medium"  # low, medium, high, critical
        self.symptoms = []
        self.applies_to = []
        self.vb6_pattern = ""
        self.dotnet_fix = ""
        self.content = ""
        self._parse()

    def _parse(self):
        with open(self.file_path, "r", encoding="utf-8") as f:
            raw = f.read()

        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", raw, re.DOTALL)
        if fm_match:
            self._parse_frontmatter(fm_match.group(1))
            self.content = fm_match.group(2).strip()
        else:
            self.content = raw.strip()
            self.id = Path(self.file_path).stem
            self.title = self.id.replace("_", " ").replace("-", " ").title()

    def _parse_frontmatter(self, text: str):
        for line in text.splitlines():
            line = line.strip()
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()

            if key == "id":
                self.id = value
            elif key == "title":
                self.title = value
            elif key == "category":
                self.category = value
            elif key == "severity":
                self.severity = value
            elif key == "symptoms":
                self.symptoms = self._parse_list(value)
            elif key == "applies_to":
                self.applies_to = self._parse_list(value)
            elif key == "vb6_pattern":
                self.vb6_pattern = value
            elif key == "dotnet_fix":
                self.dotnet_fix = value

        if not self.id:
            self.id = Path(self.file_path).stem

    @staticmethod
    def _parse_list(value: str) -> list:
        if value.startswith("["):
            return [s.strip().strip("\"'") for s in value.strip("[]").split(",") if s.strip()]
        return [value] if value else []

    def relevance_score(self, query: str, class_name: str = None) -> int:
        """Calculate relevance score for a query."""
        q = query.lower()
        score = 0

        # Symptom matching (highest weight)
        for s in self.symptoms:
            if s.lower() in q:
                score += 5

        # Title matching
        for word in self.title.lower().split():
            if len(word) > 3 and word in q:
                score += 3

        # Category matching
        if self.category and self.category.lower() in q:
            score += 3

        # Content keyword matching
        for word in q.split():
            if len(word) > 3 and word in self.content.lower():
                score += 1

        # Class-specific boost
        if class_name and self.applies_to:
            if any(class_name.lower() in a.lower() for a in self.applies_to):
                score += 4

        # Severity boost
        severity_boost = {"critical": 3, "high": 2, "medium": 1, "low": 0}
        score += severity_boost.get(self.severity, 0)

        return score

    def to_prompt(self) -> str:
        """Format for LLM prompt injection — full content."""
        header = (
            f"### 📘 Skill: {self.title} [{self.id}]\n"
            f"- **Category**: {self.category}\n"
            f"- **Severity**: {self.severity}\n"
            f"- **Symptoms**: {', '.join(self.symptoms)}\n"
        )
        if self.vb6_pattern:
            header += f"- **VB6 Pattern**: {self.vb6_pattern}\n"
        if self.dotnet_fix:
            header += f"- **.NET Fix**: {self.dotnet_fix}\n"

        return f"{header}\n{self.content}"

    def to_dict(self) -> dict:
        return {
            "id": self.id, "title": self.title, "category": self.category,
            "severity": self.severity, "symptoms": self.symptoms,
            "applies_to": self.applies_to,
        }


class SkillsEngine:
    """Loads, indexes, and queries migration skill files."""

    def __init__(self, skills_dir: str = None):
        self.skills_dir = Path(skills_dir) if skills_dir else SKILLS_DIR
        self.skills: list[Skill] = []

    def load(self) -> int:
        """Load all .md skill files from the skills directory."""
        if not self.skills_dir.is_dir():
            self.skills_dir.mkdir(parents=True, exist_ok=True)
            return 0

        self.skills = []
        for file in sorted(self.skills_dir.iterdir()):
            if file.suffix != ".md":
                continue
            try:
                self.skills.append(Skill(str(file)))
            except Exception as e:
                print(f"  ⚠ Error loading skill {file.name}: {e}")

        return len(self.skills)

    def search(
        self,
        query: str = "",
        class_name: str = None,
        category: str = None,
        max_results: int = 5,
    ) -> list[Skill]:
        """Find relevant skills for a given bug description."""
        candidates = self.skills

        if category:
            cat_match = [s for s in candidates if s.category == category]
            if cat_match:
                candidates = cat_match

        if query or class_name:
            scored = [(s.relevance_score(query, class_name), s) for s in candidates]
            scored.sort(key=lambda x: x[0], reverse=True)
            candidates = [s for score, s in scored if score > 0]

        return candidates[:max_results]

    def get_all_as_context(self) -> str:
        """Return ALL skills formatted for system prompt (Gold Standard)."""
        if not self.skills:
            return ""

        lines = ["## 📘 Migration Skills (Gold Standard)\n",
                 "These are the team's established patterns. STRICTLY adhere to these.\n"]
        for skill in self.skills:
            lines.append(skill.to_prompt())
            lines.append("\n---\n")
        return "\n".join(lines)

    def format_relevant(self, skills: list[Skill], max_items: int = 5) -> str:
        """Format only relevant skills for the prompt."""
        if not skills:
            return "No matching skills found."

        lines = [f"## 📘 Relevant Migration Skills ({len(skills)} matched)\n"]
        for skill in skills[:max_items]:
            lines.append(skill.to_prompt())
            lines.append("\n---\n")
        return "\n".join(lines)

    def get_summary(self) -> str:
        if not self.skills:
            return "📘 No skills loaded. Add .md files to excalibur-agent/skills/"
        lines = [f"📘 {len(self.skills)} skills loaded:\n"]
        by_cat = {}
        for s in self.skills:
            by_cat.setdefault(s.category or "uncategorized", []).append(s)
        for cat, skills in sorted(by_cat.items()):
            lines.append(f"  [{cat}]")
            for s in skills:
                sev_icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(s.severity, "⚪")
                lines.append(f"    {sev_icon} {s.title} ({s.id})")
        return "\n".join(lines)
