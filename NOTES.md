# VedaDiff — Implementation Notes

## What This Is

A static site comparing Purusha Suktam across two Vedic recensions:
- **Ṛg Veda 10.90** (16 verses)
- **Taittirīya Āraṇyaka 3.12–13** (19 sub-verses, including uttara-nārāyaṇa)

Two views: a dual-script (Devanagari / IAST) reader with hover-linked tokens, and a word-level recension diff.

Source data comes from SanskritDocuments.org ITX files at `/home/meru/hw/veda/r10.itx` and `/home/meru/hw/veda/taittirIyaAraNyaka.itx`.

---

## Directory Layout

```
vedadiff/
├── build/
│   ├── convert.py            # ITX → JSON preprocessor
│   └── requirements.txt      # indic-transliteration
├── data/
│   ├── processed/
│   │   ├── rv10-090.json     # 16 RV verses, accented Devanagari + IAST
│   │   └── ta3-012.json      # 19 TA sub-verses
│   └── alignments/
│       └── purusha-suktam.json  # verse-pair mapping for diff view
├── site/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── siddhanta.ttf         # self-hosted Vedic font
│   └── data -> ../data       # symlink so http.server can reach JSON
└── .venv/                    # Python venv (indic-transliteration installed)
```

### Serving

```bash
cd vedadiff/site && python3 -m http.server
```

The `site/data` symlink exists because `python3 -m http.server` only serves files under its root directory. Without it, `fetch("data/processed/rv10-090.json")` would 404.

### Regenerating JSON

```bash
.venv/bin/python3 build/convert.py        # full conversion
.venv/bin/python3 build/convert.py --test  # run sanity tests
```

---

## convert.py — Key Design Decisions

### ITX Accent Convention: Postfix

This was the biggest gotcha. ITX svara markers (`\``, `\'`, `\"`) are **postfix** — they appear immediately **after** the vowel they modify, not before it.

Example: `sa\`hasra\'shIrShA\``
- `\`` after the `a` of `sa` → anudatta on that `a` (vowel 0)
- `\'` after the `a` of `ra` → svarita on that `a` (vowel 2)
- `\`` after the `A` of `ShA` → anudatta on that `A` (vowel 4)
- Result: स॒हस्र॑शीर्षा॒

Initially implemented as prefix (marker applies to the *next* vowel). This produced wrong accent placement. Fixed by using `bisect_right` on vowel start offsets to find the last vowel whose start is ≤ the marker position.

### Verse-Level Svara Extraction

Svara markers can span whitespace token boundaries. Example: `shIrShA\` puru\'ShaH` — the `\`` after `ShA` followed by space applies to the `A` of `ShA`, not to `puru`. Extracting svaras at the verse level (before tokenization) and then distributing them to tokens by cumulative vowel count solves this.

Flow:
1. `strip_svaras(raw_itrans)` → `(clean_text, [(vowel_index, type), ...])`
2. `_split_tokens(clean_text)` → `[(token, pada_idx), ...]`
3. For each token, count its vowels, filter svaras by cumulative range
4. Transliterate each token (clean ITRANS → Devanagari / IAST)
5. Reinject svara marks into the transliterated output

### Three Svara Types

| ITX marker | Type | Unicode | Visual |
|------------|------|---------|--------|
| `\`` | anudatta | U+0952 | ॒ horizontal bar below |
| `\'` | svarita (dependent) | U+0951 | ॑ single vertical stroke above |
| `\"` | independent svarita | U+1CDA | ᳚ double vertical stroke above |

The same Unicode characters are used for both Devanagari and IAST output. This requires the Siddhanta font (or another Vedic-capable font) to render correctly on Latin characters.

Udatta is unmarked (Vedic convention: only anudatta and svarita are marked).

### Devanagari Vowel Position Counting

To reinject accent marks into Devanagari, we need to find where each logical vowel is in the output string. The `deva_vowel_positions()` function walks the string identifying:
- Independent vowels (U+0904–U+0914)
- Consonant + matra (the matra is the vowel)
- Consonant with no virama and no matra (inherent `a`)
- Consonant + virama = conjunct, no vowel

Returns insertion points (character indices where the combining mark goes).

### RV Parser

Source: `/home/meru/hw/veda/r10.itx`, around lines 2118–2149.

Each verse spans 2 lines. The verse-end marker is `|| 10\.090\.NN`. The parser scans backwards from the first marker to find the start of verse 1's text (since the text precedes its own marker).

Produces 16 verses numbered `10.90.1` through `10.90.16`.

### TA Parser

Source: `/home/meru/hw/veda/taittirIyaAraNyaka.itx`, around lines 1299–1349.

**Section scoping:** The file has multiple anuvakas with overlapping verse numbers. We scope by finding the `|| 11||` anuvaka-end marker first, then only parse verse numbers 33–41 from lines after that marker.

