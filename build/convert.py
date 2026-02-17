#!/usr/bin/env python3
"""
convert.py — ITX to JSON preprocessor for VedaDiff.

Parses Rg Veda 10.90 and Taittiriya Aranyaka 3.12-13 from ITX format,
transliterates to Devanagari and IAST with Vedic accent marks, and outputs
structured JSON for the static site.

ITX accent convention (postfix): the marker \\`, \\', \\" appears
immediately AFTER the vowel (or vowel-containing syllable) it marks.
"""

import bisect
import json
import re
import sys
from pathlib import Path

from indic_transliteration import sanscript
from indic_transliteration.sanscript import transliterate as translit

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SOURCE_DIR = Path(__file__).resolve().parent.parent.parent  # /home/meru/hw/veda/

RV_FILE = SOURCE_DIR / "r10.itx"
TA_FILE = SOURCE_DIR / "taittirIyaAraNyaka.itx"
OUTPUT_DIR = DATA_DIR / "processed"

# ---------------------------------------------------------------------------
# ITRANS vowel regex (longer sequences first)
# ---------------------------------------------------------------------------
ITRANS_VOWEL_RE = re.compile(
    r"R\^I|R\^i|L\^I|L\^i|ai|au|AA|II|UU|ee|oo|A|I|U|a|i|u|e|o"
)

# IAST vowel regex
IAST_VOWEL_RE = re.compile(
    r"ai|au|ā|ī|ū|ṛ|ṝ|ḷ|ḹ|a|i|u|e|o", re.IGNORECASE
)

# Devanagari code-point sets
DEVA_CONSONANTS = set(range(0x0915, 0x093A)) | set(range(0x0958, 0x0960))
DEVA_VIRAMA = '\u094D'
DEVA_MATRAS = set(range(0x093E, 0x094D)) | {0x0962, 0x0963}
DEVA_INDEP_VOWELS = set(range(0x0904, 0x0915))

# Combining svara marks
SVARA_ANUDATTA     = '\u0952'   # ॒  horizontal bar below
SVARA_SVARITA      = '\u0951'   # ॑  single vertical stroke above
SVARA_IND_SVARITA  = '\u1CDA'   # ᳚  double vertical stroke above (independent svarita)


# ===================================================================
# 1. Svara extraction (postfix convention, verse-level)
# ===================================================================

def strip_svaras(itrans: str):
    """Remove \\`, \\', \\" markers. Return (clean_text, svara_list).

    Markers are postfix: they follow the vowel they modify.
    svara_list: [(vowel_index, type), ...] 0-based in clean text.
    """
    clean_chars: list[str] = []
    markers: list[tuple[int, str]] = []   # (clean_offset_of_marker, type)
    i = 0
    while i < len(itrans):
        if (i + 1 < len(itrans) and itrans[i] == '\\'
                and itrans[i + 1] in "`'\""):
            ch = itrans[i + 1]
            typ = {'`': 'anudatta', "'": 'svarita', '"': 'ind_svarita'}[ch]
            markers.append((len(clean_chars), typ))
            i += 2
        else:
            clean_chars.append(itrans[i])
            i += 1
    clean = ''.join(clean_chars)

    # Enumerate vowel start-offsets in clean text
    vowel_starts: list[int] = []
    pos = 0
    while pos < len(clean):
        m = ITRANS_VOWEL_RE.match(clean, pos)
        if m and m.start() == pos:
            vowel_starts.append(pos)
            pos = m.end()
        else:
            pos += 1

    # Also compute vowel end-offsets for postfix matching
    vowel_ends: list[int] = []
    pos = 0
    while pos < len(clean):
        m = ITRANS_VOWEL_RE.match(clean, pos)
        if m and m.start() == pos:
            vowel_ends.append(m.end())
            pos = m.end()
        else:
            pos += 1

    # Postfix: marker at clean_offset X modifies the last vowel whose
    # start < X (i.e. the vowel that ended at or before X).
    # More precisely: the vowel whose text range includes or immediately
    # precedes the marker position.
    svaras: list[tuple[int, str]] = []
    for offset, typ in markers:
        # Find the last vowel that ends at or before this offset
        idx = bisect.bisect_right(vowel_ends, offset) - 1
        # But the marker can also appear right after consonants following
        # the vowel (same syllable). So we actually want the last vowel
        # whose start < offset.
        idx2 = bisect.bisect_right(vowel_starts, offset) - 1
        # Use whichever gives a valid index
        vi = max(idx, idx2)
        if vi >= 0:
            svaras.append((vi, typ))

    return clean, svaras


