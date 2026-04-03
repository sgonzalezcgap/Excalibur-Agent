"""
forensic_agent.py — Excalibur Forensic Migration Agent.

System Role: Lead Forensic Migration Engineer for the "Excalibur Modernized" project.
Specializes in VB6 → .NET (C#) migration debugging with autonomous problem-solving.

Knowledge Sources:
  1. Repository PRs (GAP-Note extraction via GitHub API)
  2. Skill Files (.md Gold Standard migration patterns)
  3. Local Codebase (live GAP-Note scanning)

Response Structure:
  1. Root Cause Analysis
  2. Historical Reference (GAP-Note / Skill citation)
  3. Proposed Fix (C# code block with comments)
  4. Verification Steps
"""

import os
import re
import json
import base64
import subprocess
from pathlib import Path
from openai import OpenAI, BadRequestError

from config import (
    PROJECT_ROOT, BUILD_PROJECT, SKIP_DIRS, GAP_NOTE_REGEX,
    GITHUB_MODELS_ENDPOINT, DEFAULT_MODEL, MIGRATION_CONTEXT, VB6_TO_DOTNET_TYPES,
)
from repo_sync import RepoSync
from gap_note_scanner import GapNoteScanner
from skills_engine import SkillsEngine


# ─────────────────────────────────────────────
# TOKEN LIMITS — truncation thresholds (chars)
# ─────────────────────────────────────────────

MAX_READ_FILE_CHARS = 3000
MAX_SEARCH_CODE_CHARS = 2000
MAX_COMPILE_CHARS = 1500
MAX_GAP_NOTES_CHARS = 1500
MAX_VB6_PATTERN_CHARS = 800
COMPACT_AFTER_ITERATIONS = 8


def _truncate(text: str, limit: int, label: str = "output") -> str:
    """Truncate text and append a notice if over the limit."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... [{label} truncated — {len(text)} total chars, showing first {limit}]"


# ─────────────────────────────────────────────
# TOOLS — Operations the agent can perform
# ─────────────────────────────────────────────

# Session-level file read cache: path → (content_hash, iteration)
_read_cache: dict[str, tuple[int, int]] = {}
_current_iteration = 0


def tool_read_file(path: str, start_line: int = None, end_line: int = None) -> str:
    """Read a file from the project. Optionally a line range."""
    global _read_cache, _current_iteration
    full = path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)
    try:
        with open(full, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()

        # If reading the full file (no range) and we already read it, return summary
        if not start_line and not end_line and full in _read_cache:
            prev_len, prev_iter = _read_cache[full]
            if prev_len == len(lines):
                return (
                    f"[Cached] Already read {path} in iteration {prev_iter} "
                    f"({len(lines)} lines, unchanged). Use start_line/end_line to read a specific section."
                )

        if start_line and end_line:
            sel = lines[max(0, start_line - 1) : end_line]
            result = "".join(f"{start_line + i}: {l}" for i, l in enumerate(sel))
        elif len(lines) > 200:
            result = "".join(f"{i+1}: {l}" for i, l in enumerate(lines))
        else:
            result = "".join(lines)

        # Cache full reads
        if not start_line and not end_line:
            _read_cache[full] = (len(lines), _current_iteration)

        return _truncate(result, MAX_READ_FILE_CHARS, f"file {path}")
    except Exception as e:
        return f"Error: {e}"


def tool_edit_file(path: str, old_text: str, new_text: str) -> str:
    """Edit a file by replacing old_text with new_text (single occurrence)."""
    full = path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)
    try:
        with open(full, "r", encoding="utf-8-sig") as f:
            content = f.read()
        if old_text not in content:
            return f"Error: old_text not found in {path}. Verify exact whitespace and context."
        if content.count(old_text) > 1:
            return f"Ambiguous: old_text found {content.count(old_text)} times. Add more surrounding context lines."
        content = content.replace(old_text, new_text, 1)
        with open(full, "w", encoding="utf-8-sig") as f:
            f.write(content)
        return f"OK: {path} edited successfully."
    except Exception as e:
        return f"Error: {e}"


def tool_search_code(pattern: str, file_extension: str = ".cs", max_results: int = 15) -> str:
    """Search for a regex pattern across project files."""
    results = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file in files:
            if not file.endswith(file_extension):
                continue
            fpath = os.path.join(root, file)
            try:
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    for i, line in enumerate(f, 1):
                        if re.search(pattern, line, re.IGNORECASE):
                            rel = os.path.relpath(fpath, PROJECT_ROOT)
                            results.append(f"{rel}:{i}: {line.rstrip()}")
                            if len(results) >= max_results:
                                out = "\n".join(results)
                                return _truncate(out, MAX_SEARCH_CODE_CHARS, "search results")
            except Exception:
                pass
    out = "\n".join(results) if results else "No matches found."
    return _truncate(out, MAX_SEARCH_CODE_CHARS, "search results")


def tool_find_class_files(class_name: str) -> str:
    """Find all files (.cs, .Designer.cs, .resX) associated with a class."""
    results = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file in files:
            if class_name.lower() in file.lower() and file.endswith((".cs", ".resX", ".resx")):
                rel = os.path.relpath(os.path.join(root, file), PROJECT_ROOT)
                size = os.path.getsize(os.path.join(root, file))
                results.append(f"{rel} ({size:,} bytes)")
    return "\n".join(sorted(results)) if results else f"No files found for '{class_name}'"


def tool_search_gap_notes(class_name: str = None, keyword: str = None) -> str:
    """Search for //GAP-Note comments in the local codebase."""
    scanner = GapNoteScanner()
    scanner.scan(class_filter=class_name)
    results = scanner.search(query=keyword or "", class_name=class_name, keyword=keyword)
    out = scanner.format_for_prompt(results) if results else "No GAP-Notes found matching criteria."
    return _truncate(out, MAX_GAP_NOTES_CHARS, "GAP-Notes")


