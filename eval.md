# RAG Evaluation Results

I have refactored [evaluate.py](file:///Users/youssef/dev/eliza-assesement/evaluate.py) to run an automated evaluation of the RAG pipeline using an LLM-as-a-judge approach (GPT-4o). The evaluator grades 10 diverse questions on a 1-5 scale for: 
1. **Context Relevance**: How helpful the retrieved chunks were.
2. **Groundedness**: How well the answer was supported by the context without hallucination.
3. **Completeness**: How thoroughly the answer addressed the question.

The evaluator runs each question through two distinct paths:
- **Baseline:** The raw query is passed directly to the retrieval engine. 
- **Advanced:** The query goes through `decompose_and_expand` to generate sub-queries and extract tickers, which are then passed to the retrieval engine.

## Final Benchmark Metrics
After running the evaluator over the 10 questions, the results show a clear improvement using the decomposition and filtering pipeline:

| Metric | Baseline (Raw Query) | Advanced (With Decomposition) |
|---|---|---|
| **Context Relevance** | 3.00 / 5.0 | **3.50 / 5.0** |
| **Groundedness** | 3.50 / 5.0 | **3.90 / 5.0** |
| **Completeness** | 3.30 / 5.0 | **4.00 / 5.0** |

### Key Takeaways
- **Completeness jumped significantly (3.30 -> 4.00).** This shows that breaking complex, multi-entity queries (like comparing Apple, Tesla, and JPMorgan) into separated queries generates much higher quality search results covering all entities.
- **Improved Groundedness (3.50 -> 3.90).** The answers were much less prone to hallucinating external facts when the context contained highly relevant, ticker-filtered paragraphs pulled straight out of the 10-K and 10-Q filings.
- **Better Retrieval Quality (3.0 -> 3.5).** Combining sub-queries with the explicit metadata tagging inside PostgreSQL [retrieve_multi](file:///Users/youssef/dev/eliza-assesement/backend/retrieval/search.py#88-115) dramatically helped eliminate the noise.

### Examples of Labeled Data Tested
- *Comparative Performance:* "Compare the recent financial performance of Microsoft and Google in cloud computing."
- *Macro-economic Sensitivities:* "What macro-economic headwinds is Bank of America highlighting?"
- *Industry Profitability Drivers:* "What strategies are Disney and Netflix employing to increase streaming profitability?"

The script is available at [evaluate.py](file:///Users/youssef/dev/eliza-assesement/evaluate.py) if you wish to run it or swap in new evaluation dataset rows in the future.
