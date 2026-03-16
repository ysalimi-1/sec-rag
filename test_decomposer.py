from backend.retrieval.query_decomposer import decompose_and_expand

questions = [
    "What are the primary risk factors facing Apple, Tesla, and JPMorgan, and how do they compare?",
    "How has NVIDIA's revenue and growth outlook changed over the last two years?",
    "What regulatory risks do the major pharmaceutical companies face, and how are they addressing them?"
]

for q in questions:
    print(f"--- Question: {q}")
    plan = decompose_and_expand(q)
    print("Queries:", plan.queries)
    print("Tickers:", plan.tickers)
    print()
