def build_user_prompt(question: str, chunks: list[dict]) -> str:
    context_parts = []
    for i, chunk in enumerate(chunks):
        source = f"[{chunk.get('ticker', '?')}, {chunk.get('filing_type', '?')}, {chunk.get('filing_date', '?')}]"
        context_parts.append(f"--- Source {i+1} {source} ---\n{chunk['content']}")

    context = "\n\n".join(context_parts)

    return f"""Context from SEC EDGAR filings:

{context}

Question: {question}

Provide a well-structured answer grounded in the above filing data. Cite sources."""
