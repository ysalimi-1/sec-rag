import asyncio
from backend.db import get_pool
from backend.retrieval.embeddings import embed_texts


async def retrieve(
    query: str,
    top_k: int = 12,
    ticker: str | None = None,
    section: str | None = None,
    query_embedding: list[float] | None = None,
) -> list[dict]:
    if query_embedding is None:
        query_embedding = (await asyncio.to_thread(embed_texts, [query]))[0]

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Build WHERE and params for both queries (ticker, section)
            conditions = []
            extra_params: list = []
            if ticker:
                conditions.append("d.ticker = %s")
                extra_params.append(ticker)
            if section:
                conditions.append("c.section = %s")
                extra_params.append(section)
            
            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
            
            # Vector similarity search
            vec_params = [str(query_embedding)] + extra_params + [str(query_embedding), top_k]
            await cur.execute(
                f"""SELECT c.id, c.content, c.chunk_index, c.document_id,
                           c.section, c.token_count,
                           d.ticker, d.company, d.filing_type, d.filing_date, d.quarter,
                           1 - (c.embedding <=> %s::vector) AS score
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    {where_clause}
                    ORDER BY c.embedding <=> %s::vector
                    LIMIT %s""",
                vec_params,
            )
            vector_results = await cur.fetchall()

            # Trigram keyword search - using distance operator <-> with GIST
            tri_where = where_clause
            if conditions:
                tri_where = where_clause + " AND c.content %% %s"
            else:
                tri_where = "WHERE c.content %% %s"
            
            tri_params = [query] + extra_params + [query, query, top_k]
            await cur.execute(
                f"""SELECT c.id, c.content, c.chunk_index, c.document_id,
                           c.section, c.token_count,
                           d.ticker, d.company, d.filing_type, d.filing_date, d.quarter,
                           similarity(c.content, %s) AS score
                    FROM chunks c
                    JOIN documents d ON c.document_id = d.id
                    {tri_where}
                    ORDER BY c.content <-> %s
                    LIMIT %s""",
                tri_params,
            )
            keyword_results = await cur.fetchall()

    return _rrf_merge(vector_results, keyword_results, top_k)


def _rrf_merge(vector_results: list, keyword_results: list, top_k: int, k: int = 60) -> list[dict]:
    scores: dict[int, float] = {}
    chunks: dict[int, dict] = {}

    for rank, row in enumerate(vector_results):
        cid = row["id"]
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
        chunks[cid] = row

    for rank, row in enumerate(keyword_results):
        cid = row["id"]
        scores[cid] = scores.get(cid, 0) + 1.0 / (k + rank + 1)
        chunks[cid] = row

    # Correcting the sorting and indexing for Pydantic/type safety
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return [chunks[cid] for cid, _ in ranked]


async def retrieve_multi(
    queries: list[str],
    top_k_per_query: int = 8,
    final_top_k: int = 20,
    tickers: list[str] | None = None,
) -> list[dict]:
    """Retrieve and RRF-merge chunks across multiple queries in parallel."""
    # Determine the dimensions to iterate over
    ticker_filters: list[str | None] = list(tickers) if tickers else [None]

    # Batch embed all unique queries
    unique_queries = list(set(queries))
    query_to_embedding: dict[str, list[float]] = {}
    if unique_queries:
        embeddings = await asyncio.to_thread(embed_texts, unique_queries)
        query_to_embedding = dict(zip(unique_queries, embeddings))

    tasks = []
    for query in queries:
        embedding = query_to_embedding.get(query)
        for ticker_filter in ticker_filters:
            tasks.append(
                retrieve(
                    query, top_k=top_k_per_query, ticker=ticker_filter, query_embedding=embedding
                )
            )

    # Run all retrievals in parallel
    results_list = await asyncio.gather(*tasks)
    
    # Merge results and deduplicate
    all_results: list[dict] = []
    seen_ids: set = set()
    
    for results in results_list:
        for r in results:
            if r["id"] not in seen_ids:
                seen_ids.add(r["id"])
                all_results.append(r)

    return all_results[:final_top_k]
