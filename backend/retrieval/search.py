from backend.db import get_conn
from backend.retrieval.embeddings import embed_texts


def retrieve(
    query: str,
    top_k: int = 12,
    ticker: str | None = None,
    filing_type: str | None = None,
    section: str | None = None,
) -> list[dict]:
    query_embedding = embed_texts([query])[0]

    conn = get_conn()
    cur = conn.cursor()

    # Build WHERE and params for both queries (ticker, section)
    conditions = []
    extra_params: list = []
    if ticker:
        conditions.append("d.ticker = %s")
        extra_params.append(ticker)
    if filing_type:
        conditions.append("d.filing_type = %s")
        extra_params.append(filing_type)
    if section:
        conditions.append("c.section = %s")
        extra_params.append(section)
    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    vec_params = [str(query_embedding)] + extra_params + [str(query_embedding), top_k]
    tri_params = [query] + extra_params + [query, query, top_k]

    sel = """c.id, c.content, c.chunk_index, c.document_id,
             c.section, c.token_count,
             d.ticker, d.company, d.filing_type, d.filing_date, d.quarter"""

    # Vector similarity search
    cur.execute(
        f"""SELECT {sel},
                   1 - (c.embedding <=> %s::vector) AS score
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            {where_clause}
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s""",
        vec_params,
    )
    vector_results = cur.fetchall()

    # Trigram keyword search
    tri_where = where_clause
    if conditions:
        tri_where = where_clause + " AND similarity(c.content, %s) > 0.05"
    else:
        tri_where = "WHERE similarity(c.content, %s) > 0.05"
    cur.execute(
        f"""SELECT {sel},
                      similarity(c.content, %s) AS score
               FROM chunks c
               JOIN documents d ON c.document_id = d.id
               {tri_where}
               ORDER BY similarity(c.content, %s) DESC
               LIMIT %s""",
        tri_params,
    )
    keyword_results = cur.fetchall()

    cur.close()
    conn.close()

    return _rrf_merge(vector_results, keyword_results, top_k)


def _rrf_merge(vector_results: list, keyword_results: list, top_k: int, k: int = 60) -> list[dict]:
    scores = {}
    chunks = {}

    for rank, row in enumerate(vector_results):
        cid = row["id"]
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
        chunks[cid] = row

    for rank, row in enumerate(keyword_results):
        cid = row["id"]
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
        chunks[cid] = row

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [chunks[cid] for cid, _ in ranked]


def retrieve_multi(
    queries: list[str],
    top_k_per_query: int = 8,
    final_top_k: int = 15,
    tickers: list[str] | None = None,
    filing_types: list[str] | None = None,
) -> list[dict]:
    """Retrieve and RRF-merge chunks across multiple queries.

    If ``tickers`` or ``filing_types`` is provided, only chunks matching those
    conditions will be returned. Each query is run for each ticker/filing_type
    combination so the DB-level filter is applied appropriately.
    """
    all_results: list[dict] = []
    seen_ids: set = set()

    # Determine the dimensions to iterate over
    ticker_filters: list[str | None] = list(tickers) if tickers else [None]
    filing_filters: list[str | None] = list(filing_types) if filing_types else [None]

    for query in queries:
        for ticker_filter in ticker_filters:
            for filing_filter in filing_filters:
                results = retrieve(query, top_k=top_k_per_query, ticker=ticker_filter, filing_type=filing_filter)
                for r in results:
                    if r["id"] not in seen_ids:
                        seen_ids.add(r["id"])
                        all_results.append(r)

    return all_results[:final_top_k]
