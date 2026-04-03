"""
mcp_server.py — Excalibur Forensic Migration Agent as MCP Server.

Exposes the agent's tools to GitHub Copilot Chat in VS Code via MCP (stdio transport).
Teammates can use these tools directly from Copilot Chat without running the CLI.

Usage (automatic via .vscode/mcp.json):
    In Copilot Chat, the tools appear automatically. Just ask:
    "Search for IndexOutOfRangeException in PD_BarCodePrint"
    "Read line 87 of PD_BarCodePrint.cs"
    "Compile the Excalibur project"
"""

import os
import re
import sys
import json
import subprocess
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# ─── Resolve project paths ───────────────────
# MCP server runs from excalibur-agent/ folder
AGENT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = AGENT_DIR.parent.resolve()
BUILD_PROJECT = PROJECT_ROOT / "ExcaliburEXE" / "Avalon.csproj"

SKIP_DIRS = frozenset({
    "bin", "obj", ".git", ".vs", "packages", "node_modules",
    "agent", "excalibur-agent", "_UpgradeReport_Files", "Documents",
})

GAP_NOTE_REGEX = r"//\s*GAP-Note[:\.]?\s*(\w+)[,:]\s*(.*?)$"

# ─── Create MCP Server ───────────────────────
mcp = FastMCP("Excalibur Migration Agent")


# ─── Tools ────────────────────────────────────