def tool_compile_project() -> str:
    """Compile the .NET project and return CS errors if any."""
    try:
        result = subprocess.run(
            ["dotnet", "build", str(BUILD_PROJECT)],
            capture_output=True, text=True, timeout=120, cwd=str(PROJECT_ROOT),
        )
        errors = [l for l in result.stdout.splitlines() if "error CS" in l]
        warnings = [l for l in result.stdout.splitlines() if "warning CS" in l]
        if not errors:
            return f"✅ BUILD SUCCEEDED — 0 errors, {len(warnings)} warnings."
        out = "❌ BUILD FAILED:\n" + "\n".join(errors)
        return _truncate(out, MAX_COMPILE_CHARS, "build output")
    except Exception as e:
        return f"Compilation error: {e}"


def tool_search_vb6_pattern(keyword: str) -> str:
    """Search for VB6 migration patterns and their .NET equivalents."""
    matches = []
    for vb6_type, dotnet_type in VB6_TO_DOTNET_TYPES.items():
        if keyword.lower() in vb6_type.lower() or keyword.lower() in dotnet_type.lower():
            matches.append(f"  VB6 `{vb6_type}` → .NET `{dotnet_type}`")
    parts = []
    if matches:
        parts.append("Type mappings:\n" + "\n".join(matches))
    parts.append(f"DbVariant<T>: .Value returns boxed T, .IsNull checks null, no IConvertible")
    return _truncate("\n".join(parts), MAX_VB6_PATTERN_CHARS, "VB6 patterns")


# ─── Tool Dispatch ────────────────────────────

TOOL_DISPATCH = {
    "read_file":          lambda a: tool_read_file(a["path"], a.get("start_line"), a.get("end_line")),
    "edit_file":          lambda a: tool_edit_file(a["path"], a["old_text"], a["new_text"]),
    "search_code":        lambda a: tool_search_code(a["pattern"], a.get("file_extension", ".cs"), a.get("max_results", 25)),
    "find_class_files":   lambda a: tool_find_class_files(a["class_name"]),
    "search_gap_notes":   lambda a: tool_search_gap_notes(a.get("class_name"), a.get("keyword")),
    "compile_project":    lambda a: tool_compile_project(),
    "search_vb6_pattern": lambda a: tool_search_vb6_pattern(a["keyword"]),
}


def execute_tool(name: str, args: dict) -> str:
    try:
        return TOOL_DISPATCH[name](args)
    except Exception as e:
        return f"Tool error ({name}): {e}"


# ─── Tool Definitions (OpenAI format) ────────