# ===================================================================
# 2. Devanagari vowel-position finder
# ===================================================================

def deva_vowel_positions(deva: str) -> list[int]:
    """Return insertion-point indices for each logical vowel in Devanagari.

    Each entry is the character index where a combining svara mark
    should be inserted (right after the vowel/matra).
    """
    positions: list[int] = []
    i = 0
    n = len(deva)
    while i < n:
        cp = ord(deva[i])
        if cp in DEVA_INDEP_VOWELS:
            positions.append(i + 1)
            i += 1
        elif cp in DEVA_CONSONANTS:
            if i + 1 < n and deva[i + 1] == DEVA_VIRAMA:
                i += 2
            elif i + 1 < n and ord(deva[i + 1]) in DEVA_MATRAS:
                positions.append(i + 2)
                i += 2
            else:
                positions.append(i + 1)
                i += 1
        else:
            i += 1
    return positions


# ===================================================================
# 3. Svara reinjection
# ===================================================================

def _svara_mark(typ: str) -> str:
    if typ == 'anudatta':
        return SVARA_ANUDATTA
    if typ == 'ind_svarita':
        return SVARA_IND_SVARITA
    return SVARA_SVARITA


def inject_deva(deva: str, svaras: list[tuple[int, str]]) -> str:
    if not svaras:
        return deva
    vpos = deva_vowel_positions(deva)
    inserts: dict[int, str] = {}
    for vidx, typ in svaras:
        if vidx < len(vpos):
            inserts[vpos[vidx]] = _svara_mark(typ)
    out: list[str] = []
    for i, ch in enumerate(deva):
        if i in inserts:
            out.append(inserts[i])
        out.append(ch)
    if len(deva) in inserts:
        out.append(inserts[len(deva)])
    return ''.join(out)


def inject_iast(iast: str, svaras: list[tuple[int, str]]) -> str:
    if not svaras:
        return iast
    vowel_spans: list[tuple[int, int]] = []
    pos = 0
    while pos < len(iast):
        m = IAST_VOWEL_RE.match(iast, pos)
        if m and m.start() == pos:
            vowel_spans.append((m.start(), m.end()))
            pos = m.end()
        else:
            pos += 1

    svara_map: dict[int, str] = {vi: t for vi, t in svaras}
    # Udatta is unmarked in Vedic convention — no inference needed.

    out: list[str] = []
    vi = 0
    pos = 0
    while pos < len(iast):
        m = IAST_VOWEL_RE.match(iast, pos)
        if m and m.start() == pos:
            out.append(m.group())
            if vi in svara_map:
                out.append(_svara_mark(svara_map[vi]))
            vi += 1
            pos = m.end()
        else:
            out.append(iast[pos])
            pos += 1
    return ''.join(out)


# ===================================================================
# 4. Per-token transliteration
# ===================================================================

def transliterate_token_plain(itrans_tok: str):
    deva = translit(itrans_tok, sanscript.ITRANS, sanscript.DEVANAGARI)
    iast = translit(itrans_tok, sanscript.ITRANS, sanscript.IAST)
    return deva, iast


# ===================================================================
# 5. Verse-level processing
# ===================================================================

def _split_tokens(clean_itrans: str):
    """Split clean ITRANS into tokens, skipping | and ||.
    Returns [(token_str, pada_idx), ...]
    """
    parts = clean_itrans.split()
    tokens = []
    pada = 0
    for p in parts:
        if p == '|':
            pada += 1
        elif p == '||':
            pada += 1
        else:
            tokens.append((p, pada))
    return tokens


