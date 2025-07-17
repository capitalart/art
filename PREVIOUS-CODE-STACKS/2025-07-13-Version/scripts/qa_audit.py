#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Simple recursive QA audit for the repo.
Generates QA_REPORT.md in each folder and a master full-rundown.md in repo root.
This is a best-effort heuristic audit. It checks for TODOs and empty files.
"""

from pathlib import Path
from datetime import datetime
from typing import List, Tuple

IGNORE_DIRS = {'.git', 'venv', '.venv', '__pycache__', '.pytest_cache'}
IGNORE_FILES = {'QA_REPORT.md', 'full-rundown.md'}

STATUS_COMPLETE = '✅'
STATUS_TUNE = '⚠️'
STATUS_BROKEN = '❌'


def extract_summary(path: Path) -> str:
    """Return first comment line as summary if available."""
    try:
        with path.open('r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if line.startswith(('#', '//', '/*', '"""', "'")):
                    return line.strip('#/ *"')[:80]
                if path.suffix in {'.html', '.htm'} and line.startswith('<!--'):
                    return line.strip('<!-> ')[:80]
                # Non comment line means there's no summary
                break
    except Exception:
        return ''
    return ''


def analyze_file(path: Path) -> Tuple[str, str, List[str]]:
    """Return purpose, status, issues list."""
    issues = []
    summary = extract_summary(path)
    try:
        text = path.read_text(encoding='utf-8')
    except Exception as e:
        return summary, STATUS_BROKEN, [f'Could not read file: {e}']

    lines = text.splitlines()
    if len(lines) == 0:
        return summary, STATUS_BROKEN, ['File is empty']

    status = STATUS_COMPLETE
    if len(lines) < 5:
        status = STATUS_TUNE
        issues.append('File very short')

    todo_keywords = ['TODO', 'FIXME', 'XXX']
    if any(kw in text for kw in todo_keywords):
        status = STATUS_TUNE
        issues.append('Contains TODO/FIXME')

    return summary, status, issues


def write_report(folder: Path, reports: List[Tuple[Path, str, str, List[str]]]):
    report_path = folder / 'QA_REPORT.md'
    lines = [f"# QA Report: {folder}\n", f"_Audit date: {datetime.utcnow():%Y-%m-%d %H:%M UTC}_\n\n"]
    lines.append("| File | Purpose/Role | Status | Issues |\n")
    lines.append("|------|--------------|--------|--------|\n")
    for rel_path, summary, status, issues in reports:
        issues_str = '; '.join(issues) if issues else '-'
        summary = summary if summary else '-'
        lines.append(f"| {rel_path} | {summary} | {status} | {issues_str} |\n")
    lines.append("\n---\n")
    lines.append("## Next Steps\n")
    for rel_path, _, status, issues in reports:
        if status != STATUS_COMPLETE:
            lines.append(f"- [ ] Review `{rel_path}`\n")
    lines.append("\n")
    report_path.write_text(''.join(lines), encoding='utf-8')
    return report_path


def update_master_log(root: Path, folder: Path, report_path: Path, reports: List[Tuple[Path, str, str, List[str]]]):
    master_path = root / 'full-rundown.md'
    total = len(reports)
    counts = {STATUS_COMPLETE: 0, STATUS_TUNE: 0, STATUS_BROKEN: 0}
    for _, _, status, _ in reports:
        counts[status] += 1
    entry = (
        f"| {folder} | {total} | {report_path.relative_to(root)} | "
        f"{counts[STATUS_COMPLETE]}/{counts[STATUS_TUNE]}/{counts[STATUS_BROKEN]} | "
        f"{datetime.utcnow():%Y-%m-%d %H:%M UTC} |\n"
    )

    is_new = not master_path.exists()
    header = (
        "# Full QA Audit Rundown\n\n"
        "| Folder | Files Audited | QA_REPORT Path | Status (✅/⚠️/❌) | Timestamp |\n"
        "|--------|--------------|----------------|-----------------|-----------|\n"
    )

    with master_path.open('a', encoding='utf-8') as f:
        if is_new:
            f.write(header)
        f.write(entry)


def audit_folder(folder: Path, root: Path):
    reports = []
    for item in sorted(folder.iterdir()):
        if item.name in IGNORE_DIRS:
            continue
        if item.is_file() and item.name not in IGNORE_FILES:
            summary, status, issues = analyze_file(item)
            reports.append((item.relative_to(root), summary, status, issues))
    if reports:
        report_path = write_report(folder, reports)
        update_master_log(root, folder.relative_to(root), report_path, reports)

    for item in sorted(folder.iterdir()):
        if item.name in IGNORE_DIRS:
            continue
        if item.is_dir():
            audit_folder(item, root)


def main():
    root = Path('.')
    audit_folder(root, root)


if __name__ == '__main__':
    main()
