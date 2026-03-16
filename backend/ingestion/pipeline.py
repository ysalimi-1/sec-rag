import os
from backend.config import CORPUS_DIR
from backend.db import get_conn, init_db
from backend.ingestion.parser import (
    parse_metadata_from_header,
    build_chunk_header,
    clean_text,
    classify_sections,
)
from backend.ingestion.chunker import chunk_section, count_tokens
from backend.retrieval.embeddings import embed_texts


def _section_label(title: str) -> str:
    """Short section label for metadata (e.g. 'Item 7', 'Note 3')."""
    if not title:
        return ""
    # Take first 80 chars; often "Item 7. Management's Discussion..."
    return title[:80].strip()


def ingest(overwrite: bool = False):
    init_db(overwrite=overwrite)
    corpus_path = CORPUS_DIR

    files = sorted(f for f in os.listdir(corpus_path) if f.endswith("_full.txt"))
    print(f"Found {len(files)} files")

    conn = get_conn()
    cur = conn.cursor()

    for i, filename in enumerate(files):
        cur.execute("SELECT id FROM documents WHERE filename = %s", (filename,))
        
        if cur.fetchone():
            print(f"  [{i+1}/{len(files)}] {filename} - skipped (already processed)")
            continue

        filepath = os.path.join(corpus_path, filename)
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            raw = f.read()

        meta = parse_metadata_from_header(raw)
        cleaned = clean_text(raw)

        if not cleaned or len(cleaned) < 100:
            print(f"  [{i+1}/{len(files)}] {filename} - skipped (too short after cleaning)")
            continue

        header = build_chunk_header(meta)
        blocks = classify_sections(cleaned)

        # Minimum content token guard: skip blocks whose raw content is too
        # small to be useful, BEFORE formatting (avoids repeated-header issues).
        MIN_CONTENT_TOKENS = 50

        chunk_list: list[tuple[str, str]] = []  # (content, section)
        for block in blocks:
            btype = block["type"]
            title = block.get("title", "")
            content = block.get("content", "").strip()
            if not content:
                continue
            if btype == "boilerplate":
                continue
            if count_tokens(content) < MIN_CONTENT_TOKENS:
                continue
            section_label = _section_label(title)

            for c in chunk_section(content, header, section_title=title):
                chunk_list.append((c, section_label))

        if not chunk_list:
            # Fallback: no sections detected, use unified chunk_section
            legacy_chunks = chunk_section(cleaned, header)
            chunk_list = [(c, "") for c in legacy_chunks]

        cur.execute(
            """INSERT INTO documents (filename, company, ticker, filing_type, filing_date, quarter, cik)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id""",
            (filename, meta.get("company"), meta.get("ticker"), meta.get("filing_type"),
             meta.get("filing_date"), meta.get("quarter"), meta.get("cik")),
        )
        doc_id = cur.fetchone()["id"]

        contents = [c[0] for c in chunk_list]
        embeddings = embed_texts(contents)

        for idx, ((content, section), emb) in enumerate(zip(chunk_list, embeddings)):
            token_count = count_tokens(content)
            cur.execute(
                """INSERT INTO chunks (document_id, chunk_index, content, embedding, section, token_count)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (doc_id, idx, content, str(emb), section or None, token_count),
            )

        conn.commit()
        print(f"  [{i+1}/{len(files)}] {filename} - {len(chunk_list)} chunks")

    cur.close()
    conn.close()
    print("Ingestion complete")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest SEC filings into the database.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite the database (drop tables) instead of resuming.")
    args = parser.parse_args()
    
    ingest(overwrite=args.overwrite)
