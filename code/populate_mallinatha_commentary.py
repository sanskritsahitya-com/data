"""
Populate Mallinatha commentary for Shishupalavadham from Wikisource content
"""

import json
import re
from difflib import SequenceMatcher
from file_utils import load_text, write_text


def devanagari_to_arabic(dev_num):
    """Convert Devanagari numerals to Arabic"""
    devanagari = "०१२३४५६७८९"
    arabic = "0123456789"
    trans = str.maketrans(devanagari, arabic)
    return dev_num.translate(trans)


def is_valid_verse(text):
    """Check if text looks like a valid Sanskrit verse"""
    # Must have minimum length (verses are typically 40+ chars)
    if len(text) < 30:
        return False

    # Must contain Devanagari characters
    if not re.search(r'[ऀ-ॿ]', text):
        return False

    # Should not contain strong meta-commentary markers
    # Note: "इति" alone is too common in verses, so only check specific phrases
    meta_markers = ['प्रक्षिप्त', 'इति मन्यमानेन', 'मल्लिनाथेन', 'टीकाकारेण']
    for marker in meta_markers:
        if marker in text:
            return False

    # Should not start with commentary-like text
    if text.startswith('अत्र') or text.startswith('अस्य') or text.startswith('इति'):
        return False

    # Should not be mostly punctuation
    text_clean = re.sub(r'[।॥\s]', '', text)
    if len(text_clean) < 20:
        return False

    return True


def validate_sequence(shlokas_dict, expected_count):
    """
    Validate verse numbering - keep verses that form a reasonable sequence.

    Strategy: If we have verses numbered 1-96 expected, but we extracted
    verses 1-34 (meta-commentary) and 35-96 (actual chapter), we want to
    keep the longer continuous sequence.
    """
    if not shlokas_dict:
        return shlokas_dict

    # Find continuous sequences
    nums = sorted([int(n) for n in shlokas_dict.keys()])

    if not nums:
        return shlokas_dict

    # Find the longest continuous or near-continuous sequence
    # that ends near expected_count
    sequences = []
    current_seq = [nums[0]]

    for i in range(1, len(nums)):
        # Allow gaps of up to 5 (some verses might be genuinely missing)
        if nums[i] - current_seq[-1] <= 5:
            current_seq.append(nums[i])
        else:
            sequences.append(current_seq)
            current_seq = [nums[i]]

    sequences.append(current_seq)

    # Pick the sequence that:
    # 1. Has the most verses
    # 2. Ends closest to expected_count
    best_seq = max(sequences, key=lambda s: (len(s), -abs(s[-1] - expected_count)))

    # Keep only verses in the best sequence
    validated = {}
    for num_str in shlokas_dict.keys():
        if int(num_str) in best_seq:
            validated[num_str] = shlokas_dict[num_str]

    return validated