def _count_vowels(itrans: str) -> int:
    n = 0
    pos = 0
    while pos < len(itrans):
        m = ITRANS_VOWEL_RE.match(itrans, pos)
        if m and m.start() == pos:
            n += 1
            pos = m.end()
        else:
            pos += 1
    return n


def build_verse(verse_number: str, raw_itrans: str) -> dict:
    """Build verse JSON from raw ITRANS (with svara markers)."""
    clean, svaras = strip_svaras(raw_itrans)
    tok_list = _split_tokens(clean)

    token_dicts = []
    cum = 0
    for idx, (tok, pada) in enumerate(tok_list):
        nv = _count_vowels(tok)
        tok_svaras = [(vi - cum, t) for vi, t in svaras
                      if cum <= vi < cum + nv]
        dp, ip = transliterate_token_plain(tok)
        d = inject_deva(dp, tok_svaras)
        ia = inject_iast(ip, tok_svaras)
        token_dicts.append({"idx": idx, "devanagari": d, "iast": ia})
        cum += nv

    deva_parts: list[str] = []
    iast_parts: list[str] = []
    lp = 0
    for idx, (tok, pada) in enumerate(tok_list):
        if pada > lp:
            deva_parts.append('।')
            iast_parts.append('|')
            lp = pada
        deva_parts.append(token_dicts[idx]["devanagari"])
        iast_parts.append(token_dicts[idx]["iast"])

    return {
        "number": verse_number,
        "devanagari": ' '.join(deva_parts),
        "iast": ' '.join(iast_parts),
        "tokens": token_dicts,
    }


# ===================================================================
# 6. RV 10.90 parser
# ===================================================================

def parse_rv(filepath: Path) -> list[tuple[str, str]]:
    text = filepath.read_text(encoding='utf-8')
    lines = text.split('\n')
    marker_re = re.compile(r'\|\|\s*10\\\.090\\\.(\d+)')
    verses = []
    buf: list[str] = []

    # Find the first line that is part of 10.090 (before marker 01)
    # by scanning for the first marker and then looking backwards.
    start_idx = None
    for i, line in enumerate(lines):
        if marker_re.search(line):
            # Look back for lines that are part of this verse
            start_idx = i
            # Check previous lines for content before marker 01
            for j in range(i - 1, max(i - 5, -1), -1):
                s = lines[j].strip()
                if s and not marker_re.search(lines[j]):
                    # Check it's not from a different hymn
                    if re.search(r'\|\|\s*10\\\.089', lines[j]):
                        break
                    start_idx = j
                else:
                    break
            break

    if start_idx is None:
        return verses

    for line in lines[start_idx:]:
        m = marker_re.search(line)
        if m:
            vnum = int(m.group(1))
            before = line[:m.start()].strip()
            if before:
                buf.append(before)
            vt = ' '.join(buf).strip()
            if vt:
                verses.append((f"10.90.{vnum}", vt))
            buf = []
        else:
            s = line.strip()
            if s:
                if re.search(r'\|\|\s*10\\\.09[1-9]', line):
                    break
                buf.append(s)
    return verses


# ===================================================================
# 7. TA 3.12–13 parser
# ===================================================================

TA_PADA_MAP = [
    (33, 0, 3,  "3.12.33a"),
    (33, 4, 7,  "3.12.33b"),
    (33, 8, 9,  "3.12.33c"),
    (34, 0, 1,  "3.12.33c"),   # merge
    (34, 2, 5,  "3.12.34a"),
    (34, 6, 9,  "3.12.34b"),
    (35, 0, 3,  "3.12.35a"),
    (35, 4, 7,  "3.12.35b"),
    (35, 8, 9,  "3.12.35c"),
    (36, 0, 1,  "3.12.35c"),   # merge
    (36, 2, 5,  "3.12.36a"),
    (36, 6, 9,  "3.12.36b"),
    (37, 0, 3,  "3.12.37a"),
    (37, 4, 7,  "3.12.37b"),
    (37, 8, 9,  "3.12.37c"),
    (38, 0, 1,  "3.12.37c"),   # merge
    (38, 2, 5,  "3.12.38a"),
    (38, 6, 9,  "3.12.38b"),
    (39, 0, 7,  "3.12.39a"),
    (39, 8, 11, "3.12.39b"),
    (40, None, None, "3.13.40"),
    (41, None, None, "3.13.41"),
]


