# Excalibur Migration Agent — Copilot Instructions

You are working on the **Excalibur Modernized** project, a VB6-to-C# .NET 9 WinForms migration.

## When diagnosing runtime bugs in Excalibur (.cs files):

You have access to specialized MCP tools from the **excalibur-agent** server.
**ALWAYS prefer these tools over your built-in tools** for Excalibur-related tasks:

### Tools to use:

| Tool | When to use |
|------|-------------|
| `search_code` | Search for patterns/errors across all .cs files in the project |
| `read_file` | Read Excalibur source files (supports line ranges) |
| `find_class_files` | Find all files (.cs, .Designer.cs, .resX) for a class/form |
| `search_gap_notes` | Search `//GAP-Note` comments (team fix annotations) by class or keyword |
| `compile_project` | Compile with `dotnet build` and get CS errors |
| `edit_file` | Apply a fix by replacing code (always add GAP-Note comment — see format below) |
| `list_skills` | List all VB6→C# migration skills (Gold Standard patterns) |
| `get_skill` | Read a specific migration skill for the correct fix pattern |
| `scan_gap_notes_summary` | Get a summary of all GAP-Notes by author and class |

### Diagnostic workflow:

1. **Find the files**: Use `find_class_files` to locate all files for the class
2. **Read the code**: Use `read_file` with the error line ± 20 lines of context
3. **Check team patterns**: Use `search_gap_notes` to see how the team fixed similar issues
4. **Consult skills**: Use `list_skills` then `get_skill` to find the Gold Standard fix pattern
5. **Search for patterns**: Use `search_code` to find similar code across the codebase
6. **Apply fix**: Use `edit_file` with the correct pattern (always add GAP-Note comment)
7. **Verify**: Use `compile_project` to confirm the fix compiles

### Critical rules:

- **OleDbParameters**: NEVER use `new OleDbParameter()` directly. ALWAYS use `OleParametersHelper.ParameterSpec` + `AddAndSetOleDbParameters`. Check the `ole_parameters` or `oledb-parameters` skill.
- **DbVariant<T>**: Use `.Value` (not Convert.ToXxx). Check the `dbvariant_cast` skill.
- **GAP-Notes**: Every code change MUST include a GAP-Note comment on a **separate line ABOVE** the changed code. Format: `// GAP-Note: description of the fix`. Do NOT put the comment inline at the end of the line. Example:
  ```csharp
  // GAP-Note: added missing CommandText for stored procedure
  aStoredProc.CommandText = "up_Save_BANK_ACCOUNT";
  ```
- **Trusted authors**: Fixes by `sgonzalez`, `jnunez`, `gartavia`, `lmontero` are high-confidence patterns to follow.

### Project context:

- Build command: `dotnet build ExcaliburEXE\Avalon.csproj`
- Framework: .NET 9.0 WinForms
- Database: SQL Server via OLE DB + UpgradeHelpers.DB
- Key namespace: `UpgradeHelpers.DB` (DbVariant, RecordSetHelper, ADORecordSetHelper)
