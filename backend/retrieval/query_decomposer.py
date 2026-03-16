import json
from openai import OpenAI
from backend.config import OPENAI_API_KEY, DECOMPOSE_MODEL

_client = OpenAI(api_key=OPENAI_API_KEY)

DECOMPOSE_SYSTEM = """You are a query preprocessor for a SEC EDGAR filing search system.
Given a user question, decompose it into retrieval-optimized search queries.

the SEC Database has the following companies:
{AAPL,ABBV,ADBE,AMD,AMZN,AXP,BA,BAC,BLK,BRK,CAT,CMCSA,COST,CRM,CSCO,CVX,DE,DIS,GE,GOOG,GS,HD,IBM,INTC,JNJ,JPM,KO,LLY,LMT,MA,MCD,META,MRK,MS,MSFT,NFLX,NKE,NVDA,ORCL,PEP,PFE,PG,RTX,SBUX,T,TGT,TMO,TSLA,UNH,UPS,V,VZ,WMT,XOM}

Rules:
- Output 1 to 4 search queries as a JSON array of strings
- Each query should target a specific entity or facet of the original question
- Expand each query with: ticker symbols, SEC filing terminology, relevant financial terms
- Do NOT answer the question, only produce search queries
- For company names, always include the stock ticker (e.g., Apple -> AAPL, Tesla -> TSLA)
- Use terms from SEC filings: "risk factors", "revenue", "net income", "forward-looking statements", etc.
- If the question asks about a specific sector or industry (e.g., "pharmaceutical companies", "tech companies", "banks"), identify the relevant companies from the provided list and explicitly include their tickers in the generated queries.
- If the query is already simple and specific, return it expanded with relevant terms

Examples:
Input: "What are the primary risk factors facing Apple, Tesla, and JPMorgan?"
Output: ["AAPL Apple Inc 10-K risk factors business risks competitive threats", "TSLA Tesla Inc 10-K risk factors regulatory operational supply chain", "JPM JPMorgan Chase 10-K risk factors credit market regulatory capital", "AAPL TSLA JPM comparative risk factors across sectors technology automotive banking"]

Input: "How has NVIDIA's revenue and growth outlook changed over the last two years?"
Output: ["NVDA NVIDIA revenue net income financial results fiscal year 2024 2025", "NVDA NVIDIA growth outlook forward-looking statements data center AI demand"]

Input: "What regulatory risks do the major pharmaceutical companies face?"
Output: ["PFE Pfizer regulatory risks FDA approval clinical trials litigation", "JNJ Johnson Johnson regulatory compliance legal proceedings product liability", "MRK Merck regulatory risks patent expiration drug pricing government", "LLY ABBV pharmaceutical regulatory government pricing reform healthcare policy"]

Respond only with the JSON array."""

FILTER_SYSTEM = """You are a financial entity extractor.
Given a user question, identify which specific company stock tickers (if any) and/or SEC filing types (e.g., 10-K, 10-Q, 8-K) the question targets.


Availaible tickers:
{AAPL,ABBV,ADBE,AMD,AMZN,AXP,BA,BAC,BLK,BRK,CAT,CMCSA,COST,CRM,CSCO,CVX,DE,DIS,GE,GOOG,GS,HD,IBM,INTC,JNJ,JPM,KO,LLY,LMT,MA,MCD,META,MRK,MS,MSFT,NFLX,NKE,NVDA,ORCL,PEP,PFE,PG,RTX,SBUX,T,TGT,TMO,TSLA,UNH,UPS,V,VZ,WMT,XOM}
Rules:
- Return a JSON object with two keys: "tickers" and "filing_types", both containing a list of uppercase strings.
- Only include tickers when the question is clearly about one or more named companies. Resolve company names to tickers (e.g., "NVIDIA" -> "NVDA", "Apple" -> "AAPL").
- If the question asks about a specific sector or industry (e.g., "pharmaceutical companies", "tech companies"), identify the relevant companies from the available tickers and include them in the "tickers" list.
- Only include filing types if the user explicitly asks about them (e.g., "10-K", "10-Q", "Annual Report" -> "10-K", "Quarterly" -> "10-Q").
- If broad or unspecified, return empty lists: {"tickers": [], "filing_types": []}.

Examples:
Input: "How has NVIDIA's revenue changed in its latest 10-K?"
Output: {"tickers": ["NVDA"], "filing_types": ["10-K"]}

Input: "Compare Apple and Microsoft's quarterly cloud revenue in their 10-Qs"
Output: {"tickers": ["AAPL", "MSFT"], "filing_types": ["10-Q"]}

Input: "What regulatory risks do the major pharmaceutical companies face?"
Output: {"tickers": ["JNJ", "LLY", "MRK", "PFE", "ABBV"], "filing_types": []}

Input: "What are the S&P 500 companies' average margins?"
Output: {"tickers": [], "filing_types": []}

Respond only with the JSON object."""


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
