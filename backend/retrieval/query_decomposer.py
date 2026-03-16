import json
from openai import OpenAI
from backend.config import OPENAI_API_KEY, DECOMPOSE_MODEL
from backend.chat.prompts import DECOMPOSE_SYSTEM, FILTER_SYSTEM

_client = OpenAI(api_key=OPENAI_API_KEY)



def decompose_and_expand(query: str) -> list[str]:
    resp = _client.chat.completions.create(
        model=DECOMPOSE_MODEL,
        messages=[
            {"role": "system", "content": DECOMPOSE_SYSTEM},
            {"role": "user", "content": query},
        ],
        max_completion_tokens=1000,
    )
    text = resp.choices[0].message.content.strip()

    try:
        queries = json.loads(text)
        if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
            return queries[:4]
    except json.JSONDecodeError:
        pass

    return [query]


def extract_filters(query: str) -> dict:
    """Return a dictionary of tickers and filing_types the query focuses on."""
    resp = _client.chat.completions.create(
        model=DECOMPOSE_MODEL,
        messages=[
            {"role": "system", "content": FILTER_SYSTEM},
            {"role": "user", "content": query},
        ],
        max_completion_tokens=800,
    )
    text = resp.choices[0].message.content.strip()

    result = {"tickers": [], "filing_types": []}
    try:
        data = json.loads(text)
        
        tickers = data.get("tickers", [])
        if isinstance(tickers, list) and all(isinstance(t, str) for t in tickers):
            result["tickers"] = [t.upper() for t in tickers]
            
        filing_types = data.get("filing_types", [])
        if isinstance(filing_types, list) and all(isinstance(f, str) for f in filing_types):
            result["filing_types"] = [f.upper() for f in filing_types]
            
    except (json.JSONDecodeError, AttributeError):
        pass

    return result
