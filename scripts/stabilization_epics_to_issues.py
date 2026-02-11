import json
import re
import sys
from pathlib import Path


def _clean_heading(text: str) -> str:
    return text.strip().lstrip('#').strip()


def parse_stabilization_epics(markdown: str):
    epic_title = None
    current = None
    issues = []

    def flush_current():
        nonlocal current
        if not current:
            return

        title = current.get("title")
        if not title:
            current = None
            return

        labels = [l.strip() for l in current.get("labels", []) if l.strip()]
        problem = (current.get("problem") or "").strip()
        ac_lines = [line.rstrip() for line in current.get("acceptance", []) if line.strip()]

        body_parts = []
        if current.get("epic"):
            body_parts.append(f"Epic: {current['epic']}")

        if problem:
            body_parts.append("Problem Summary:\n" + problem)

        if ac_lines:
            body_parts.append("Acceptance Criteria:\n" + "\n".join(ac_lines))

        body = "\n\n".join(body_parts).strip() or title

        issues.append({
            "title": title,
            "body": body,
            "labels": labels,
        })
        current = None

    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip("\n")

        # Epic headings
        if line.startswith("## "):
            flush_current()
            heading = _clean_heading(line)
            # Normalize "Epic 1: ..." -> "..." for nicer display
            m = re.match(r"Epic\s+\d+\s*:\s*(.+)$", heading, flags=re.IGNORECASE)
            epic_title = (m.group(1).strip() if m else heading)
            i += 1
            continue

        # Issue headings
        if line.startswith("### "):
            flush_current()
            heading = _clean_heading(line)
            m = re.match(r"Issue\s*:\s*(.+)$", heading, flags=re.IGNORECASE)
            title = (m.group(1).strip() if m else heading)
            current = {
                "epic": epic_title,
                "title": title,
                "problem": "",
                "acceptance": [],
                "labels": [],
            }
            i += 1
            continue

        if current:
            # Problem Summary
            if line.strip().startswith("- Problem Summary:"):
                # capture rest of line after the colon
                current["problem"] = line.split(":", 1)[1].strip()
                i += 1
                continue

            # Acceptance Criteria
            if line.strip().startswith("- Acceptance Criteria:"):
                i += 1
                # Consume subsequent bullet lines until next section marker or heading
                while i < len(lines):
                    nxt = lines[i]
                    if nxt.startswith("### ") or nxt.startswith("## "):
                        break
                    if nxt.strip().startswith("- Labels:"):
                        break
                    if nxt.strip().startswith("-"):
                        current["acceptance"].append(nxt.strip())
                    i += 1
                continue

            # Labels
            if line.strip().startswith("- Labels:"):
                labels_str = line.split(":", 1)[1].strip()
                current["labels"] = [x.strip() for x in labels_str.split(",") if x.strip()]
                i += 1
                continue

        i += 1

    flush_current()
    return issues


def main():
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/stabilization_epics_to_issues.py <input_md> <output_json>")
        return 2

    in_path = Path(sys.argv[1])
    out_path = Path(sys.argv[2])

    if not in_path.exists():
        print(f"Input markdown not found: {in_path}")
        return 2

    issues = parse_stabilization_epics(in_path.read_text(encoding="utf-8"))
    if not issues:
        print("No issues parsed from markdown; refusing to write empty issues.json")
        return 3

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(issues, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(issues)} issues to {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