def parse_wikisource_content(content, expected_count=120):
    """
    Parse Wikisource content to extract shloka-commentary pairs.

    Ensemble approach:
    1. Skip to chapter heading to avoid prologues
    2. Extract verses using multiple patterns
    3. Validate verse content structure
    4. Ensure sequential ordering

    Structure:
    - Shloka text ends with ॥ NUM ॥ or ॥NUM॥ or just NUM
    - Commentary follows and ends with same number marker
    """
    original_content = content

    # STEP 1: Skip to chapter heading and detect interpolated verse sections
    chapter_names = [
        'द्वितीयः', 'तृतीयः', 'चतुर्थः', 'पञ्चमः', 'षष्ठः',
        'सप्तमः', 'अष्टमः', 'नवमः', 'दशमः', 'एकादशः',
        'द्वादशः', 'त्रयोदशः', 'चतुर्दशः', 'पञ्चदशः', 'षोडशः',
        'सप्तदशः', 'अष्टादशः', 'एकोनविंशः', 'विंशः'
    ]

    for chapter_name in chapter_names:
        heading_pattern = rf'{chapter_name}\s*सर्गः\s*[।॥]'
        heading_match = re.search(heading_pattern, content)
        if heading_match:
            # Start parsing after the heading
            content = content[heading_match.end():]
            break

    # Remove interpolated verses section if present
    # These are verses Mallinatha considered spurious and are presented separately
    # Structure: "...॥38॥ ये चतुर्स्त्रिशच्छ्लोकाः 'प्रक्षिप्ताः' इति... [34+ verses] ... ॥४७॥..."
    # We need to find where this section ends and Mallinatha's commentary resumes
    interpolated_start = r"['\"]?प्रक्षिप्ता[ःḥ]?['\"]?\s*इति मन्यमानेन मल्लिनाथेन"
    start_match = re.search(interpolated_start, content)

    if start_match:
        # Look for where Mallinatha's style commentary resumes
        # Pattern: verse ending with ॥NUM॥ where NUM > 40, indicating resumption
        # Search from the interpolated marker onwards
        search_after = content[start_match.end():]

        # Find the first occurrence of a verse number in the 40s-90s range
        # indicating Mallinatha's commentary has resumed
        resume_pattern = r'॥\s*[४-९][०-९]\s*॥'
        resume_match = re.search(resume_pattern, search_after)

        if resume_match:
            # Calculate absolute position
            interpolated_end_pos = start_match.end() + resume_match.start()
            # Remove the interpolated section
            content = content[:start_match.start()] + content[interpolated_end_pos:]
            print(f"  Removed interpolated section: chars {start_match.start()} to {interpolated_end_pos}")

    shlokas = {}

    # STEP 2: Split by ॥ NUM ॥ pattern, allowing optional spaces around number
    # This handles: ॥ १ ॥, ॥१॥, etc.
    dev_digits = "[०-९]+"
    parts = re.split(rf"॥\s*({dev_digits})\s*॥", content)

    i = 0
    while i < len(parts):
        if i + 3 < len(parts):
            shloka_text = parts[i].strip()
            num1 = devanagari_to_arabic(parts[i + 1].strip())
            commentary = parts[i + 2].strip()
            num2 = devanagari_to_arabic(parts[i + 3].strip())

            if num1 == num2:
                # Clean up shloka text - remove headings
                shloka_lines = []
                for line in shloka_text.split("\n"):
                    line = line.strip()
                    if line and not line.endswith("-") and "॥" not in line:
                        shloka_lines.append(line)

                shloka_clean = " ".join(shloka_lines).strip()

                if shloka_clean and commentary:
                    shlokas[num1] = {"text": shloka_clean, "commentary": commentary}

                i += 4
            else:
                i += 1
        else:
            break

    # Additional pass: find missing numbers sequentially
    # Since we know the expected sequence, search for each missing number
    found_nums = set(shlokas.keys())
    for line_num in range(1, expected_count + 1):
        str_num = str(line_num)
        if str_num in found_nums:
            continue

        # Convert to Devanagari
        dev_num = str_num.translate(str.maketrans("0123456789", "०१२३४५६७८९"))

        # Try multiple patterns to handle different formats
        match = None

        # Pattern 1: Standard - space before number, possible blank lines
        # Matches: "word NUM\n\n commentary ॥NUM॥" or "word NUM\n commentary ॥NUM॥"
        pattern1 = (
            rf"((?:[^\n]+\n){{1,3}}[^\n]+)\s+{dev_num}\s*\n\s*(.*?)॥\s*{dev_num}\s*॥"
        )
        match = re.search(pattern1, content, re.DOTALL)

        if not match:
            # Pattern 2: Number directly attached to word (no space)
            # Matches: "wordNUM\n commentary ॥NUM॥"
            pattern2 = rf"((?:[^\n]+\n){{1,3}}[^\n]+[ःा-ॅ]){dev_num}\s*\n\s*(.*?)॥\s*{dev_num}\s*॥"
            match = re.search(pattern2, content, re.DOTALL)

        if not match:
            # Pattern 3: ॥NUM॥ directly attached to word
            # Matches: "word॥NUM॥\n commentary ॥NUM॥"
            pattern3 = (
                rf"((?:[^\n]+\n){{1,3}}[^\n]+)॥{dev_num}॥\s*\n\s*(.*?)॥\s*{dev_num}\s*॥"
            )
            match = re.search(pattern3, content, re.DOTALL)

        if not match:
            # Pattern 4: Just the number without any dandas at end of verse
            # Matches: "word NUM\n commentary ॥NUM॥"
            # More flexible - looks for number after verse content
            pattern4 = rf"([^\n]{{40,}}\s+{dev_num})\s*\n\s*(.*?)॥\s*{dev_num}\s*॥"
            match = re.search(pattern4, content, re.DOTALL)

        if not match:
            # Pattern 5: Number on its own line after verse
            # Matches: "verse text\nNUM\n commentary ॥NUM॥"
            pattern5 = rf"([^\n]{{40,}})\s*\n\s*{dev_num}\s*\n\s*(.*?)॥\s*{dev_num}\s*॥"
            match = re.search(pattern5, content, re.DOTALL)

        if not match:
            # Pattern 6: Only ONE ॥NUM॥ marker (at end of commentary)
            # Matches: "verse text\n commentary ॥NUM॥"
            # Very flexible - just look for content followed by ॥NUM॥
            pattern6 = rf"([^\n]{{40,}})\s*\n\s*(.{{50,}}?)॥\s*{dev_num}\s*॥"
            match = re.search(pattern6, content, re.DOTALL)
            if match:
                # Need to validate this is not part of a larger match
                # Check if there's another number marker before this one
                potential_shloka = match.group(1).strip()
                potential_commentary = match.group(2).strip()

                # Skip if the commentary contains another ॥NUM॥ pattern (means we caught too much)
                if re.search(rf"॥\s*[०-९]+\s*॥", potential_commentary[:-20]):
                    match = None

        if not match:
            # Pattern 7: Just find the number ONCE anywhere, extract context around it
            # This is very permissive - only use for truly missing shlokas
            # Find the position of the number
            num_pattern = rf"(?:॥\s*)?{dev_num}(?:\s*॥)?"
            positions = [m.start() for m in re.finditer(num_pattern, content)]

            if len(positions) == 1:  # Only if number appears exactly once
                pos = positions[0]
                # Extract 300 chars before and 500 chars after
                start = max(0, pos - 300)
                end = min(len(content), pos + 500)
                context = content[start:end]

                # Try to find verse-like content (has Devanagari, proper length)
                lines_before = content[start:pos].split('\n')
                lines_after = content[pos:end].split('\n')

                # Get last 2-3 lines before number as shloka
                shloka_lines = []
                for line in lines_before[-3:]:
                    line = line.strip()
                    if line and re.search(r'[ऀ-ॿ]', line) and len(line) > 20:
                        shloka_lines.append(line)

                # Get text after number as commentary (until we hit another marker)
                commentary_text = '\n'.join(lines_after[1:])
                # Stop at next ॥NUM॥
                next_marker = re.search(rf"॥\s*[०-९]+\s*॥", commentary_text)
                if next_marker:
                    commentary_text = commentary_text[:next_marker.start()]

                if shloka_lines and len(commentary_text) > 50:
                    shloka_clean = ' '.join(shloka_lines).strip()
                    # Clean the shloka text
                    shloka_clean = re.sub(rf"[॥।]?\s*{dev_num}\s*[॥।]?$", "", shloka_clean)
                    shloka_clean = re.sub(rf"{dev_num}$", "", shloka_clean).strip()

                    if len(shloka_clean) > 30:
                        shlokas[str_num] = {
                            "text": shloka_clean,
                            "commentary": commentary_text.strip()
                        }
                        continue

        if match:
            shloka_text = match.group(1).strip()
            commentary = match.group(2).strip()

            # Clean shloka text - extract last 2-3 lines (the actual verse)
            shloka_lines = []
            for line in shloka_text.split("\n")[-3:]:
                line = line.strip()
                if line and not line.endswith("-"):
                    # Remove any markers
                    line = re.sub(rf"[॥।]?\s*{dev_num}\s*[॥।]?$", "", line)
                    line = re.sub(rf"{dev_num}$", "", line)
                    if line:
                        shloka_lines.append(line)

            shloka_clean = " ".join(shloka_lines).strip()

            # Ensure we have real content
            if shloka_clean and len(shloka_clean) > 30 and len(commentary) > 50:
                shlokas[str_num] = {"text": shloka_clean, "commentary": commentary}

    # STEP 3: Validate verse content structure
    validated_shlokas = {}
    for num, data in shlokas.items():
        if is_valid_verse(data['text']):
            validated_shlokas[num] = data

    # STEP 4: Ensure sequential ordering (filter meta-commentary sequences)
    final_shlokas = validate_sequence(validated_shlokas, expected_count)

    return final_shlokas


