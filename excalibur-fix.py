#!/usr/bin/env python3
"""
excalibur-fix.py — CLI for the Excalibur Forensic Migration Agent.

Usage:
    excalibur-fix -C frmInstallments -b "button undo shows no image"
    excalibur-fix -C frmBondBilling -b "Form_Load crash" -s error.png -c callstack.png
    excalibur-fix -C frmPolicyPC -b "crash on save" -e "Should save without error" --repo org/Excalibur --sync-repo
    excalibur-fix --list-skills
    excalibur-fix --list-knowledge
    excalibur-fix --scan-notes
"""

import argparse
import os
import sys

from dotenv import load_dotenv

# Load .env if present
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.isfile(env_path):
    load_dotenv(env_path)

from forensic_agent import ForensicAgent
from skills_engine import SkillsEngine
from gap_note_scanner import GapNoteScanner
from repo_sync import RepoSync


def cmd_list_skills():
    """List all available skills."""
    engine = SkillsEngine()
    engine.load()
    print(engine.get_summary())


def cmd_list_knowledge():
    """Show the knowledge base from synced PRs."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("❌ GITHUB_TOKEN required. Set $env:GITHUB_TOKEN = (gh auth token)")
        return
    sync = RepoSync(token, "")
    if sync.load_cache():
        cache = sync.cache
        print(f"📋 Knowledge Base: {cache.get('total_fixes', 0)} fixes")
        print(f"   Repo: {cache.get('repo', '?')}")
        print(f"   Last sync: {cache.get('last_sync', '?')}")
        print(f"   PRs scanned: {cache.get('total_prs_scanned', '?')}")

        # Categories summary
        cats = {}
        for f in cache.get("fixes", []):
            cat = f.get("category", "other")
            cats[cat] = cats.get(cat, 0) + 1
        print("\n   By category:")
        for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
            print(f"     {cat}: {count}")
    else:
        print("📋 No knowledge base found. Use --sync-repo to create one.")


def cmd_scan_notes(class_filter: str = None):
    """Scan local codebase for GAP-Notes."""
    scanner = GapNoteScanner()
    scanner.scan(class_filter=class_filter, verbose=True)
    print(scanner.get_summary())


def cmd_run_agent(args):
    """Run the forensic agent."""
    # Validate images
    for img, label in [
        (args.screenshot, "--screenshot"),
        (args.callstack, "--callstack"),
        (args.legacy, "--legacy"),
    ]:
        if img and not os.path.isfile(img):
            print(f"❌ File not found for {label}: {img}")
            sys.exit(1)

    try:
        agent = ForensicAgent(
            token=args.token,
            model=args.model,
            repo=args.repo,
        )
    except ValueError as e:
        print(f"\n❌ {e}")
        sys.exit(1)

    # Initialize knowledge
    agent.initialize_knowledge(
        sync_repo=args.sync_repo,
        max_prs=args.max_prs,
        base_branch=args.base_branch,
    )

    # Run
    agent.run(
        description=args.bug_description,
        class_name=args.class_name,
        error_line=args.error_line,
        expected_result=args.expected,
        screenshot_error=args.screenshot,
        screenshot_callstack=args.callstack,
        screenshot_legacy=args.legacy,
        auto_apply=args.auto,
        max_iterations=args.max_iterations,
    )


def main():
    parser = argparse.ArgumentParser(
        description="🔬 Excalibur Forensic Migration Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic fix
  excalibur-fix -C frmInstallments -b "undo button shows no image"

  # With error line
  excalibur-fix -C PD_BarCodePrint -b "IndexOutOfRangeException" -L "PD_BarCodePrint.cs:87"

  # With screenshots (error + callstack + expected)
  excalibur-fix -C frmBondBilling -b "NullReference on load" \\
      -s error.png -c stack.png -l expected.png

  # With repo sync (first time scans PRs, then uses cache)
  excalibur-fix -C frmBondBilling -b "Form_Load crash" \\
      --repo myorg/Excalibur --sync-repo --base-branch stabilization/PBI4248

  # Auto mode (applies fixes without confirmation)
  excalibur-fix -C frmPolicyPC -b "missing color" -s bug.png --auto

  # Utilities
  excalibur-fix --list-skills
  excalibur-fix --list-knowledge
  excalibur-fix --scan-notes
  excalibur-fix --scan-notes -C frmInstallments

Token setup (one time):
  $env:GITHUB_TOKEN = (gh auth token)
  # or
  $env:GITHUB_TOKEN = "ghp_YOUR_TOKEN"
        """,
    )

    # Bug report inputs
    parser.add_argument("--class", "-C", dest="class_name",
                        help="Target class/form where the failure is localized")
    parser.add_argument("--bug", "-b", dest="bug_description",
                        help="Description of the runtime error or bug")
    parser.add_argument("--line", "-L", dest="error_line",
                        help="Exact line where the error occurs (e.g. 'PD_BillingInvoiceData.cs:245')")
    parser.add_argument("--expected", "-e", dest="expected",
                        help="Expected result / functional intent")

    # Screenshots
    parser.add_argument("--screenshot", "-s", dest="screenshot",
                        help="Runtime error screenshot (PNG/JPG)")
    parser.add_argument("--callstack", "-c", dest="callstack",
                        help="Callstack screenshot (PNG/JPG)")
    parser.add_argument("--legacy", "-l", dest="legacy",
                        help="Expected result / legacy VB6 screenshot (PNG/JPG)")

    # Repository sync
    parser.add_argument("--repo", "-r", dest="repo",
                        help="GitHub repository (owner/repo) for PR knowledge")
    parser.add_argument("--sync-repo", action="store_true",
                        help="Sync: fetch latest PRs and extract GAP-Notes")
    parser.add_argument("--max-prs", type=int, default=50,
                        help="Max PRs to scan during sync (default: 50)")
    parser.add_argument("--base-branch", dest="base_branch",
                        help="Filter PRs by base branch")

    # Options
    parser.add_argument("--auto", action="store_true",
                        help="Auto-apply fixes without confirmation")
    parser.add_argument("--model", "-m", default="gpt-4o",
                        help="GitHub Models model (default: gpt-4o)")
    parser.add_argument("--token", "-t",
                        help="GitHub token (or use $env:GITHUB_TOKEN)")
    parser.add_argument("--max-iterations", type=int, default=15,
                        help="Max agent iterations (default: 15, was 30)")

    # Utility commands
    parser.add_argument("--list-skills", action="store_true",
                        help="List all available migration skills")
    parser.add_argument("--list-knowledge", action="store_true",
                        help="Show knowledge base from synced PRs")
    parser.add_argument("--scan-notes", action="store_true",
                        help="Scan local codebase for GAP-Notes")

    args = parser.parse_args()

    # Utility modes
    if args.list_skills:
        cmd_list_skills()
        return
    if args.list_knowledge:
        cmd_list_knowledge()
        return
    if args.scan_notes:
        cmd_scan_notes(args.class_name)
        return

    # Validate required args for agent mode
    if not args.class_name or not args.bug_description:
        parser.error("--class and --bug are required for agent mode")

    cmd_run_agent(args)


if __name__ == "__main__":
    main()
