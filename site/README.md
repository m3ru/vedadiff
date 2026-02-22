# VedaDiff - Running the Server

## Quick Start

To view the VedaDiff site in your browser:

1. Open a terminal in the `site` directory:
   ```bash
   cd /Users/meru/kainkaryam/vedadiff/site
   ```

2. Start a Python HTTP server:
   ```bash
   python3 -m http.server 8000
   ```

3. Open your browser and navigate to:
   ```
   http://localhost:8000
   ```

## What's Available

The site will automatically load all JSON files from the `data/processed/` directory:

- **Ṛg Veda 10.90** (`rv10-090.json`) - Purusha Suktam
- **Taittirīya Āraṇyaka 3.12–13** (`ta3-012.json`) - Purusha Suktam
- **Taittirīya Saṃhitā 1.1** (`ts1-001.json`) - Kāṇḍa 1, Prapāṭhaka 1

Select any text from the dropdown menu to view the dual-script (Devanagari + IAST) presentation with Vedic accents.

## Stopping the Server

Press `Ctrl+C` in the terminal to stop the server.
