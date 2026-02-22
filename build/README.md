# VedaDiff Build Tools

This directory contains the conversion pipeline for processing ITX files from sanskritdocuments.org into dual-script JSON format for the VedaDiff viewer.

## Quick Start: Adding a New Text

1. **Download ITX file** from sanskritdocuments.org and save to `/Users/meru/kainkaryam/`
   ```bash
   # Example: download a file
   curl -o /Users/meru/kainkaryam/newtext.itx https://sanskritdocuments.org/...
   ```

2. **Run the converter**:
   ```bash
   cd /Users/meru/kainkaryam/vedadiff/build
   source ~/hackathons/aiatl/bin/activate
   python3 convert.py /Users/meru/kainkaryam/newtext.itx
   ```

3. **Update the dropdown** (automatic):
   ```bash
   python3 update_dropdown.py
   ```

4. **View in browser**: Refresh your browser at http://localhost:8000 and select the new text from the dropdown!

## How It Works

### convert.py

The main conversion script with a **generic ITX parser** that handles any file from sanskritdocuments.org:

- **Extracts metadata** from ITX file headers (`% Text title: ...`)
- **Finds all verses** marked with `|| N| N| N||` pattern
- **Generates labels** from marker numbers (e.g., `|| 1| 2| 3||` → "1.2.3")
- **Transliterates** to Devanagari and IAST with Vedic accent marks
- **Outputs JSON** to `../data/processed/<filename>.json`

**Usage:**
```bash
# Process all ITX files in /Users/meru/kainkaryam/
python3 convert.py

# Process specific file(s)
python3 convert.py /path/to/file.itx

# Run tests
python3 convert.py --test
```

### update_dropdown.py

Automatically updates the dropdown menu in `site/index.html` with all available texts from `data/processed/`:

```bash
python3 update_dropdown.py
```

This scans all JSON files and updates the `<select>` element with the correct IDs and titles.

## File Structure

```
vedadiff/
├── build/
│   ├── convert.py           # Main conversion script
│   ├── update_dropdown.py   # Dropdown updater
│   └── README.md            # This file
├── data/
│   ├── processed/           # Output JSON files
│   │   ├── rv10-090.json
│   │   ├── ta3-012.json
│   │   ├── taitsamhita1.json
│   │   └── ...
│   └── alignments/          # Recension comparison data
└── site/
    ├── index.html           # Main HTML file
    ├── app.js               # Frontend application
    └── data -> ../data      # Symlink to data directory
```

## ITX File Format

The parser handles standard ITX format from sanskritdocuments.org:

- **Metadata**: Lines starting with `%` in the header
- **Verse markers**: `|| N| N| N||` or `|| N| N| N| N||`
- **Svara marks**: Postfix notation (`\`` for anudatta, `\'` for svarita, `\"` for independent svarita)
- **Anusvara**: `{m+}` or `{\\m+}` → M

## Requirements

```bash
pip install indic-transliteration
```

## Examples

### Example 1: Full Pipeline
```bash
# Download a new text
cd /Users/meru/kainkaryam
curl -O https://sanskritdocuments.org/doc_veda/some-text.itx

# Convert it
cd vedadiff/build
source ~/hackathons/aiatl/bin/activate
python3 convert.py /Users/meru/kainkaryam/some-text.itx

# Update dropdown
python3 update_dropdown.py

# View in browser
cd ../site
python3 -m http.server 8000
# Open http://localhost:8000
```

### Example 2: Batch Processing
```bash
# Process all ITX files at once
python3 convert.py
python3 update_dropdown.py
```

## Troubleshooting

**Problem**: JSON file created but not showing in dropdown
- **Solution**: Run `python3 update_dropdown.py` to regenerate the dropdown

**Problem**: Parser not finding verses
- **Solution**: Check if the ITX file uses the standard `|| N| N| N||` marker format

**Problem**: Title showing as filename
- **Solution**: Check if the ITX file has a `% Text title:` line in the header

## Advanced: Legacy Parsers

The script still includes legacy parsers (`parse_rv`, `parse_ta`, `parse_ts`) for backward compatibility, but they are no longer used. The generic `parse_itx` function handles all files.