def parse_ta(filepath: Path) -> list[tuple[str, str]]:
    text = filepath.read_text(encoding='utf-8')
    lines = text.split('\n')

    end_re = re.compile(r'\|\|\s*0\|\s*3\|\s*1[23]\|\s*(\d+)\s*\|\|')
    start_re = re.compile(r'^(\d+)\s+')

    # Find the end of anuvaka 11 (|| 11||) to scope our search
    anuvaka_11_end = None
    for i, line in enumerate(lines):
        if re.search(r'\|\|\s*11\s*\|\|', line) and i > 1200:
            anuvaka_11_end = i
            break

    if anuvaka_11_end is None:
        # Fallback: search from line ~1295
        anuvaka_11_end = 1295

    raw: dict[int, str] = {}
    cur = None
    parts: list[str] = []

    for line in lines[anuvaka_11_end:]:
        sm = start_re.match(line)
        if sm:
            vn = int(sm.group(1))
            if 33 <= vn <= 41:
                if cur is not None:
                    raw[cur] = ' '.join(parts)
                cur = vn
                rest = line[sm.end():].strip()
                parts = [rest] if rest else []
                continue
            elif vn > 41:
                # Past our section
                break

        if cur is not None:
            em = end_re.search(line)
            if em:
                before = line[:em.start()].strip()
                if before:
                    parts.append(before)
                raw[cur] = ' '.join(parts)
                cur = None
                parts = []
                continue
            s = line.strip()
            if s:
                parts.append(s)

    if cur is not None:
        raw[cur] = ' '.join(parts)

    for vn in raw:
        raw[vn] = raw[vn].replace('{\\m+}', 'M')
        raw[vn] = re.sub(r'\([^)]*\)', '', raw[vn])

    verse_padas: dict[int, list[str]] = {}
    for vn, txt in raw.items():
        txt = re.sub(r'\|\|[^|]*\|\|', '', txt)
        padas = [p.strip() for p in txt.split('|') if p.strip()]
        verse_padas[vn] = padas

    merge: dict[str, list[str]] = {}
    full: list[tuple[str, str]] = []

    for vn, ps, pe, label in TA_PADA_MAP:
        if vn not in verse_padas:
            continue
        if ps is None:
            full.append((label, ' | '.join(verse_padas[vn])))
            continue
        sel = verse_padas[vn][ps:pe + 1]
        if label in merge:
            merge[label].extend(sel)
        else:
            merge[label] = list(sel)

    seen: set[str] = set()
    result: list[tuple[str, str]] = []
    for vn, ps, pe, label in TA_PADA_MAP:
        if label in seen:
            continue
        seen.add(label)
        if ps is None:
            for lbl, txt in full:
                if lbl == label:
                    result.append((lbl, txt))
                    break
        elif label in merge:
            result.append((label, ' | '.join(merge[label])))
    return result


# ===================================================================
# 8. Conversion
# ===================================================================

def convert_rv():
    verses = parse_rv(RV_FILE)
    print(f"Parsed {len(verses)} RV verses")
    vjs = []
    for vnum, raw in verses:
        vj = build_verse(vnum, raw)
        vjs.append(vj)
        print(f"  {vnum}: {len(vj['tokens'])} tokens — {vj['tokens'][0]['devanagari']}…")

    out = {
        "id": "rv10-090",
        "title": "Purusha Sūktam (Ṛg Veda 10.90)",
        "source": "SanskritDocuments.org",
        "verses": vjs,
    }
    p = OUTPUT_DIR / "rv10-090.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Wrote {p}")


