"""
repo_sync.py — Repository Synchronization Module.

Handles the --sync-repo flag: fetches latest commits, diffs, and GAP-Notes
from the Excalibur Modernized GitHub repository to ensure the agent's
knowledge base is up to date.

Uses GitHub REST API with GITHUB_TOKEN.
"""

import os
import re
import json
import time
import requests
from typing import Optional
from config import GAP_NOTE_REGEX, KNOWLEDGE_CACHE, TRUSTED_AUTHORS

GITHUB_API = "https://api.github.com"


class RepoSync:
    """Synchronizes knowledge from the remote GitHub repository."""

    def __init__(self, token: str, repo: str):
        """
        Args:
            token: GitHub personal access token or gh auth token
            repo: owner/repo (e.g. 'myorg/Excalibur_Modernized')
        """
        self.token = token
        self.repo = repo
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        self.diff_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3.diff",
        }
        self.gap_pattern = re.compile(GAP_NOTE_REGEX, re.MULTILINE | re.IGNORECASE)
        self.cache = {"fixes": [], "last_sync": None, "repo": repo}

    def _get(self, url: str, headers: dict = None, params: dict = None) -> requests.Response:
        """GET with rate-limit handling."""
        h = headers or self.headers
        resp = requests.get(url, headers=h, params=params, timeout=30)
        if resp.status_code == 403 and "rate limit" in resp.text.lower():
            reset = int(resp.headers.get("X-RateLimit-Reset", time.time() + 60))
            wait = max(reset - int(time.time()), 1)
            print(f"  ⏳ Rate limit hit, waiting {wait}s...")
            time.sleep(wait)
            return self._get(url, headers, params)
        return resp

    # ─── PR Scanning ──────────────────────────────────────

    def fetch_merged_prs(
        self,
        base_branch: Optional[str] = None,
        max_prs: int = 50,
    ) -> list:
        """Fetch merged PRs from the repository."""
        prs = []
        page = 1
        per_page = min(max_prs, 100)

        while len(prs) < max_prs:
            params = {
                "state": "closed", "per_page": per_page, "page": page,
                "sort": "updated", "direction": "desc",
            }
            if base_branch:
                params["base"] = base_branch

            resp = self._get(f"{GITHUB_API}/repos/{self.repo}/pulls", params=params)
            if resp.status_code != 200:
                print(f"  ❌ Error listing PRs: {resp.status_code} — {resp.text[:200]}")
                break

            batch = resp.json()
            if not batch:
                break

            for pr in batch:
                if not pr.get("merged_at"):
                    continue
                prs.append({
                    "number": pr["number"],
                    "title": pr["title"],
                    "body": (pr.get("body") or "")[:500],
                    "author": pr["user"]["login"],
                    "merged_at": pr["merged_at"],
                    "base": pr["base"]["ref"],
                    "head": pr["head"]["ref"],
                    "url": pr["html_url"],
                })

            if len(batch) < per_page:
                break
            page += 1

        return prs[:max_prs]

    def fetch_pr_diff(self, pr_number: int) -> str:
        """Get the unified diff of a PR."""
        resp = self._get(
            f"{GITHUB_API}/repos/{self.repo}/pulls/{pr_number}",
            headers=self.diff_headers,
        )
        return resp.text if resp.status_code == 200 else ""

    # ─── Latest Commits ──────────────────────────────────

    def fetch_latest_commits(self, branch: str = "main", count: int = 20) -> list:
        """Fetch latest commits to check for new GAP-Notes."""
        resp = self._get(
            f"{GITHUB_API}/repos/{self.repo}/commits",
            params={"sha": branch, "per_page": count},
        )
        if resp.status_code != 200:
            return []

        commits = []
        for c in resp.json():
            commits.append({
                "sha": c["sha"][:8],
                "message": c["commit"]["message"].split("\n")[0],
                "author": c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
            })
        return commits

    # ─── GAP-Note Extraction ─────────────────────────────

    def extract_gap_notes_from_diff(self, diff_text: str, pr_info: dict) -> list:
        """Parse a diff and extract all GAP-Note occurrences with context."""
        fixes = []
        current_file = None
        hunk_lines = []
        hunk_start = 0

        for line in diff_text.splitlines():
            if line.startswith("diff --git"):
                if current_file and hunk_lines:
                    fixes.extend(self._process_hunk(current_file, hunk_lines, hunk_start, pr_info))
                    hunk_lines = []
                m = re.search(r"b/(.+)$", line)
                current_file = m.group(1) if m else None

            elif line.startswith("@@"):
                if current_file and hunk_lines:
                    fixes.extend(self._process_hunk(current_file, hunk_lines, hunk_start, pr_info))
                hunk_lines = []
                m = re.search(r"\+(\d+)", line)
                hunk_start = int(m.group(1)) if m else 0

            else:
                hunk_lines.append(line)

        if current_file and hunk_lines:
            fixes.extend(self._process_hunk(current_file, hunk_lines, hunk_start, pr_info))

        return fixes

    def _process_hunk(self, file_path: str, lines: list, start: int, pr_info: dict) -> list:
        """Extract GAP-Note fixes from a single diff hunk."""
        hunk_text = "\n".join(lines)
        matches = list(self.gap_pattern.finditer(hunk_text))
        if not matches:
            return []

        added = [l[1:] for l in lines if l.startswith("+")]
        removed = [l[1:] for l in lines if l.startswith("-")]

        fixes = []
        for m in matches:
            author = m.group(1)
            description = m.group(2).strip()

            # Determine confidence based on trusted authors
            confidence = "high" if author.lower() in [a.lower() for a in TRUSTED_AUTHORS] else "medium"

            fix = {
                "file": file_path,
                "class_name": self._class_from_path(file_path),
                "pr_number": pr_info["number"],
                "pr_title": pr_info["title"],
                "pr_url": pr_info["url"],
                "author": author,
                "description": description,
                "confidence": confidence,
                "lines_added": added[:20],
                "lines_removed": removed[:20],
                "context": hunk_text[:2000],
                "category": self._categorize(description, hunk_text),
            }
            fixes.append(fix)

        return fixes

    @staticmethod
    def _class_from_path(path: str) -> str:
        from pathlib import Path as P
        name = P(path).stem.replace(".Designer", "")
        return name

    @staticmethod
    def _categorize(description: str, context: str) -> str:
        """Auto-categorize a fix based on keywords."""
        text = (description + " " + context).lower()
        categories = {
            "form_load_timing": ["form_load", "createinstance", "onload", "load event"],
            "dbvariant_cast": ["dbvariant", "iconvertible", "invalidcastexception", ".value", "getprimitivevalue"],
            "backcolor_visual": ["backcolor", "fromargb", "192, 255, 255", "celeste", "cyan"],
            "commandbutton_image": ["commandbuttonhelper", "setmaskcolor", "silver", "button image"],
            "control_sizing": ["size", "minimumsize", "text cut", "truncated"],
            "treeview_migration": ["selectednodes", "selectednode", "treeview", "imagelist"],
            "ole_parameters": ["oleparametershelper", "commandtype", "storedprocedure", "addwithvalue"],
            "field_helper": ["fieldhelper", "extract value", "compare as double"],
            "compilation_fix": ["error cs", "cs0234", "cs1615", "cs0571"],
        }
        best, best_score = "general_migration", 0
        for cat, keywords in categories.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best, best_score = cat, score
        return best

    # ─── Full Sync ───────────────────────────────────────

    def sync(
        self,
        max_prs: int = 50,
        base_branch: Optional[str] = None,
        verbose: bool = True,
    ) -> dict:
        """
        Full repository sync: fetch PRs, extract GAP-Notes, build knowledge.

        Returns summary dict.
        """
        if verbose:
            print(f"\n🔄 SYNC: Fetching data from {self.repo}...")

        # 1. Latest commits
        if verbose:
            print(f"  📋 Checking latest commits...")
        commits = self.fetch_latest_commits(branch=base_branch or "main")
        if verbose and commits:
            print(f"     Latest: {commits[0]['sha']} — {commits[0]['message'][:60]}")

        # 2. Merged PRs
        if verbose:
            print(f"  📋 Fetching merged PRs (max {max_prs})...")
        prs = self.fetch_merged_prs(base_branch=base_branch, max_prs=max_prs)
        if verbose:
            print(f"     Found {len(prs)} merged PRs")

        # 3. Extract GAP-Notes from each PR
        all_fixes = []
        for i, pr in enumerate(prs):
            if verbose:
                print(f"  🔍 [{i+1}/{len(prs)}] PR #{pr['number']}: {pr['title'][:50]}")
            diff = self.fetch_pr_diff(pr["number"])
            if diff:
                fixes = self.extract_gap_notes_from_diff(diff, pr)
                all_fixes.extend(fixes)
                if verbose and fixes:
                    print(f"     ✅ {len(fixes)} GAP-Notes extracted")

        # 4. Save to cache
        self.cache = {
            "repo": self.repo,
            "last_sync": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_prs_scanned": len(prs),
            "total_fixes": len(all_fixes),
            "fixes": all_fixes,
        }
        with open(KNOWLEDGE_CACHE, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=2, ensure_ascii=False)

        if verbose:
            print(f"\n  {'='*50}")
            print(f"  ✅ SYNC COMPLETE: {len(all_fixes)} GAP-Note fixes from {len(prs)} PRs")
            print(f"  💾 Saved to {KNOWLEDGE_CACHE}")
            print(f"  {'='*50}\n")

        return self.cache

    def load_cache(self) -> bool:
        """Load previously synced knowledge from cache."""
        if not KNOWLEDGE_CACHE.is_file():
            return False
        try:
            with open(KNOWLEDGE_CACHE, "r", encoding="utf-8") as f:
                self.cache = json.load(f)
            return True
        except Exception:
            return False

    def search_fixes(
        self,
        query: str = "",
        class_name: str = None,
        category: str = None,
        max_results: int = 10,
    ) -> list:
        """Search the cached fixes by query, class, or category."""
        fixes = self.cache.get("fixes", [])

        if class_name:
            cls_lower = class_name.lower()
            # Prioritize same-class fixes
            same = [f for f in fixes if cls_lower in f.get("class_name", "").lower()]
            other = [f for f in fixes if cls_lower not in f.get("class_name", "").lower()]
            fixes = same + other

        if category:
            cat_fixes = [f for f in fixes if f.get("category") == category]
            if cat_fixes:
                fixes = cat_fixes

        if query:
            words = query.lower().split()
            scored = []
            for f in fixes:
                text = " ".join([
                    f.get("description", ""), f.get("context", ""),
                    f.get("pr_title", ""), f.get("file", ""),
                ]).lower()
                score = sum(1 for w in words if w in text)
                # Boost high-confidence fixes
                if f.get("confidence") == "high":
                    score += 2
                if score > 0:
                    scored.append((score, f))
            scored.sort(key=lambda x: x[0], reverse=True)
            fixes = [f for _, f in scored]

        return fixes[:max_results]

    def format_for_prompt(self, fixes: list, max_items: int = 5) -> str:
        """Format fixes for inclusion in the LLM system prompt (compact)."""
        if not fixes:
            return "No historical fixes found matching this context."

        lines = [f"## Historical Fixes ({min(len(fixes), max_items)} of {len(fixes)})\n"]
        for i, f in enumerate(fixes[:max_items]):
            conf_icon = "🟢" if f.get("confidence") == "high" else "🟡"
            lines.append(f"### {conf_icon} Fix #{i+1} — PR #{f.get('pr_number')} [{f.get('category')}]")
            lines.append(f"- **File**: `{f.get('file', '?')}` | **Author**: {f.get('author', '?')}")
            lines.append(f"- **GAP-Note**: {f.get('description', '?')}")
            added = f.get("lines_added", [])
            removed = f.get("lines_removed", [])
            if removed or added:
                lines.append("```diff")
                for r in removed[:4]:
                    lines.append(f"- {r}")
                for a in added[:4]:
                    lines.append(f"+ {a}")
                lines.append("```")
            lines.append("")
        return "\n".join(lines)
