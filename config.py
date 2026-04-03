"""
config.py — Central configuration for the Excalibur Forensic Migration Agent.

All paths, endpoints, patterns, and constants in one place.
"""

import os
from pathlib import Path

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────

AGENT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = AGENT_DIR.parent.resolve()
SKILLS_DIR = AGENT_DIR / "skills"
KNOWLEDGE_CACHE = AGENT_DIR / "knowledge_cache.json"
BUILD_PROJECT = PROJECT_ROOT / "ExcaliburEXE" / "Avalon.csproj"

# ─────────────────────────────────────────────
# GITHUB MODELS API (included with Copilot)
# ─────────────────────────────────────────────

GITHUB_MODELS_ENDPOINT = "https://models.inference.ai.azure.com"
DEFAULT_MODEL = "gpt-4o"

# ─────────────────────────────────────────────
# GAP-NOTE PATTERN
# ─────────────────────────────────────────────

# Primary pattern: //GAP-Note. username: Description
# Also matches:    // GAP-Note. username, Description
#                  //GAP-Note: username: Description
GAP_NOTE_REGEX = r"//\s*GAP-Note[:\.]?\s*(\w+)[,:]\s*(.*?)$"

# High-confidence authors (prioritized in pattern matching)
TRUSTED_AUTHORS = ["sgonzalez", "jnunez", "gartavia", "lmontero", "agente"]

# ─────────────────────────────────────────────
# CODEBASE SCANNING
# ─────────────────────────────────────────────

SKIP_DIRS = frozenset({
    "bin", "obj", ".git", ".vs", "packages", "node_modules",
    "agent", "excalibur-agent", "_UpgradeReport_Files", "Documents",
})

CODE_EXTENSIONS = frozenset({".cs", ".resX", ".resx", ".csproj"})

# ─────────────────────────────────────────────
# EXCALIBUR TECHNICAL CONTEXT
# ─────────────────────────────────────────────

MIGRATION_CONTEXT = {
    "source": "Visual Basic 6.0 (COM+, ActiveX, ADODB)",
    "target": ".NET 9.0, C# WinForms",
    "migration_tool": "VBUC (Visual Basic Upgrade Companion)",
    "db_access": "OLE DB via UpgradeHelpers.DB",
    "grid_control": "C1TrueDBGrid (ComponentOne)",
    "wrapper_type": "DbVariant<T> — .Value returns boxed T, .IsNull checks null, does NOT implement IConvertible",
    "legacy_color": "Color.FromArgb(192, 255, 255)  // VB6 cyan/celeste",
    "gap_note_format": "// GAP-Note. author, description",
}

# ─────────────────────────────────────────────
# VB6/.NET TYPE MAPPING (for cast diagnostics)
# ─────────────────────────────────────────────

VB6_TO_DOTNET_TYPES = {
    "Integer": "short (Int16)",
    "Long": "int (Int32)",
    "Single": "float",
    "Double": "double",
    "Currency": "decimal",
    "String": "string",
    "Boolean": "bool",
    "Date": "DateTime",
    "Variant": "object / DbVariant<T>",
    "Object": "object",
    "Byte": "byte",
}