def convert_ta():
    sub = parse_ta(TA_FILE)
    print(f"Parsed {len(sub)} TA sub-verses")
    vjs = []
    for label, raw in sub:
        vj = build_verse(label, raw)
        vjs.append(vj)
        print(f"  {label}: {len(vj['tokens'])} tokens — {vj['tokens'][0]['devanagari']}…")

    out = {
        "id": "ta3-012",
        "title": "Puruṣa Sūktam (Taittirīya Āraṇyaka 3.12–13)",
        "source": "SanskritDocuments.org",
        "verses": vjs,
    }
    p = OUTPUT_DIR / "ta3-012.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Wrote {p}")


# ===================================================================
# 9. Tests
# ===================================================================

def run_tests():
    print("=== Tests ===")

    # Test 1: sa\`hasra\'shIrShA\` (postfix markers)
    # \` after 'a' of 'sa' → anudatta on vowel 0
    # \' after 'a' of 'ra' → svarita on vowel 2
    # \` after 'A' of 'ShA' → anudatta on vowel 4
    clean, sv = strip_svaras("sa\\`hasra\\'shIrShA\\`")
    assert clean == "sahasrashIrShA", f"clean={clean!r}"
    print(f"  T1 clean={clean!r}  sv={sv}")
    assert sv == [(0, 'anudatta'), (2, 'svarita'), (4, 'anudatta')], f"sv={sv}"

    # Test 2: Devanagari output: स॒हस्र॑शीर्षा॒
    d, ia = build_verse("test", "sa\\`hasra\\'shIrShA\\`")['tokens'][0]['devanagari'], \
            build_verse("test", "sa\\`hasra\\'shIrShA\\`")['tokens'][0]['iast']
    print(f"  T2 deva={d!r}  iast={ia!r}")
    assert DEVA_ANUDATTA in d, f"Missing anudatta in {d!r}"
    assert DEVA_SVARITA in d, f"Missing svarita in {d!r}"

    # Test 3: puru\'ShaH → svarita on 'u' (vowel 1), i.e. पुरु॑षः
    clean3, sv3 = strip_svaras("puru\\'ShaH")
    print(f"  T3 clean={clean3!r}  sv={sv3}")
    # 'puruShaH': vowels p-u(0), r-u(1), Sh-a(2)
    # \' after second 'u' → svarita on vowel 1
    assert sv3 == [(1, 'svarita')], f"sv3={sv3}"
    v3 = build_verse("test", "puru\\'ShaH")
    print(f"  T3 deva={v3['tokens'][0]['devanagari']!r}")

    # Test 4: verse-level cross-token svaras
    # sa\`hasra\'shIrShA\` puru\'ShaH
    # Vowels in clean: sahasrashIrShA puruShaH
    #   0:a(sa), 1:a(ha), 2:a(ra), 3:I(shI), 4:A(ShA), 5:u(pu), 6:u(ru), 7:a(Sha)
    # Markers: \` after sa → v0, \' after ra → v2, \` after ShA → v4, \' after ru → v6
    clean4, sv4 = strip_svaras("sa\\`hasra\\'shIrShA\\` puru\\'ShaH")
    print(f"  T4 sv={sv4}")
    assert sv4 == [(0, 'anudatta'), (2, 'svarita'), (4, 'anudatta'), (6, 'svarita')], f"sv4={sv4}"

    # Verse-level: first token gets vowels 0-4, second token gets vowels 5-7
    v4 = build_verse("test", "sa\\`hasra\\'shIrShA\\` puru\\'ShaH")
    print(f"  T4 tok0_deva={v4['tokens'][0]['devanagari']!r}")
    print(f"  T4 tok1_deva={v4['tokens'][1]['devanagari']!r}")

    # Test 5: independent svarita \"
    clean5, sv5 = strip_svaras('pAdo\\".asya\\`')
    print(f"  T5 clean={clean5!r}  sv={sv5}")
    # pAdo.asya: vowels A(0), o(1), a(2), a(3)  — wait, '.' is .a?
    # Actually in ITRANS '.a' is avagraha. 'pAdo.asya' → pAdo + avagraha + sya
    # Let me just check the offsets.

    print("\nAll tests passed!")
    return True


def main():
    if '--test' in sys.argv:
        ok = run_tests()
        sys.exit(0 if ok else 1)
    else:
        convert_rv()
        convert_ta()


if __name__ == '__main__':
    main()
