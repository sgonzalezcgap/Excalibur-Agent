"""
gap_note_scanner.py — Local Codebase GAP-Note Scanner.

Scans the local Excalibur codebase for //GAP-Note comments.
This is the "live" source of truth — reads directly from the working tree.
"""

import os
import re
import json
from typing import Optional
from config import PROJECT_ROOT, GAP_NOTE_REGEX, SKIP_DIRS, TRUSTED_AUTHORS


class GapNoteScanner:
    """Scans local .cs files for GAP-Note comments and indexes them."""

    def __init__(self):
        self.pattern = re.compile(GAP_NOTE_REGEX, re.IGNORECASE)
        self.notes = []

    def scan(self, class_filter: str = None, verbose: bool = False) -> list:
        """
        Scan the entire codebase for GAP-Note comments.

        Args:
            class_filter: If set, only scan files containing this class name
            verbose: Print progress
        """
        self.notes = []
        file_count = 0

        for root, dirs, files in os.walk(PROJECT_ROOT):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for file in files:
                if not file.endswith(".cs"):
                    continue
                if class_filter and class_filter.lower() not in file.lower():
                    continue

                filepath = os.path.join(root, file)
                file_count += 1

                try:
                    with open(filepath, "r", encoding="utf-8-sig") as f:
                        for line_num, line in enumerate(f, 1):
                            match = self.pattern.search(line)
                            if match:
                                author = match.group(1)
                                description = match.group(2).strip()
                                rel_path = os.path.relpath(filepath, PROJECT_ROOT)

                                self.notes.append({
                                    "file": rel_path,
                                    "line": line_num,
                                    "author": author,
                                    "description": description,
                                    "confidence": "high" if author.lower() in [a.lower() for a in TRUSTED_AUTHORS] else "medium",
                                    "class_name": file.replace(".Designer.cs", "").replace(".cs", ""),
                                    "raw_line": line.rstrip(),
                                })
                except Exception:
                    pass

        if verbose:
            print(f"  📝 Scanned {file_count} files, found {len(self.notes)} GAP-Notes")

        return self.notes

    def search(
        self,
        query: str = "",
        class_name: Optional[str] = None,
        author: Optional[str] = None,
        keyword: Optional[str] = None,
        max_results: int = 20,
    ) -> list:
        """Search GAP-Notes by various criteria."""
        results = self.notes

        if class_name:
            cls_lower = class_name.lower()
            same = [n for n in results if cls_lower in n.get("class_name", "").lower()]
            other = [n for n in results if cls_lower not in n.get("class_name", "").lower()]
            results = same + other

        if author:
            results = [n for n in results if author.lower() in n.get("author", "").lower()]

        if keyword:
            results = [n for n in results if keyword.lower() in n.get("description", "").lower()]

        if query:
            words = query.lower().split()
            scored = []
            for n in results:
                text = f"{n.get('description', '')} {n.get('file', '')} {n.get('raw_line', '')}".lower()
                score = sum(1 for w in words if w in text)
                if n.get("confidence") == "high":
                    score += 1
                if score > 0:
                    scored.append((score, n))
            scored.sort(key=lambda x: x[0], reverse=True)
            results = [n for _, n in scored]

        return results[:max_results]

    def get_by_class(self, class_name: str) -> list:
        """Get all GAP-Notes for a specific class."""
        return [n for n in self.notes if class_name.lower() in n.get("class_name", "").lower()]

    def get_by_author(self, author: str) -> list:
        """Get all GAP-Notes by a specific author."""
        return [n for n in self.notes if author.lower() == n.get("author", "").lower()]

    def format_for_prompt(self, notes: list, max_items: int = 15) -> str:
        """Format GAP-Notes for LLM prompt injection."""
        if not notes:
            return "No local GAP-Notes found for this context."

        lines = [f"## Local GAP-Notes ({len(notes)} found)\n"]
        for n in notes[:max_items]:
            conf = "🟢" if n.get("confidence") == "high" else "🟡"
            lines.append(
                f"- {conf} `{n['file']}:{n['line']}` — **{n['author']}**: {n['description']}"
            )
        return "\n".join(lines)

    def get_summary(self) -> str:
        """Return a summary of scanned GAP-Notes."""
        if not self.notes:
            return "No GAP-Notes scanned yet. Run scan() first."

        by_author = {}
        by_class = {}
        for n in self.notes:
            by_author.setdefault(n["author"], []).append(n)
            by_class.setdefault(n["class_name"], []).append(n)

        lines = [f"📝 {len(self.notes)} GAP-Notes in codebase\n"]
        lines.append("By author:")
        for author, notes in sorted(by_author.items(), key=lambda x: -len(x[1])):
            lines.append(f"  {author}: {len(notes)}")
        lines.append("\nTop classes:")
        for cls, notes in sorted(by_class.items(), key=lambda x: -len(x[1]))[:10]:
            lines.append(f"  {cls}: {len(notes)}")

        return "\n".join(lines)