**Pre-processing:**
- `{\m+}` → `M` (anusvara notation)
- Remove parenthetical variants `( ... )`

**Pada-level splitting:** TA verses contain ~10 padas each (≈2.5 RV verses). A hard-coded `TA_PADA_MAP` table splits them into sub-verses aligned with RV verses. Cross-verse padas (e.g., RV 10.90.3 spans TA verse 33 padas 8–9 and verse 34 padas 0–1) are merged.

Sub-verse labels: `3.12.33a`, `3.12.33b`, etc.

### Known Recension Differences

The diff view highlights genuine textual differences, including:
- `haviṣā` — RV has single svarita `\'`, TA has independent svarita `\"`
- Word forms: `sahasrākṣaḥ` (RV, with visarga) vs `sahasrākṣassahasrapāt` (TA, sandhi'd)
- Verse ordering: RV 10.90.15 appears between RV 6 and 7 in the TA sequence
- Extra TA content: `vedāhametam` section (3.12.39a), uttara-nārāyaṇa (3.13.40–41)

---

## Alignment File

`data/alignments/purusha-suktam.json` maps RV↔TA verse pairs in TA sequential order. Three pairs have `"left": null` (TA-only content not in RV). One pair has a reordering note (RV 15 between 6 and 7).

---

## Static Site

### HTML

Single page, two `<section>` elements toggled by nav buttons:
- `#dual-view` — text selector dropdown, dual/single layout toggle button, two panes (Devanagari / IAST). The "IAST Only" button hides the Devanagari pane and switches to a single-column layout.
- `#diff-view` — comparison selector, script toggle button, two panes (left / right recension)

### CSS (168 lines)

Dark theme based on VS Code / Compiler Explorer palette. CSS Grid two-pane layout. Diff colors: green (insert), red (delete), yellow (modify). Token hover highlight.

### JS (381 lines)

- **Data loading:** Fetch + cache JSON files
- **Dual-script view:** Renders all verses with per-token `<span>` elements carrying `data-v` (verse number) and `data-t` (token index) attributes
- **Hover linking:** `mouseenter`/`mouseleave` event delegation adds/removes `.highlight` class on matching spans across panes
- **Synchronized scrolling:** Ratio-based scroll sync between paired panes
- **LCS diff:** Standard DP longest common subsequence on IAST token arrays, backtrack to edit script. Post-processing: consecutive delete+insert with >50% character overlap → modify
- **Diff rendering:** Side-by-side with `diff-equal`/`diff-insert`/`diff-delete`/`diff-modify` CSS classes. `null` alignment entries show grey placeholder
- **Script toggle:** Switches diff view between Devanagari and IAST

### Font

**Siddhanta** (siddhanta.ttf, self-hosted, CC BY-NC-ND 3.0) — a Devanagari font specifically designed for Vedic texts. Renders U+0951 as a proper vertical stroke (not a slanted accent) and supports U+1CDA (double svarita). Loaded via `@font-face` in CSS.

Google Fonts `Noto Serif Devanagari` is listed as fallback.

---

## Issues Encountered & Resolved

1. **404 on JSON files** — `python3 -m http.server` from `site/` couldn't reach `../data/`. Fixed with symlink `site/data -> ../data` and changed fetch paths from `../data/` to `data/`.

2. **RV verse 1 missing first half** — Parser started collecting only after the first verse-end marker, so the text before `|| 10\.090\.01` was skipped. Fixed by scanning backwards from the first marker to find the start of verse 1.

3. **TA parser matching wrong section** — `^(\d+)\s+` matched verse "33" from anuvaka 11 (line 224) instead of anuvaka 12 (line 1299). Fixed by scoping the search to start after the `|| 11||` anuvaka-end marker.

4. **Prefix vs postfix svara convention** — Initial implementation treated markers as prefix (applying to the next vowel). Testing against known output (स॒हस्र॑शीर्षा॒) proved they're postfix. Rewritten with `bisect_right` on vowel start offsets.

5. **Noto Sans Devanagari accent rendering** — Rendered U+0951 as a slanted accent mark instead of a vertical stroke. Switched to Noto Serif Devanagari (slight improvement), then to self-hosted Siddhanta font (correct vertical stroke rendering).

6. **IAST accent style** — Initially used combining acute/grave/macron-below (standard IAST convention). Changed to use the same U+0951/U+0952/U+1CDA characters as Devanagari so both scripts render identically via Siddhanta.

7. **Independent svarita (`\"`) rendering as single stroke** — Both `\'` and `\"` were mapped to U+0951. Added U+1CDA (VEDIC TONE DOUBLE SVARITA) for `\"`, confirmed Siddhanta has the glyph via fontTools inspection.

---

## Possible Future Work

- Character-level diff within modified tokens (highlight differing chars with nested spans)
- Pada boundary markers in diff view
- Additional texts / alignment files
- Search / jump-to-verse
- Mobile-responsive layout
- Export / permalink support
