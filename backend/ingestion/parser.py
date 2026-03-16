import re
from typing import TypedDict

class SectionBlock(TypedDict):
    type: str  # "narrative"
    title: str
    content: str

PART_PATTERN = re.compile(r"(?i)\n\s*(PART\s+[IVX]+)")
ITEM_PATTERN = re.compile(r"(?i)\n\s*(Item\s+\d+[A-Z]?\.)")
SUBSECTION_PATTERN = re.compile(r"(^\n?[A-Z][A-Z\s,]{10,}\n|(?i:\n\s*Note\s+\d+\s+[-–]\s*.*))", re.MULTILINE)

# Detects a single TOC index line: "| Section Title | 14" (pipe-delimited, ends with page number)
_TOC_REF_LINE_RE = re.compile(r'^\|.+\|\s*\d+\s*$', re.MULTILINE)

# XBRL inline tag lines: very long, start with ticker-date-false sequence.
# They always appear within the first 15 lines of a filing.
# Note: the blob may contain spaces (from pipe-table chars embedded at end),
# so we rely on the regex match + minimum length only — no no-space check.
_XBRL_TAG_RE = re.compile(r'^[a-zA-Z0-9]+-\d{8}false\d{4}', re.ASCII)

def clean_text(raw: str) -> str:
    lines = raw.split("\n")

    # Strip XBRL inline-tag lines: within first 15 lines, >500 chars long,
    # starting with the known <ticker>-<date>false<period> pattern.
    lines = [
        line for i, line in enumerate(lines)
        if not (
            i < 15
            and len(line) > 500
            and _XBRL_TAG_RE.match(line.strip())
        )
    ]

    separator_idx = None
    for i, line in enumerate(lines[:50]):
        if line.strip().startswith("=" * 10):
            separator_idx = i
            break

    content_lines = lines[separator_idx + 1:] if separator_idx is not None else lines[10:]
    text = "\n".join(content_lines)

    # 1. Collapse multiple blank lines -> single newline
    text = re.sub(r'\n{2,}', '\n', text)
    # 2. Collapse multiple spaces/tabs -> single space
    text = re.sub(r'[ \t]{2,}', ' ', text)
    # 3. Fix squashed headers (PART … Item …)
    text = re.sub(r"(PART\s+[IVX]+.*?)(Item\s+\d+[A-Z]?\.?)", r"\1\n\2", text, flags=re.IGNORECASE)
    # 4. Strip trailing whitespace
    text = text.strip()

    return text

def parse_metadata_from_header(text: str) -> dict:
    meta = {}
    for line in text.split("\n")[:10]:
        if ":" in line:
            key, _, val = line.partition(":")
            meta[key.strip().lower().replace(" ", "_")] = val.strip()
    return meta

def parse_metadata_from_filename(filename: str) -> dict:
    base = filename.replace("_full.txt", "")
    parts = base.split("_")
    meta = {"ticker": parts[0]}
    if len(parts) >= 3:
        meta["filing_type"] = parts[1]
    if len(parts) >= 4:
        meta["quarter"] = parts[2] if parts[2].startswith("20") is False else None
        meta["filing_date"] = parts[-1]
    if len(parts) == 3:
        meta["filing_date"] = parts[2]
    return meta

def build_chunk_header(meta: dict) -> str:
    lines = []
    field_map = [
        ("company", "Company"),
        ("ticker", "Ticker"),
        ("filing_type", "Filing Type"),
        ("filing_date", "Filing Date"),
        ("quarter", "Quarter"),
        ("cik", "CIK"),
        ("source", "Source"),
    ]
    for key, label in field_map:
        if key in meta and meta[key]:
            lines.append(f"{label}: {meta[key]}")
    return "\n".join(lines)

def classify_sections(cleaned_text: str) -> list[SectionBlock]:
    if not cleaned_text:
        return []

    blocks: list[SectionBlock] = []

    # 0. Detect and skip the TOC.
    # The TOC is only an index (page numbers); it carries no semantic value for
    # retrieval.  We use the match purely to advance body_text past the TOC so
    # TOC lines don't contaminate real section chunks.
    toc_match = re.search(r"(?i)(TABLE\s+OF\s+CONTENTS.*?\n)(?=\s*PART\s+[IVX]+)", cleaned_text, flags=re.DOTALL)
    body_text = cleaned_text[toc_match.end(1):] if toc_match else cleaned_text

    # 1. Split by PART
    part_splits = re.split(PART_PATTERN, "\n" + body_text)
    
    parts = []
    if len(part_splits) == 1:
        parts = [("Unknown Part", part_splits[0])]
    else:
        parts = [("Unknown Part", part_splits[0])]
        for i in range(1, len(part_splits), 2):
            parts.append((part_splits[i].strip(), part_splits[i+1]))

    for part_title, part_content in parts:
        if not part_content.strip():
            continue
            
        # 2. Split by ITEM
        item_splits = re.split(ITEM_PATTERN, "\n" + part_content)
        items = []
        if len(item_splits) == 1:
            items = [("Unknown Item", item_splits[0])]
        else:
            items = [("Unknown Item", item_splits[0])]
            for i in range(1, len(item_splits), 2):
                items.append((item_splits[i].strip(), item_splits[i+1]))
                
        for item_title, item_content in items:
            if not item_content.strip():
                continue
                
            # 3. Split by SUBSECTION
            sub_splits = re.split(SUBSECTION_PATTERN, item_content)
            subs = []
            if len(sub_splits) == 1:
                subs = [("", sub_splits[0])]
            else:
                subs = [("", sub_splits[0])]
                for i in range(1, len(sub_splits), 2):
                    subs.append((sub_splits[i].strip(), sub_splits[i+1]))
                    
            for sub_title, sub_content in subs:
                content = sub_content.strip()
                if not content:
                    continue

                # Skip TOC-reference-only blocks.
                # A block is a pure TOC entry when EVERY non-empty line is a
                # pipe-table row that ends with a bare page number, e.g.:
                #   | Financial Statements | 1
                # These appear when the ITEM regex matches TOC lines instead
                # of real document sections.
                non_empty_lines = [l for l in content.splitlines() if l.strip()]
                if non_empty_lines and all(
                    _TOC_REF_LINE_RE.match(l.strip()) for l in non_empty_lines
                ):
                    continue

                title_parts = [p for p in [part_title, item_title, sub_title] if p and p not in ("Unknown Part", "Unknown Item")]
                full_title = " > ".join(title_parts) if title_parts else "Document Start"

                blocks.append({
                    "type": "narrative",
                    "title": full_title,
                    "content": content
                })

    return blocks
