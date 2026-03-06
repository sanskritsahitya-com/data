"""
Convert single-quoted spans in mn fields to backtick spans for Markdown rendering.

Strategy:
- For entries with ODD number of single quotes: skip entirely (can't safely auto-pair)
- For entries with EVEN number: apply regex '([^'`]*)' -> `\1`
  (excludes spans that contain backticks, to avoid nested code span issues)
- After replacement, verify total backtick count is even (sanity check)
"""

import json
import re
import sys

def process_mn(text):
    """Returns (new_text, status) where status is 'converted', 'partial', 'skipped', or 'unchanged'."""
    count = text.count("'")
    if count == 0:
        return text, 'unchanged'
    if count % 2 != 0:
        return text, 'skipped'

    # Replace paired single quotes whose content has no backticks
    new_text, n_rep = re.subn(r"'([^'`]*)'", r"`\1`", text)

    if n_rep == 0:
        return text, 'unchanged'

    # Sanity check: total backtick count must be even
    if new_text.count('`') % 2 != 0:
        print(f"WARNING: odd backtick count after replacement, reverting", file=sys.stderr)
        return text, 'skipped'

    remaining = new_text.count("'")
    status = 'converted' if remaining == 0 else 'partial'
    return new_text, status


def main(dry_run=False):
    filepath = 'kiratarjuniyam/kiratarjuniyam.json'

    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    stats = {'converted': 0, 'partial': 0, 'skipped': 0, 'unchanged': 0}
    out_lines = []

    for line in lines:
        stripped = line.rstrip('\n')
        # Data entries start with {"c":
        if not stripped.startswith('{"c":'):
            out_lines.append(line)
            continue

        # Strip trailing comma if present for JSON parsing
        has_trailing_comma = stripped.endswith(',')
        json_str = stripped.rstrip(',')

        try:
            obj = json.loads(json_str)
        except json.JSONDecodeError:
            out_lines.append(line)
            continue

        if 'mn' not in obj:
            out_lines.append(line)
            stats['unchanged'] += 1
            continue

        new_mn, status = process_mn(obj['mn'])
        stats[status] += 1

        if status in ('converted', 'partial') and not dry_run:
            obj['mn'] = new_mn
            new_json = json.dumps(obj, ensure_ascii=False)
            new_line = new_json + (',' if has_trailing_comma else '') + '\n'
            out_lines.append(new_line)
        else:
            out_lines.append(line)

    print(f"Stats: {stats}")
    print(f"Total entries modified: {stats['converted'] + stats['partial']}")

    if not dry_run:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.writelines(out_lines)
        print("File written.")
    else:
        print("DRY RUN - no changes written.")


if __name__ == '__main__':
    dry_run = '--dry-run' in sys.argv
    main(dry_run=dry_run)
