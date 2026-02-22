#!/usr/bin/env python3
"""
Helper script to automatically update the dropdown menu in index.html
with all available JSON files from data/processed/
"""

import json
from pathlib import Path

# Paths
SITE_DIR = Path(__file__).resolve().parent.parent / "site"
INDEX_HTML = SITE_DIR / "index.html"
DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "processed"

def get_available_texts():
    """Get list of (id, title) tuples from all JSON files."""
    texts = []
    for json_file in sorted(DATA_DIR.glob("*.json")):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            texts.append((data['id'], data['title']))
    return texts

def update_dropdown():
    """Update the dropdown in index.html with all available texts."""
    texts = get_available_texts()

    if not texts:
        print("No JSON files found in data/processed/")
        return

    # Generate dropdown HTML
    options = []
    for text_id, title in texts:
        options.append(f'        <option value="{text_id}">{title}</option>')
    dropdown_html = '\n'.join(options)

    # Read current HTML
    html = INDEX_HTML.read_text(encoding='utf-8')

    # Find and replace the dropdown section
    start_marker = '<select id="text-select">'
    end_marker = '</select>'

    start_idx = html.find(start_marker)
    end_idx = html.find(end_marker, start_idx)

    if start_idx == -1 or end_idx == -1:
        print("Error: Could not find dropdown in index.html")
        return

    # Build new HTML
    new_html = (
        html[:start_idx + len(start_marker)] +
        '\n' + dropdown_html + '\n      ' +
        html[end_idx:]
    )

    # Write back
    INDEX_HTML.write_text(new_html, encoding='utf-8')

    print(f"Updated dropdown with {len(texts)} texts:")
    for text_id, title in texts:
        print(f"  - {title} ({text_id})")

if __name__ == '__main__':
    update_dropdown()