def normalize_shloka(text):
    """Normalize shloka text for comparison"""
    # Remove line breaks, extra spaces
    text = re.sub(r"\s+", " ", text)
    # Remove all punctuation including dandas and visargas
    text = re.sub(r"[।॥॰\s]", "", text)
    # Normalize visarga variations (ः and ह्)
    text = re.sub(r"[ःह्]", "", text)
    # Remove avagraha
    text = re.sub(r"ऽ", "", text)
    return text.strip()


def match_and_populate(text_data, wikisource_shlokas, chapter_num):
    """Match shlokas and populate commentary"""
    matches = 0
    mismatches = []

    for shloka_data in text_data.data:
        if shloka_data.c != chapter_num:
            continue

        shloka_num = shloka_data.n

        if shloka_num in wikisource_shlokas:
            wiki_shloka = normalize_shloka(wikisource_shlokas[shloka_num]["text"])
            json_shloka = normalize_shloka(shloka_data.v)

            # Compare normalized texts
            if wiki_shloka == json_shloka:
                # Match! Add commentary
                shloka_data.mn = wikisource_shlokas[shloka_num]["commentary"].replace(
                    "\\n", " "
                )
                matches += 1
            else:
                # Partial match check using sequence matching
                similarity = SequenceMatcher(None, wiki_shloka, json_shloka).ratio()
                if similarity > 0.80:  # 80% similar
                    shloka_data.mn = wikisource_shlokas[shloka_num]["commentary"]
                    matches += 1
                    print(
                        f"Warning: Partial match for shloka {shloka_num} (similarity: {similarity:.2%})"
                    )
                else:
                    mismatches.append(
                        {
                            "num": shloka_num,
                            "wiki": wikisource_shlokas[shloka_num]["text"][:50],
                            "json": shloka_data.v[:50],
                            "similarity": similarity,
                        }
                    )

    return matches, mismatches


