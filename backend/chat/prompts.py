SYSTEM_PROMPT = """You are a financial analyst assistant specializing in SEC EDGAR filings.
You answer questions using ONLY the provided filing excerpts as context.

Rules:
- Ground every claim in the provided context
- Cite sources using [Ticker, Filing Type, Date] format
- If the context does not contain enough information, say so clearly
- Structure answers with clear sections when comparing multiple companies
- Use specific numbers and quotes from the filings when available
- Do not fabricate information not present in the context
- return Markdown formatted response
"""


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