TOOLS = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a project file. Can read a specific line range for large files.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Relative or absolute path to the file"},
            "start_line": {"type": "integer", "description": "Start line (1-based, optional)"},
            "end_line": {"type": "integer", "description": "End line (inclusive, optional)"},
        }, "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "edit_file",
        "description": "Edit a file by replacing old_text with new_text. old_text must be unique. Include 3+ lines of surrounding context.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Path to the file"},
            "old_text": {"type": "string", "description": "Exact literal text to replace (with context lines)"},
            "new_text": {"type": "string", "description": "New text to insert"},
        }, "required": ["path", "old_text", "new_text"]},
    }},
    {"type": "function", "function": {
        "name": "search_code",
        "description": "Search for a regex pattern across project files.",
        "parameters": {"type": "object", "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search"},
            "file_extension": {"type": "string", "description": "File extension filter (.cs, .resX)"},
            "max_results": {"type": "integer", "description": "Max results to return"},
        }, "required": ["pattern"]},
    }},
    {"type": "function", "function": {
        "name": "find_class_files",
        "description": "Find all files (.cs, .Designer.cs, .resX) for a given class/form name.",
        "parameters": {"type": "object", "properties": {
            "class_name": {"type": "string", "description": "Class or form name"},
        }, "required": ["class_name"]},
    }},
    {"type": "function", "function": {
        "name": "search_gap_notes",
        "description": "Search for //GAP-Note comments in the codebase. These are the primary source of truth for established fixes.",
        "parameters": {"type": "object", "properties": {
            "class_name": {"type": "string", "description": "Filter by class name"},
            "keyword": {"type": "string", "description": "Filter by keyword in the note"},
        }},
    }},
    {"type": "function", "function": {
        "name": "compile_project",
        "description": "Compile the .NET project with 'dotnet build' and return any CS errors.",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "search_vb6_pattern",
        "description": "Search VB6-to-.NET type mappings and migration context for a keyword.",
        "parameters": {"type": "object", "properties": {
            "keyword": {"type": "string", "description": "VB6 or .NET type/pattern to look up"},
        }, "required": ["keyword"]},
    }},
]


# ─────────────────────────────────────────────
# SYSTEM PROMPT — Forensic Migration Engineer
# ─────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = """# Excalibur Migration Agent

