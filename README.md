# 🔬 Excalibur Forensic Migration Agent

**Lead Forensic Migration Engineer** for the Excalibur Modernized project (VB6 → C# .NET 9).

An autonomous debugging agent that diagnoses complex runtime errors by cross-referencing
legacy VB6 patterns with modern C# implementations, using established team patterns (GAP-Notes)
and documented migration skills as its primary source of truth.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    INPUT (Bug Report)                         │
├──────────────┬───────────────┬──────────────┬───────────────┤
│ 🖥️ Error     │ 📋 Callstack  │ 🎯 Expected  │ 📝 Description│
│ Screenshot   │ Screenshot    │ Result       │ + Class       │
└──────┬───────┴───────┬───────┴──────┬───────┴───────┬───────┘
       │               │              │               │
       ▼               ▼              ▼               ▼
┌──────────────────────────────────────────────────────────────┐
│                   KNOWLEDGE SOURCES                          │
├────────────────┬──────────────────┬──────────────────────────┤
│ 📋 Repo PRs    │ 📘 Skills (.md)  │ 📝 Local GAP-Notes      │
│ --sync-repo    │ Gold Standard    │ Live codebase scan       │
│ GitHub API     │ agent/skills/    │ // GAP-Note. author,..   │
├────────────────┴──────────────────┴──────────────────────────┤
│                 Pattern Matching Engine                       │
│  • GAP-Note identification (sgonzalez, jnunez, etc.)        │
│  • Skill relevance scoring                                   │
│  • Category classification                                   │
│  • Confidence ranking (trusted authors = high confidence)    │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    LLM (GPT-4o via GitHub Models)            │
│                                                              │
│  System Prompt:                                              │
│  • Full migration context (VB6 types, DbVariant, etc.)      │
│  • Injected relevant skills                                  │
│  • Injected historical fixes from PRs                        │
│  • Injected local GAP-Notes for the class                   │
│                                                              │
│  Tools:                                                      │
│  • read_file, edit_file, search_code                        │
│  • find_class_files, search_gap_notes                       │
│  • compile_project, search_vb6_pattern                      │
└──────────────────────────┬───────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                    RESPONSE (Mandatory Structure)            │
├──────────────────────────────────────────────────────────────┤
│  1. Root Cause Analysis                                      │
│  2. Historical Reference (GAP-Note / Skill citation)        │
│  3. Proposed Fix (C# code with // GAP-Note comments)        │
│  4. Verification Steps                                       │
└──────────────────────────────────────────────────────────────┘
```

## Quick Start (Para el equipo)

### Primera vez (setup — solo una vez)
```powershell
# 1. Clonar o actualizar el repo
git pull

# 2. Correr setup (instala dependencias automáticamente)
agent\setup.bat

# 3. Configurar tu GitHub token (una vez por terminal)
$env:GITHUB_TOKEN = "ghp_TU_TOKEN_AQUI"
# O crear archivo agent\.env con: GITHUB_TOKEN=ghp_TU_TOKEN_AQUI
```

### Uso diario
```powershell
# Desde cualquier terminal, navegar a la carpeta agent:
cd agent

# Correr el agente:
excalibur-fix -C NombreClase -b "descripción del error"

# Ejemplo real:
excalibur-fix -C PD_BarCodePrint -b "IndexOutOfRangeException: Invalid index 1 for OleDbParameterCollection" -L "PD_BarCodePrint.cs:87"
```

> **Nota**: Si `excalibur-fix` no funciona, usar directamente:
> ```powershell
> python fix.py -C NombreClase -b "descripción del error"
> ```

## Usage Examples

### Diagnose with error screenshot
```powershell
python fix.py -C frmBondBilling -b "crash when opening" -s error.png
```

### Diagnose with callstack
```powershell
python fix.py -C frmPolicyPC -b "NullReference on save" -s error.png -c callstack.png
```

### Compare with legacy visual
```powershell
python fix.py -C frmInstallments -b "button blank" -s current.png -l legacy.png
```

### With expected result description
```powershell
python fix.py -C frmPolicyPC -b "crash on save" -e "Should save policy and return to search"
```

### Sync repository PRs for knowledge
```powershell
# First time: scans PRs and builds knowledge cache
python fix.py -C frmBondBilling -b "Form_Load crash" \
    --repo myorg/Excalibur_Modernized --sync-repo --base-branch main

# Subsequent runs use the cache automatically
python fix.py -C frmBondBilling -b "Form_Load crash" --repo myorg/Excalibur_Modernized
```

### Auto-apply mode
```powershell
python fix.py -C frmPolicyPC -b "missing color" -s bug.png --auto
```

### Utility commands
```powershell
python fix.py --list-skills          # Show all migration skills
python fix.py --list-knowledge       # Show PR knowledge cache
python fix.py --scan-notes           # Scan all GAP-Notes in codebase
python fix.py --scan-notes -C frmInstallments  # Scan GAP-Notes for specific class
```

## CLI Parameters

### Bug Report Inputs
| Parameter | Short | Required | Description |
|-----------|-------|----------|-------------|
| `--class` | `-C` | ✅ | Target class where the failure is localized |
| `--bug` | `-b` | ✅ | Runtime error description |
| `--line` | `-L` | ❌ | Exact error line (e.g. `PD_BarCodePrint.cs:87`) |
| `--expected` | `-e` | ❌ | Expected functional result |

### Screenshots (OCR + Vision Analysis)
| Parameter | Short | Description |
|-----------|-------|-------------|
| `--screenshot` | `-s` | Runtime error screenshot |
| `--callstack` | `-c` | Callstack screenshot |
| `--legacy` | `-l` | Expected result / VB6 legacy screenshot |

### Repository Sync
| Parameter | Description |
|-----------|-------------|
| `--repo` | GitHub repo (owner/repo) for PR knowledge |
| `--sync-repo` | Trigger PR scan (first time or refresh) |
| `--max-prs` | Max PRs to scan (default: 50) |
| `--base-branch` | Filter PRs by base branch |

### Options
| Parameter | Short | Description |
|-----------|-------|-------------|
| `--auto` | | Apply fixes without confirmation |
| `--model` | `-m` | LLM model (default: gpt-4o) |
| `--token` | `-t` | GitHub token override |
| `--max-iterations` | | Max agent loop iterations (default: 15) |

## Skills (Gold Standard)

Skills are `.md` files in `agent/skills/` that document the team's established migration patterns.
The agent **strictly adheres** to these guidelines.

| # | Skill | Category | Severity |
|---|-------|----------|----------|
| 01 | Form_Load Timing (CreateInstance) | `form_load_timing` | 🔴 Critical |
| 02 | DbVariant<T> IConvertible Cast | `dbvariant_cast` | 🔴 Critical |
| 03 | BackColor Cyan/Celeste Visual | `backcolor_visual` | 🟡 Medium |
| 04 | CommandButtonHelper Image | `commandbutton_image` | 🟠 High |
| 05 | Control Sizing / Text Clip | `control_sizing` | 🟡 Medium |
| 06 | TreeView Migration (SelectedNodes + ImageList) | `treeview_migration` | 🟠 High |
| 07 | OleParametersHelper ParameterSpec Fix | `ole_parameters` | � Critical |
| 08 | VB6 Integer/Long Type Nuances | `dbvariant_cast` | 🟠 High |
| 09 | DbParameter → DbVariant\<T\> Field Types | `dbvariant_cast` | 🔴 Critical |

### Adding a New Skill

Create a `.md` file in `agent/skills/` with YAML frontmatter:

```markdown
---
id: my_new_skill
title: My New Migration Pattern
category: category_name
severity: high
symptoms: [symptom1, symptom2, symptom3]
applies_to: [frmSpecificForm]
vb6_pattern: What the VB6 code looked like
dotnet_fix: What the correct .NET fix is
---

## Problem
(Description)

## Fix
(Code examples)

## Resolved Cases
(Real examples)
```

## File Structure

```
excalibur-agent/
├── excalibur-fix.bat      # 🚀 Launcher script (teammates use this)
├── excalibur-fix.py       # CLI entry point
├── setup.bat              # 🔧 One-time setup (install deps)
├── forensic_agent.py      # Lead Forensic Migration Engineer (main agent)
├── config.py              # Central configuration
├── repo_sync.py           # GitHub PR sync + GAP-Note extraction
├── gap_note_scanner.py    # Local codebase GAP-Note scanner
├── skills_engine.py       # Skills loader + indexer (Gold Standard)
├── skills/                # Migration skill files (.md)
│   ├── 01_form_load_timing.md
│   ├── 02_dbvariant_cast.md
│   ├── 03_backcolor_visual.md
│   ├── 04_commandbutton_image.md
│   ├── 05_control_sizing.md
│   ├── 06_treeview_migration.md
│   ├── 08_vb6_type_nuances.md
│   ├── 09_dbvariant_field_types.md
│   └── ... (more skills)
├── knowledge_cache.json   # Auto-generated PR knowledge cache
├── requirements.txt       # Python dependencies
├── .env.example           # Token configuration template
└── README.md              # This documentation
```

## Key Design Decisions

1. **GAP-Note as Source of Truth**: The agent prioritizes solutions that align with `//GAP-Note.*` 
   patterns found in the codebase and PR history.

2. **Trusted Authors**: Notes from `sgonzalez`, `jnunez`, `gartavia`, `lmontero` get 
   **high confidence** ranking in pattern matching.

3. **Mandatory Response Structure**: The agent always responds with Root Cause Analysis → 
   Historical Reference → Proposed Fix → Verification Steps.

4. **Legacy Contract**: Fixes never break VB6/.NET behavioral parity unless explicitly requested.

5. **Autonomous but Careful**: The agent proposes and explains fixes before applying. 
   Use `--auto` only when you trust the pattern matching.
