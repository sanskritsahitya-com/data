import os
import re
import json
import sys
import argparse
from distutils.util import strtobool
from smart_json_dump import smart_json_string, smart_json_dump

# ANSI Color Codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"

# Texts the linter leaves alone. They stay in the repo and are reachable by URL,
# but are not in the catalog and are not maintained to the current rules.
SKIPPED_TEXTS = {
    "mahasubhashitasangraha",
}


# Verse numbers: digits with an optional letter suffix for inserted verses
# ("13", "13a", "1363A"). "p" is reserved as the prose separator below.
VERSE_N_RE = re.compile(r"^\d+[A-Za-z]*$")
# Prose numbers: "<anchor>p<k>[suffix]", where the anchor is the n of a verse
# earlier in the same chapter, or "0" for prose before the chapter's first verse.
# e.g. "12p3" = 3rd prose entry after verse 12; "12p3a" = inserted after 12p3.
PROSE_N_RE = re.compile(r"^(?P<anchor>\d+[A-Za-z]*?)p\d+[a-z]*$")


def _summarise(label, items, limit=10):
    shown = ", ".join(str(x) for x in items[:limit])
    more = f" ... and {len(items) - limit} more" if len(items) > limit else ""
    return f"{len(items)} {label}: {shown}{more}"


def check_text_entries(data):
    """Structural rules for verse ("v") and prose ("t") entries.

    Returns a list of error strings; empty means the file passes. Entries
    with neither "v" nor "t" (kosha, dhatu, chhanda tables) are ignored.
    """
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        return []

    entries = [
        (i, item) for i, item in enumerate(data["data"])
        if isinstance(item, dict) and ("v" in item or "t" in item)
    ]
    chapters = data.get("chapters") or []
    declared = {str(ch.get("number")) for ch in chapters if isinstance(ch, dict)}

    missing_c, undeclared_c = [], []
    verse_missing_n, bad_verse_n, bad_prose_n, unknown_anchor = [], [], [], []
    verses_seen = {}  # chapter -> set of verse n seen so far, in file order

    for i, item in entries:
        c = item.get("c")
        n = item.get("n")
        label = f"data[{i}]"

        # In a text with chapters, every entry (verse or prose) must name its
        # chapter, and that chapter must be declared. Otherwise the entry is
        # dropped from every chapter view and can't be addressed.
        if chapters:
            if c in (None, ""):
                missing_c.append(label)
            elif str(c) not in declared:
                undeclared_c.append(str(c))

        seen = verses_seen.setdefault(str(c), set())
        if "v" in item:
            if n in (None, ""):
                verse_missing_n.append(label)
            elif not VERSE_N_RE.match(str(n)) or "p" in str(n):
                bad_verse_n.append(f"{label} n={n!r}")
            else:
                seen.add(str(n))
        elif n is not None:
            # Prose numbers are optional for now, but must be well-formed when present.
            m = PROSE_N_RE.match(str(n))
            if not m:
                bad_prose_n.append(f"{label} n={n!r}")
            elif m.group("anchor") != "0" and m.group("anchor") not in seen:
                unknown_anchor.append(f"{label} n={n!r}")

    errors = []
    if missing_c:
        errors.append(_summarise("entries missing chapter (c)", missing_c))
    if undeclared_c:
        counts = sorted(set(undeclared_c))
        errors.append(_summarise("chapters used in data but not declared in 'chapters'", counts))
    if verse_missing_n:
        errors.append(_summarise("verses missing number (n)", verse_missing_n))
    if bad_verse_n:
        errors.append(_summarise("malformed verse numbers (expect digits + optional letters, no 'p')", bad_verse_n))
    if bad_prose_n:
        errors.append(_summarise("malformed prose numbers (expect <verse n>p<k> or 0p<k>)", bad_prose_n))
    if unknown_anchor:
        errors.append(_summarise("prose numbers anchored to no earlier verse in the chapter", unknown_anchor))
    return errors