You are the Lead Forensic Migration Engineer for "Excalibur Modernized" (VB6 → C# .NET 9 WinForms).

## Key Facts
- Migration tool: VBUC. DB: OLE DB via UpgradeHelpers.DB. Grid: C1TrueDBGrid.
- `DbVariant<T>`: `.Value` returns boxed T, `.IsNull` checks null, NOT IConvertible.
- VB6 Integer=short, Long=int, Single=float, Variant=object/DbVariant<T>, Date=DateTime.
- Legacy color: `Color.FromArgb(192, 255, 255)` (VB6 celeste/cyan).
- GAP-Note format: `// GAP-Note. author, description`

## Workflow (MANDATORY)
1. **Investigate**: Use read_file (with line ranges for big files), search_code, find_class_files, search_gap_notes.
2. **Analyze**: Identify root cause. Cite matching GAP-Note or Skill if found.
3. **Fix**: ALWAYS use `edit_file` tool — do NOT just print code. Add `// GAP-Note. agente, desc` on changed lines.
4. **Verify**: ALWAYS call `compile_project` after edits. If errors, fix them.

## Response Format
### 1. Root Cause Analysis
(Exception type, why it fails, VB6→C# mismatch)
### 2. Historical Reference
(Cite GAP-Note/Skill or "No prior reference")
### 3. Proposed Fix
(Use edit_file tool — user sees diff + Y/N prompt)
### 4. Verification
(compile_project result)

{skills_context}

{historical_fixes_context}

{local_gap_notes_context}
"""


# ─────────────────────────────────────────────
# AGENT CLASS
# ─────────────────────────────────────────────

class ForensicAgent:
    """
    Excalibur Forensic Migration Agent.

    Autonomous debugging agent that combines:
    - Repository PR history (via --sync-repo)
    - Gold Standard skill files
    - Local codebase GAP-Notes
    - LLM reasoning with tool use

    Token-efficiency features:
    - Tool response truncation (MAX_*_CHARS constants)
    - File read caching (avoids re-reading unchanged files)
    - Conversation compaction (every COMPACT_AFTER_ITERATIONS turns)
    - Auto-recovery on context-length errors (compact + retry)
    - Token usage tracking per iteration
    """

    def __init__(
        self,
        token: str = None,
        model: str = DEFAULT_MODEL,
        repo: str = None,
    ):
        # Resolve token
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        if not self.token:
            try:
                r = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
                self.token = r.stdout.strip()
            except Exception:
                pass
        if not self.token:
            raise ValueError(
                "GITHUB_TOKEN not found.\n"
                "  Option 1: $env:GITHUB_TOKEN = (gh auth token)\n"
                "  Option 2: $env:GITHUB_TOKEN = 'ghp_YOUR_TOKEN'\n"
                "  Option 3: Add it to excalibur-agent\\.env file"
            )

        # LLM
        self.client = OpenAI(base_url=GITHUB_MODELS_ENDPOINT, api_key=self.token)
        self.model = model
        self.messages = []

        # Knowledge sources
        self.repo = repo
        self.skills_engine = SkillsEngine()
        self.gap_scanner = GapNoteScanner()
        self.repo_sync = RepoSync(self.token, repo) if repo else None

        # Token tracking
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

    def initialize_knowledge(
        self,
        sync_repo: bool = False,
        max_prs: int = 50,
        base_branch: str = None,
        verbose: bool = True,
    ):
        """Load all three knowledge sources."""
        if verbose:
            print("\n" + "="*60)
            print("  📚 KNOWLEDGE INITIALIZATION")
            print("="*60)

        # 1. Skills (Gold Standard)
        n_skills = self.skills_engine.load()
        if verbose:
            print(f"\n  📘 Skills (Gold Standard): {n_skills} loaded")
            if n_skills:
                print(self.skills_engine.get_summary())

        # 2. Repository sync
        if sync_repo and self.repo_sync:
            self.repo_sync.sync(max_prs=max_prs, base_branch=base_branch, verbose=verbose)
        elif self.repo_sync:
            if self.repo_sync.load_cache():
                n = len(self.repo_sync.cache.get("fixes", []))
                if verbose:
                    print(f"\n  📋 Repository cache: {n} fixes (last sync: {self.repo_sync.cache.get('last_sync', '?')})")
            elif verbose:
                print(f"\n  📋 Repository: No cache found. Use --sync-repo to scan PRs.")

        # 3. Local GAP-Notes
        notes = self.gap_scanner.scan(verbose=verbose)
        if verbose:
            print(f"  📝 Local GAP-Notes: {len(notes)} found")

        if verbose:
            print("\n" + "="*60 + "\n")

    def _build_system_prompt(self, class_name: str, description: str) -> str:
        """Build the complete system prompt with injected knowledge (token-efficient)."""

        # Only top 3 relevant skills (was 5)
        relevant_skills = self.skills_engine.search(query=description, class_name=class_name, max_results=3)
        skills_ctx = self.skills_engine.format_relevant(relevant_skills, max_items=3) if relevant_skills else ""

        # Only top 5 historical fixes from PRs (was 8)
        hist_ctx = ""
        if self.repo_sync:
            hist_fixes = self.repo_sync.search_fixes(query=description, class_name=class_name, max_results=5)
            if hist_fixes:
                hist_ctx = self.repo_sync.format_for_prompt(hist_fixes, max_items=5)

        # Only top 10 local GAP-Notes for this class (was 15)
        local_notes = self.gap_scanner.get_by_class(class_name)
        local_ctx = self.gap_scanner.format_for_prompt(local_notes, max_items=10) if local_notes else ""

        return SYSTEM_PROMPT_TEMPLATE.format(
            skills_context=skills_ctx,
            historical_fixes_context=hist_ctx,
            local_gap_notes_context=local_ctx,
        )

    def _build_user_message(
        self,
        description: str,
        class_name: str,
        error_line: str = None,
        expected_result: str = None,
        screenshot_error: str = None,
        screenshot_callstack: str = None,
        screenshot_legacy: str = None,
    ) -> list:
        """Build the user message with text and images."""
        content = []

        # Images with short labels
        image_inputs = [
            (screenshot_error, "Runtime error screenshot"),
            (screenshot_callstack, "Callstack screenshot"),
            (screenshot_legacy, "Expected result / legacy VB6 screenshot"),
        ]

        for img_path, label in image_inputs:
            if img_path and os.path.isfile(img_path):
                ext = Path(img_path).suffix.lower().lstrip(".")
                mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "gif": "image/gif"}.get(ext, "image/png")
                with open(img_path, "rb") as f:
                    b64 = base64.standard_b64encode(f.read()).decode()
                content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
                content.append({"type": "text", "text": f"^ {label}"})

        # Compact bug report
        report = f"**Class**: `{class_name}` | **Bug**: {description}"
        if error_line:
            report += f" | **Error Line**: `{error_line}`"
        if expected_result:
            report += f" | **Expected**: {expected_result}"
        report += "\n\nInvestigate, fix via edit_file, then compile."

        content.append({"type": "text", "text": report})
        return content

    def _compact_messages(self):
        """
        Compact the conversation to free tokens.

        Keeps: system prompt, user prompt, last 4 messages.
        Summarizes everything in between into a single assistant note.
        """
        if len(self.messages) <= 6:
            return  # Too short to compact

        system = self.messages[0]
        user = self.messages[1]
        # Keep last 4 messages (recent context)
        recent = self.messages[-4:]
        # Summarize middle messages
        middle = self.messages[2:-4]

        tool_calls_made = []
        edits_made = []
        compile_results = []
        files_read = []

        for m in middle:
            role = m.get("role", "")
            if role == "assistant":
                # Extract tool call names
                tcs = m.get("tool_calls", [])
                for tc in tcs:
                    fn = tc.get("function", {})
                    name = fn.get("name", "?")
                    try:
                        args = json.loads(fn.get("arguments", "{}"))
                    except Exception:
                        args = {}
                    if name == "read_file":
                        files_read.append(args.get("path", "?"))
                    elif name == "edit_file":
                        edits_made.append(args.get("path", "?"))
                    elif name == "compile_project":
                        pass  # captured from tool results
                    else:
                        tool_calls_made.append(f"{name}({json.dumps(args, ensure_ascii=False)[:60]})")
            elif role == "tool":
                content = m.get("content", "")
                if "BUILD SUCCEEDED" in content:
                    compile_results.append("✅ passed")
                elif "BUILD FAILED" in content:
                    compile_results.append("❌ failed")

        summary_parts = ["[Conversation compacted to save tokens]"]
        if files_read:
            summary_parts.append(f"Files read: {', '.join(set(files_read))}")
        if tool_calls_made:
            summary_parts.append(f"Tools used: {'; '.join(tool_calls_made[:8])}")
        if edits_made:
            summary_parts.append(f"Files edited: {', '.join(set(edits_made))}")
        if compile_results:
            summary_parts.append(f"Build results: {', '.join(compile_results)}")

        compact_msg = {"role": "assistant", "content": "\n".join(summary_parts)}
        self.messages = [system, user, compact_msg] + recent
        print(f"  🗜️ Conversation compacted: {len(middle)} messages → 1 summary")

    def run(
        self,
        description: str,
        class_name: str,
        error_line: str = None,
        expected_result: str = None,
        screenshot_error: str = None,
        screenshot_callstack: str = None,
        screenshot_legacy: str = None,
        auto_apply: bool = False,
        max_iterations: int = 15,
    ):
        """Main agentic loop with token-efficiency optimizations."""
        global _read_cache, _current_iteration
        _read_cache = {}  # Reset per-session cache
        _current_iteration = 0

        system_prompt = self._build_system_prompt(class_name, description)
        user_content = self._build_user_message(
            description, class_name, error_line, expected_result,
            screenshot_error, screenshot_callstack, screenshot_legacy,
        )

        self.messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # Summary
        n_skills = len(self.skills_engine.search(query=description, class_name=class_name, max_results=3))
        n_repo = len(self.repo_sync.search_fixes(query=description, class_name=class_name, max_results=5)) if self.repo_sync else 0
        n_local = len(self.gap_scanner.get_by_class(class_name))

        print(f"\n{'='*60}")
        print(f"  🔬 FORENSIC MIGRATION AGENT")
        print(f"  Target: {class_name} | Bug: {description}")
        if error_line:
            print(f"  Error Line: {error_line}")
        if expected_result:
            print(f"  Expected: {expected_result}")
        print(f"  Model: {self.model} | Max iterations: {max_iterations}")
        print(f"  Knowledge: {n_skills} skills | {n_repo} PR fixes | {n_local} local GAP-Notes")
        imgs = []
        if screenshot_error: imgs.append("error")
        if screenshot_callstack: imgs.append("callstack")
        if screenshot_legacy: imgs.append("legacy")
        print(f"  Images: {', '.join(imgs) if imgs else 'none'}")
        print(f"{'='*60}\n")

        iteration = 0
        self.total_prompt_tokens = 0
        self.total_completion_tokens = 0

        for iteration in range(1, max_iterations + 1):
            _current_iteration = iteration
            print(f"\n--- Iteration {iteration}/{max_iterations} ---")

            # Compact conversation periodically
            if iteration > 1 and (iteration - 1) % COMPACT_AFTER_ITERATIONS == 0:
                self._compact_messages()

            # API call with error recovery
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=TOOLS,
                    max_tokens=4096,
                )
            except BadRequestError as e:
                err_msg = str(e)
                if "context_length" in err_msg or "too long" in err_msg.lower() or "maximum" in err_msg.lower():
                    print(f"\n⚠️ Context too long — auto-compacting conversation...")
                    self._compact_messages()
                    try:
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=self.messages,
                            tools=TOOLS,
                            max_tokens=4096,
                        )
                    except Exception as e2:
                        print(f"\n❌ API Error after compaction: {e2}")
                        break
                else:
                    print(f"\n❌ API Error: {e}")
                    break
            except Exception as e:
                print(f"\n❌ API Error: {e}")
                break

            # Track token usage
            if response.usage:
                self.total_prompt_tokens += response.usage.prompt_tokens
                self.total_completion_tokens += response.usage.completion_tokens
                print(f"  📊 Tokens: {response.usage.prompt_tokens:,} in / {response.usage.completion_tokens:,} out (session: {self.total_prompt_tokens:,} / {self.total_completion_tokens:,})")

            choice = response.choices[0]
            msg = choice.message

            # Show assistant text
            if msg.content:
                print(f"\n🤖 {msg.content}")

            # Tool calls
            if choice.finish_reason == "tool_calls" and msg.tool_calls:
                self.messages.append(msg.model_dump())

                for tc in msg.tool_calls:
                    fn = tc.function
                    try:
                        args = json.loads(fn.arguments)
                    except json.JSONDecodeError:
                        args = {}

                    print(f"\n🔧 {fn.name}({json.dumps(args, ensure_ascii=False)[:120]})")

                    # Confirmation for edits — show full diff before applying
                    if fn.name == "edit_file" and not auto_apply:
                        file_path = args.get('path', '?')
                        old_text = args.get('old_text', '')
                        new_text = args.get('new_text', '')

                        print(f"\n{'─'*60}")
                        print(f"  📝 PROPOSED EDIT: {file_path}")
                        print(f"{'─'*60}")
                        print(f"  ❌ REMOVE ({len(old_text.splitlines())} lines):")
                        print(f"{'─'*60}")
                        for line in old_text.splitlines():
                            print(f"  \033[91m- {line}\033[0m")
                        print(f"{'─'*60}")
                        print(f"  ✅ INSERT ({len(new_text.splitlines())} lines):")
                        print(f"{'─'*60}")
                        for line in new_text.splitlines():
                            print(f"  \033[92m+ {line}\033[0m")
                        print(f"{'─'*60}")

                        confirm = input("\n  Apply this change? (Y/N): ").strip().upper()
                        if confirm in ("Y", "YES", "S", "SI", "SÍ"):
                            result = execute_tool(fn.name, args)
                            print(f"  ✅ {result}")
                        else:
                            result = "User declined this edit."
                            print(f"  ⏭️ Skipped.")
                    else:
                        result = execute_tool(fn.name, args)

                    # Truncate tool result before adding to messages
                    result = _truncate(result, MAX_READ_FILE_CHARS, "tool result")
                    print(f"  → {result[:200]}")
                    self.messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

            elif choice.finish_reason == "stop":
                self.messages.append(msg.model_dump())
                follow = input("\n💬 Follow-up? (type question or 'exit'): ").strip()
                if follow.lower() in ("exit", "quit", "no", ""):
                    break
                self.messages.append({"role": "user", "content": follow})
            else:
                print(f"⚠ Unexpected finish_reason: {choice.finish_reason}")
                break

        print(f"\n{'='*60}")
        print(f"  Session complete ({iteration} iterations)")
        print(f"  📊 Total tokens — prompt: {self.total_prompt_tokens:,} | completion: {self.total_completion_tokens:,} | total: {self.total_prompt_tokens + self.total_completion_tokens:,}")
        print(f"{'='*60}\n")
