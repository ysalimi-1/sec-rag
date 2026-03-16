from backend.retrieval.query_decomposer import decompose_and_expand, extract_filters

q = "What regulatory risks do the major pharmaceutical companies face, and how are they addressing them?"
print("Decompose:", decompose_and_expand(q))
print("Filters:", extract_filters(q))
