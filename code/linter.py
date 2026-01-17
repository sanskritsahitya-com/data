import os
import json
import sys
import argparse
from smart_json_dump import smart_json_string, smart_json_dump

# ANSI Color Codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def check_and_fix_file(file_path, base_dir):
    rel_path = os.path.relpath(file_path, base_dir)
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

            if duplicates:
                display_dupes = duplicates[:5]
                msg = f"Duplicate verses: {', '.join(display_dupes)}"
                if len(duplicates) > 5:
                    msg += f" ... and {len(duplicates) - 5} more"
                raise ValueError(msg)

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


def lint_json_files(data_dir, target_files=None):
    changed_files = []
    error_files = []
    passed_files = []
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
            status, result = check_and_fix_file(file_path, data_dir)
            if status == "FIXED":
                changed_files.append(result)
            elif status == "OK":
                passed_files.append(result)
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
                    status, result = check_and_fix_file(file_path, data_dir)
                    if status == "FIXED":
                        changed_files.append(result)
                    elif status == "OK":
                        passed_files.append(result)
                    else:
                        error_files.append(result)

    print(f"\n" + "=" * 50)
    print(f"Linter Summary")
    print(f"=" * 50)
    print(f"Total files processed: {total_files}")
    print(f"Passed:                {len(passed_files)}")
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
    args = parser.parse_args()

    # The script is in data/code/linter.py, so data dir is one level up
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(script_dir)

    lint_json_files(base_dir, target_files=args.files if args.files else None)
