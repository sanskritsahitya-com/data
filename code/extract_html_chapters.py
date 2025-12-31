"""
Extract Sanskrit text from Wikisource HTML files for Shishupalavadham
"""

import re
import os
from pathlib import Path

def extract_chapter_number(html_content):
    """Extract chapter number from HTML content by looking at title tag"""
    # Look for chapter name in the title tag for accuracy
    chapter_names = {
        'द्वितीयः': 2, 'तृतीयः': 3, 'चतुर्थः': 4, 'पञ्चमः': 5,
        'षष्ठः': 6, 'सप्तमः': 7, 'अष्टमः': 8, 'नवमः': 9, 'दशमः': 10,
        'एकादशः': 11, 'द्वादशः': 12, 'त्रयोदशः': 13, 'चतुर्दशः': 14,
        'पञ्चदशः': 15, 'षोडशः': 16, 'सप्तदशः': 17, 'अष्टादशः': 18,
        'एकोनविंशः': 19, 'एकोनविंशतितमः': 19, 'विंशः': 20, 'विंशतितमः': 20
    }

    # Extract title tag first for most accurate detection
    title_match = re.search(r'<title>([^<]+)</title>', html_content)
    if title_match:
        title = title_match.group(1)
        # Look for chapter name + सर्गः pattern in title
        for name, num in chapter_names.items():
            if f'{name} सर्गः' in title or f'{name}सर्गः' in title:
                return num

    # Fallback: search in entire content (less reliable)
    for name, num in chapter_names.items():
        if name in html_content:
            return num

    return None

def extract_text_from_html(html_content, chapter_num=None):
    """Extract Sanskrit text content from HTML"""
    # Find the prp-pages-output div which contains the actual Sanskrit content
    # Use a more greedy approach to capture all content until the end of the page
    match = re.search(r'<div[^>]*class="prp-pages-output"[^>]*>(.*)',
                     html_content, re.DOTALL)

    if not match:
        print("  Warning: Could not find prp-pages-output div")
        return ""

    # Get everything after the opening div
    content = match.group(1)

    # Stop at common end markers (footer, printfooter, etc.)
    for end_marker in ['<div class="printfooter"', '<div id="catlinks"', '</body>', '<noscript>']:
        if end_marker in content:
            content = content[:content.index(end_marker)]
            break

    # Look for actual chapter heading to skip prologue sections like कविवंशवर्णनम्
    # Pattern: <big>द्वितीयः सर्गः ।</big> or similar
    chapter_names = {
        2: 'द्वितीयः', 3: 'तृतीयः', 4: 'चतुर्थः', 5: 'पञ्चमः',
        6: 'षष्ठः', 7: 'सप्तमः', 8: 'अष्टमः', 9: 'नवमः', 10: 'दशमः',
        11: 'एकादशः', 12: 'द्वादशः', 13: 'त्रयोदशः', 14: 'चतुर्दशः',
        15: 'पञ्चदशः', 16: 'षोडशः', 17: 'सप्तदशः', 18: 'अष्टादशः',
        19: 'एकोनविंशः', 20: 'विंशः'
    }

    if chapter_num and chapter_num in chapter_names:
        chapter_name = chapter_names[chapter_num]
        # Look for the chapter heading pattern
        heading_pattern = rf'<big>{chapter_name}[ःḥ]?\s*सर्गः\s*[।॥]?\s*</big>'
        heading_match = re.search(heading_pattern, content)
        if heading_match:
            # Start extraction from the chapter heading
            content = content[heading_match.start():]
        else:
            # Try without <big> tags
            heading_pattern = rf'{chapter_name}[ःḥ]?\s*सर्गः\s*[।॥]'
            heading_match = re.search(heading_pattern, content)
            if heading_match:
                content = content[heading_match.start():]

    # Replace <br> and <br /> with newlines
    content = re.sub(r'<br\s*/?>',  '\n', content)

    # Remove all other HTML tags
    content = re.sub(r'<[^>]+>', ' ', content)

    # Decode HTML entities
    content = content.replace('&#160;', ' ')
    content = content.replace('&nbsp;', ' ')
    content = content.replace('&lt;', '<')
    content = content.replace('&gt;', '>')
    content = content.replace('&amp;', '&')

    # Clean up: remove lines that don't have Devanagari content
    lines = []
    for line in content.split('\n'):
        line = ' '.join(line.split())  # Normalize whitespace
        if line and re.search(r'[ऀ-ॿ]', line):
            lines.append(line)

    return '\n'.join(lines)

def main():
    """Process all HTML files in shishupalavadham directory"""
    html_dir = Path('/mnt/d/sanskrit/sanskritsahitya-com/data/shishupalavadham')

    # Find all HTML files (those starting with 23)
    html_files = sorted([f for f in html_dir.iterdir() if f.name.startswith('23')])

    print(f"Found {len(html_files)} HTML files")

    # Map files to chapters
    file_to_chapter = {}

    for html_file in html_files:
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()

        chapter_num = extract_chapter_number(content)
        if chapter_num:
            file_to_chapter[html_file] = chapter_num
            print(f"{html_file.name} -> Chapter {chapter_num}")

    print(f"\nMapped {len(file_to_chapter)} files to chapters")

    # For chapters with multiple files, keep only the one with most content
    best_file_per_chapter = {}
    for html_file, chapter_num in file_to_chapter.items():
        with open(html_file, 'r', encoding='utf-8') as f:
            html_content = f.read()
        text_content = extract_text_from_html(html_content, chapter_num)
        content_length = len(text_content)

        if chapter_num not in best_file_per_chapter or content_length > best_file_per_chapter[chapter_num][1]:
            best_file_per_chapter[chapter_num] = (html_file, content_length, text_content)

    # Extract text for each chapter
    output_dir = html_dir

    for chapter_num in sorted(best_file_per_chapter.keys()):
        html_file, content_length, text_content = best_file_per_chapter[chapter_num]
        print(f"\nProcessing Chapter {chapter_num}...")
        print(f"  Using {html_file.name}")

        # Save to text file
        output_file = output_dir / f'chapter{chapter_num}_wikisource.txt'
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text_content)

        print(f"  Saved to {output_file.name}")
        print(f"  Extracted {content_length} characters")

if __name__ == '__main__':
    main()
