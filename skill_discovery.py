"""
skill_discovery.py — Auto-discovery of new migration skills.

After the agent applies a fix that didn't match any existing skill,
this module analyzes whether the fix pattern appears elsewhere in the
codebase. If the same buggy pattern exists in 3+ locations, the fix
is a reusable pattern worth documenting as a new skill.

Logic:
  1. Extract a "signature" from the old_text (the buggy code pattern)
  2. Search the entire codebase for similar patterns
  3. If occurrences >= MIN_OCCURRENCES → propose a new skill
  4. If occurrences < MIN_OCCURRENCES → skip (one-off fix)
"""

import os
import re
from pathlib import Path
from datetime import datetime
from config import PROJECT_ROOT, SKILLS_DIR, SKIP_DIRS


# Minimum number of similar patterns in the codebase to warrant a new skill
MIN_OCCURRENCES = 3


class FixRecord:
    """Captures metadata about an applied fix for skill analysis."""

    def __init__(
        self,
        file_path: str,
        old_text: str,
        new_text: str,
        description: str,
        class_name: str,
        matched_skill_id: str = None,
    ):
        self.file_path = file_path
        self.old_text = old_text
        self.new_text = new_text
        self.description = description
        self.class_name = class_name
        self.matched_skill_id = matched_skill_id