@mcp.tool()
def read_file(path: str, start_line: int = 0, end_line: int = 0) -> str:
    """Read a file from the Excalibur project. Use start_line/end_line (1-based) for large files.
    Path can be relative to project root (e.g. 'BusinessLogic/PD_BarCodePrint.cs')."""
    full = path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)
    try:
        with open(full, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
        if start_line and end_line:
            sel = lines[max(0, start_line - 1) : end_line]
            return "".join(f"{start_line + i}: {l}" for i, l in enumerate(sel))
        if len(lines) > 300:
            return f"File has {len(lines)} lines. Use start_line/end_line to read a section.\nFirst 50 lines:\n" + "".join(f"{i+1}: {l}" for i, l in enumerate(lines[:50]))
        return "".join(f"{i+1}: {l}" for i, l in enumerate(lines))
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Edit a file by replacing old_text with new_text (single occurrence). 
    old_text must be unique — include 3+ lines of surrounding context.
    Always add '// GAP-Note. agente, description' on changed lines."""
    full = path if os.path.isabs(path) else os.path.join(PROJECT_ROOT, path)
    try:
        with open(full, "r", encoding="utf-8-sig") as f:
            content = f.read()
        if old_text not in content:
            return f"Error: old_text not found in {path}. Verify exact whitespace."
        if content.count(old_text) > 1:
            return f"Ambiguous: old_text found {content.count(old_text)} times. Add more context."
        content = content.replace(old_text, new_text, 1)
        with open(full, "w", encoding="utf-8-sig") as f:
            f.write(content)
        return f"OK: {path} edited successfully."
    except Exception as e:
        return f"Error: {e}"


@mcp.tool()
def search_code(pattern: str, file_extension: str = ".cs", max_results: int = 15) -> str:
    """Search for a regex pattern across all project files. Returns file:line: match."""
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
                                return "\n".join(results)
            except Exception:
                pass
    return "\n".join(results) if results else "No matches found."


@mcp.tool()
def find_class_files(class_name: str) -> str:
    """Find all files (.cs, .Designer.cs, .resX) associated with a class/form name."""
    results = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file in files:
            if class_name.lower() in file.lower() and file.endswith((".cs", ".resX", ".resx")):
                rel = os.path.relpath(os.path.join(root, file), PROJECT_ROOT)
                size = os.path.getsize(os.path.join(root, file))
                results.append(f"{rel} ({size:,} bytes)")
    return "\n".join(sorted(results)) if results else f"No files found for '{class_name}'"


@mcp.tool()
def search_gap_notes(class_name: str = "", keyword: str = "") -> str:
    """Search for //GAP-Note comments in the codebase. Filter by class_name and/or keyword."""
    pattern = re.compile(GAP_NOTE_REGEX, re.IGNORECASE)
    results = []
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file in files:
            if not file.endswith(".cs"):
                continue
            if class_name and class_name.lower() not in file.lower():
                continue
            fpath = os.path.join(root, file)
            try:
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    for i, line in enumerate(f, 1):
                        m = pattern.search(line)
                        if m:
                            desc = m.group(2).strip()
                            if keyword and keyword.lower() not in desc.lower():
                                continue
                            rel = os.path.relpath(fpath, PROJECT_ROOT)
                            results.append(f"{rel}:{i}: {m.group(1)}: {desc}")
                            if len(results) >= 20:
                                return f"Found {len(results)}+ GAP-Notes:\n" + "\n".join(results)
            except Exception:
                pass
    return f"Found {len(results)} GAP-Notes:\n" + "\n".join(results) if results else "No GAP-Notes found."


@mcp.tool()
def compile_project() -> str:
    """Compile the Excalibur .NET project with 'dotnet build' and return any CS errors."""
    try:
        result = subprocess.run(
            ["dotnet", "build", str(BUILD_PROJECT)],
            capture_output=True, text=True, timeout=120, cwd=str(PROJECT_ROOT),
        )
        errors = [l for l in result.stdout.splitlines() if "error CS" in l]
        warnings = [l for l in result.stdout.splitlines() if "warning CS" in l]
        if not errors:
            return f"✅ BUILD SUCCEEDED — 0 errors, {len(warnings)} warnings."
        return "❌ BUILD FAILED:\n" + "\n".join(errors[:20])
    except Exception as e:
        return f"Compilation error: {e}"


@mcp.tool()
def list_skills() -> str:
    """List all available migration skills (Gold Standard patterns for VB6→C# fixes)."""
    skills_dir = AGENT_DIR / "skills"
    if not skills_dir.is_dir():
        return "No skills directory found."
    skills = []
    for f in sorted(skills_dir.iterdir()):
        if f.suffix == ".md":
            # Read title from frontmatter
            title = f.stem
            try:
                text = f.read_text(encoding="utf-8")
                for line in text.splitlines():
                    if line.strip().startswith("title:"):
                        title = line.split(":", 1)[1].strip()
                        break
            except Exception:
                pass
            skills.append(f"- {title} ({f.name})")
    return f"{len(skills)} skills loaded:\n" + "\n".join(skills)


@mcp.tool()
def get_skill(skill_name: str) -> str:
    """Read the full content of a specific migration skill file. 
    Use list_skills first to see available names."""
    skills_dir = AGENT_DIR / "skills"
    # Try exact match first
    for f in skills_dir.iterdir():
        if f.suffix == ".md" and (skill_name.lower() in f.stem.lower() or skill_name.lower() in f.name.lower()):
            return f.read_text(encoding="utf-8")
    return f"Skill '{skill_name}' not found. Use list_skills to see available skills."


@mcp.tool()
def scan_gap_notes_summary() -> str:
    """Scan the entire codebase and return a summary of GAP-Notes by author and top classes."""
    pattern = re.compile(GAP_NOTE_REGEX, re.IGNORECASE)
    by_author = {}
    by_class = {}
    total = 0
    for root, dirs, files in os.walk(PROJECT_ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for file in files:
            if not file.endswith(".cs"):
                continue
            cls = file.replace(".Designer.cs", "").replace(".cs", "")
            fpath = os.path.join(root, file)
            try:
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    for line in f:
                        m = pattern.search(line)
                        if m:
                            total += 1
                            author = m.group(1)
                            by_author[author] = by_author.get(author, 0) + 1
                            by_class[cls] = by_class.get(cls, 0) + 1
            except Exception:
                pass
    lines = [f"Total: {total} GAP-Notes\n\nBy author:"]
    for a, c in sorted(by_author.items(), key=lambda x: -x[1]):
        lines.append(f"  {a}: {c}")
    lines.append("\nTop 10 classes:")
    for cls, c in sorted(by_class.items(), key=lambda x: -x[1])[:10]:
        lines.append(f"  {cls}: {c}")
    return "\n".join(lines)


# ─── Run ──────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
