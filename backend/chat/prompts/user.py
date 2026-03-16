from datetime import date


def build_user_prompt(question: str, chunks: list[dict]) -> str:
    today = date.today().strftime("%B %d, %Y")
    context_parts = []
    for i, chunk in enumerate(chunks):
        source = f"[{chunk.get('ticker', '?')}, {chunk.get('filing_type', '?')}, {chunk.get('filing_date', '?')}]"
        context_parts.append(f"--- Source {i+1} {source} ---\n{chunk['content']}")

    context = "\n\n".join(context_parts)

    return f"""Today's date is {today}.

Context from SEC EDGAR filings:

{context}

Question: {question}

Provide a comprehensive, well-structured answer grounded in the above filing data. Ensure you address every part of the question. If multiple entities or time periods are mentioned, give each balanced coverage. Cite your sources using the [Ticker, Filing Type, Date] format."""