def check_and_fix_file(file_path, base_dir, ignore_duplicate_verses=False):
    rel_path = os.path.relpath(file_path, base_dir)
    if rel_path.split(os.sep)[0] in SKIPPED_TEXTS:
        print(f"[ SKIP  ] {rel_path} (in SKIPPED_TEXTS)")
        return "SKIPPED", rel_path
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            original_content = f.read()

        data = json.loads(original_content)

        # Check for duplicate verse numbers
        if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
            seen_verses = set()
            duplicates = []
            for item in data["data"]:
                if not isinstance(item, dict):
                    continue
                n = item.get("n")
                if n is None:
                    continue
                c = item.get("c")

                if c:
                    verse_id = f"{c}.{n}"
                else:
                    verse_id = str(n)

                if verse_id in seen_verses:
                    duplicates.append(verse_id)
                else:
                    seen_verses.add(verse_id)

            if duplicates and not ignore_duplicate_verses:
                display_dupes = duplicates[:10]
                msg = f"Duplicate verses: {', '.join(display_dupes)}"
                if len(duplicates) > 10:
                    msg += f" ... and {len(duplicates) - 10} more"
                raise ValueError(msg)

            errors = check_text_entries(data)
            if errors:
                raise ValueError("; ".join(errors))

        expected_content = smart_json_string(data)

        if original_content != expected_content:
            # Try to fix it
            smart_json_dump(data, file_path)
            print(f"[{YELLOW} FIXED {RESET}] {rel_path}")
            return "FIXED", rel_path
        else:
            print(f"[{GREEN}  OK   {RESET}] {rel_path}")
            return "OK", rel_path

    except Exception as e:
        print(f"[{RED} ERROR {RESET}] {rel_path}: {e}")
        return "ERROR", (rel_path, str(e))


def lint_json_files(data_dir, target_files=None, ignore_duplicate_verses=False):
    changed_files = []
    error_files = []
    passed_files = []
    skipped_files = []
    total_files = 0

    print(f"Starting JSON Linter in {data_dir}...\n")

    if target_files:
        # Process specific files provided via command line
        for f in target_files:
            file_path = os.path.abspath(f)
            if not os.path.isfile(file_path):
                print(f"[{RED} SKIP  {RESET}] Not a file: {f}")
                continue
            if not file_path.endswith(".json"):
                print(f"[{RED} SKIP  {RESET}] Not a JSON file: {f}")
                continue

            total_files += 1
            status, result = check_and_fix_file(
                file_path, data_dir, ignore_duplicate_verses=ignore_duplicate_verses
            )
            if status == "FIXED":
                changed_files.append(result)
            elif status == "OK":
                passed_files.append(result)
            elif status == "SKIPPED":
                skipped_files.append(result)
            else:
                error_files.append(result)
    else:
        # Recursive walk as before
        for root, dirs, files in os.walk(data_dir):
            # Filter out hidden directories and 'code'
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "code"]

            for file in sorted(files):
                if file.endswith(".json"):
                    total_files += 1
                    file_path = os.path.join(root, file)
                    status, result = check_and_fix_file(
                        file_path,
                        data_dir,
                        ignore_duplicate_verses=ignore_duplicate_verses,
                    )
                    if status == "FIXED":
                        changed_files.append(result)
                    elif status == "OK":
                        passed_files.append(result)
                    elif status == "SKIPPED":
                        skipped_files.append(result)
                    else:
                        error_files.append(result)

    print(f"\n" + "=" * 50)
    print(f"Linter Summary")
    print(f"=" * 50)
    print(f"Total files processed: {total_files}")
    print(f"Passed:                {len(passed_files)}")
    print(f"Skipped:               {len(skipped_files)}")
    print(f"Fixed:                 {len(changed_files)}")
    print(f"Errors:                {len(error_files)}")
    print(f"=" * 50)

    if error_files or changed_files:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Lint JSON files using smart_json_dump formatting."
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Specific JSON files to lint. If omitted, all files in data/ are linted.",
    )
    parser.add_argument(
        "--ignore-duplicate-verses",
        action="store_true",
        default=False,
        help="Skip the duplicate verse number check.",
    )
    args = parser.parse_args()

    # The script is in data/code/linter.py, so data dir is one level up
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)

    # Allow the pre-commit hook (which cannot pass CLI flags) to set
    # LINTER_IGNORE_DUPLICATE_VERSES=1 in the environment instead.
    env_ignore = bool(strtobool(os.environ.get("LINTER_IGNORE_DUPLICATE_VERSES", "0")))
    ignore_duplicate_verses = args.ignore_duplicate_verses or env_ignore

    lint_json_files(
        base_dir,
        target_files=args.files if args.files else None,
        ignore_duplicate_verses=ignore_duplicate_verses,
    )