class SkillDiscovery:
    """Analyzes applied fixes and proposes new skills when patterns are reusable."""

    def __init__(self, skills_dir: str = None):
        self.skills_dir = Path(skills_dir) if skills_dir else SKILLS_DIR

    def _extract_signatures(self, old_text: str) -> list[str]:
        """
        Extract searchable 'signatures' from the buggy code.

        A signature is a distinctive code pattern that could appear
        in other files — method calls, type usages, specific API patterns.
        We normalize whitespace and extract the most unique fragments.
        """
        signatures = []

        # Strategy 1: Extract method/API calls (e.g., "new OleDbParameter()", ".Parameters.Add(")
        api_patterns = re.findall(
            r'(?:new\s+\w+\([^)]*\)|\.\w+\.\w+\([^)]*\)|\w+\.\w+\s*=\s*[^;]+)',
            old_text,
        )
        for p in api_patterns:
            # Normalize whitespace
            normalized = re.sub(r'\s+', r'\\s+', re.escape(p.strip()))
            if len(p.strip()) > 15:  # Skip trivially short patterns
                signatures.append(p.strip())

        # Strategy 2: Extract distinctive type usages
        type_patterns = re.findall(
            r'(?:DbParameter|OleDbParameter|AdoFactoryManager|UpgradeHelpers\.\w+|'
            r'Convert\.To\w+|\.Value\s*[=!]|RecordSetHelper|ADORecordSetHelper)',
            old_text,
        )
        signatures.extend(set(type_patterns))

        # Strategy 3: Extract full lines that look like the "core" of the bug
        for line in old_text.splitlines():
            line = line.strip()
            # Skip comments, braces, empty lines
            if not line or line.startswith("//") or line in ("{", "}", "});"):
                continue
            # Skip GAP-Note lines
            if "GAP-Note" in line:
                continue
            # Keep lines with assignments, method calls, or type declarations
            if any(marker in line for marker in ("=", "(", "new ", "private ", "public ")):
                if len(line) > 20:
                    signatures.append(line)

        return list(set(signatures))  # Deduplicate

    def _search_pattern_in_codebase(self, pattern: str, exclude_file: str = None) -> list[dict]:
        """
        Search for a code pattern across all .cs files in the project.
        Returns list of {file, line_num, line_text} matches.
        """
        matches = []
        # Escape for regex but allow flexible whitespace
        regex_pattern = re.sub(r'\s+', r'\\s+', re.escape(pattern))

        for root, dirs, files in os.walk(PROJECT_ROOT):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for file in files:
                if not file.endswith(".cs"):
                    continue
                fpath = os.path.join(root, file)
                rel = os.path.relpath(fpath, PROJECT_ROOT)

                # Skip the file that was already fixed
                if exclude_file and os.path.normpath(fpath) == os.path.normpath(exclude_file):
                    continue
                # Skip Designer files
                if ".Designer.cs" in file:
                    continue

                try:
                    with open(fpath, "r", encoding="utf-8-sig") as f:
                        for i, line in enumerate(f, 1):
                            if re.search(regex_pattern, line, re.IGNORECASE):
                                matches.append({
                                    "file": rel,
                                    "line_num": i,
                                    "line_text": line.rstrip(),
                                })
                except Exception:
                    pass

        return matches

    def analyze(self, fix: FixRecord) -> dict:
        """
        Analyze a fix to determine if it should become a new skill.

        Returns:
            {
                "should_create_skill": bool,
                "reason": str,
                "occurrences": int,
                "locations": list[str],   # "file:line" of similar patterns
                "signatures_found": list[str],
                "suggested_title": str,
                "suggested_severity": str,
            }
        """
        result = {
            "should_create_skill": False,
            "reason": "",
            "occurrences": 0,
            "locations": [],
            "signatures_found": [],
            "suggested_title": "",
            "suggested_severity": "medium",
        }

        # Skip if the fix already matched an existing skill
        if fix.matched_skill_id:
            result["reason"] = f"Fix matched existing skill '{fix.matched_skill_id}' — no new skill needed."
            return result

        # Extract searchable patterns from the buggy code
        signatures = self._extract_signatures(fix.old_text)
        if not signatures:
            result["reason"] = "Could not extract distinctive patterns from the old code."
            return result

        # Resolve the full path for exclusion
        full_fix_path = fix.file_path
        if not os.path.isabs(full_fix_path):
            full_fix_path = os.path.join(PROJECT_ROOT, full_fix_path)

        # Search each signature across the codebase
        all_locations = set()
        matched_signatures = []

        for sig in signatures:
            if len(sig) < 15:
                continue  # Skip too-short patterns (high false positive rate)
            matches = self._search_pattern_in_codebase(sig, exclude_file=full_fix_path)
            if matches:
                matched_signatures.append(sig)
                for m in matches:
                    all_locations.add(f"{m['file']}:{m['line_num']}")

        result["occurrences"] = len(all_locations)
        result["locations"] = sorted(all_locations)[:20]  # Cap at 20 for display
        result["signatures_found"] = matched_signatures[:5]

        if len(all_locations) >= MIN_OCCURRENCES:
            result["should_create_skill"] = True
            result["reason"] = (
                f"Found {len(all_locations)} similar occurrences in {len(set(m.split(':')[0] for m in all_locations))} files. "
                f"This pattern is reusable and should be documented as a skill."
            )
            # Suggest severity based on count
            if len(all_locations) >= 10:
                result["suggested_severity"] = "critical"
            elif len(all_locations) >= 5:
                result["suggested_severity"] = "high"
            else:
                result["suggested_severity"] = "medium"

            # Suggest a title based on the fix description
            result["suggested_title"] = self._suggest_title(fix)
        else:
            result["reason"] = (
                f"Only {len(all_locations)} similar occurrence(s) found. "
                f"This appears to be an isolated fix — no new skill needed."
            )

        return result

    def _suggest_title(self, fix: FixRecord) -> str:
        """Generate a suggested skill title from the fix context."""
        desc = fix.description.lower()
        # Try to extract the core issue
        keywords = []
        if "oledb" in desc or "parameter" in desc:
            keywords.append("OleDb Parameter")
        if "dbvariant" in desc:
            keywords.append("DbVariant")
        if "cast" in desc or "convert" in desc or "iconvertible" in desc:
            keywords.append("Type Cast")
        if "null" in desc:
            keywords.append("Null Handling")
        if "index" in desc or "outofrange" in desc:
            keywords.append("Index")
        if "load" in desc or "form_load" in desc:
            keywords.append("Form Load")

        if keywords:
            return " ".join(keywords) + " Migration Fix"
        return f"Migration Fix for {fix.class_name}"

    def generate_skill_file(self, fix: FixRecord, analysis: dict) -> str:
        """
        Generate a new skill .md file with proper YAML frontmatter.
        Returns the path to the created file.
        """
        # Determine next skill number
        existing = sorted(self.skills_dir.glob("*.md"))
        max_num = 0
        for f in existing:
            match = re.match(r"^(\d+)", f.stem)
            if match:
                max_num = max(max_num, int(match.group(1)))
        next_num = max_num + 1

        # Generate skill ID
        title = analysis.get("suggested_title", f"Auto-discovered Fix ({fix.class_name})")
        skill_id = re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')
        filename = f"{next_num:02d}_{skill_id}.md"
        filepath = self.skills_dir / filename

        # Collect the affected files from locations
        affected_files = sorted(set(
            loc.split(":")[0].replace(".cs", "").replace("\\", "/").split("/")[-1]
            for loc in analysis.get("locations", [])
        ))

        # Build symptoms from signatures
        symptoms = [s[:50] for s in analysis.get("signatures_found", [])[:5]]

        # Generate content
        content = f"""---
id: {skill_id}
title: {title}
category: auto_discovered
severity: {analysis.get('suggested_severity', 'medium')}
symptoms: [{', '.join(symptoms)}]
applies_to: [{', '.join(affected_files[:10])}]
vb6_pattern: Pattern auto-discovered from fix in {fix.class_name}
dotnet_fix: See fix pattern below
---

## Problem

This skill was **auto-discovered** by the Excalibur Forensic Agent on {datetime.now().strftime('%Y-%m-%d')}.

The agent applied a fix to `{fix.class_name}` that did not match any existing skill,
and found **{analysis['occurrences']} similar occurrences** across {len(affected_files)} files
in the codebase, indicating this is a reusable migration pattern.

**Original bug**: {fix.description}

## Buggy Pattern (old code)

```csharp
{fix.old_text.strip()}
```

## Correct Pattern (fix)

```csharp
{fix.new_text.strip()}
```

## Similar Occurrences

Found in {analysis['occurrences']} locations across the codebase:

"""
        for loc in analysis.get("locations", [])[:15]:
            content += f"- `{loc}`\n"

        if analysis["occurrences"] > 15:
            content += f"\n... and {analysis['occurrences'] - 15} more.\n"

        content += """
## Verification

After applying this fix pattern, always run `compile_project` to verify the build passes.
"""

        # Write the file
        filepath.write_text(content, encoding="utf-8")
        return str(filepath)

    def print_analysis(self, analysis: dict):
        """Print the analysis result in a readable format."""
        print(f"\n{'─'*60}")
        print(f"  🔍 SKILL DISCOVERY ANALYSIS")
        print(f"{'─'*60}")

        if analysis["should_create_skill"]:
            print(f"  ✅ NEW SKILL RECOMMENDED")
            print(f"  📊 Similar patterns: {analysis['occurrences']} occurrences")
            print(f"  📝 Suggested title: {analysis['suggested_title']}")
            print(f"  🔴 Severity: {analysis['suggested_severity']}")
            print(f"\n  Locations with same pattern:")
            for loc in analysis["locations"][:10]:
                print(f"    • {loc}")
            if analysis["occurrences"] > 10:
                print(f"    ... and {analysis['occurrences'] - 10} more")
        else:
            print(f"  ⏭️ No new skill needed")

        print(f"  💬 {analysis['reason']}")
        print(f"{'─'*60}")