def main(wikisource_file, chapter_num="1"):
    """Main function to populate commentary"""
    # Load text data first to get expected count
    text_data = load_text("shishupalavadham")

    # Count how many shlokas exist for this chapter
    chapter_shlokas = [s for s in text_data.data if s.c == chapter_num]
    expected_count = len(chapter_shlokas)
    print(f"Chapter {chapter_num} has {expected_count} shlokas in JSON")

    # Read Wikisource content
    with open(wikisource_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Parse shlokas and commentary with expected count
    shlokas = parse_wikisource_content(content, expected_count)
    print(f"Parsed {len(shlokas)} shloka-commentary pairs from Wikisource")

    # Add custom field definition if not present
    if not hasattr(text_data, "custom") or not text_data.custom:
        text_data.custom = {}

    if "mn" not in text_data.custom:
        text_data.custom["mn"] = {
            "name": "मल्लिनाथः",
            "lang": "sa",
            "markdown": False,
            "order": 1,
        }

    # Match and populate
    matches, mismatches = match_and_populate(text_data, shlokas, chapter_num)

    print(f"\nMatched {matches} shlokas")
    if mismatches:
        print(f"Failed to match {len(mismatches)} shlokas:")
        for m in mismatches:
            print(f"  Shloka {m['num']} (similarity: {m.get('similarity', 0):.1%}):")
            print(f"    Wiki: {m['wiki']}...")
            print(f"    JSON: {m['json']}...")

    # Write back
    write_text(text_data, "shishupalavadham")
    print(f"\nSuccessfully updated shishupalavadham.json")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(
            "Usage: python populate_mallinatha_commentary.py <wikisource_file> [chapter_num]"
        )
        sys.exit(1)

    chapter = sys.argv[2] if len(sys.argv) > 2 else "1"
    main(sys.argv[1], chapter)
