import asyncio
import time
import json
from pydantic import BaseModel, Field

from db import init_db
from retrieval import decompose_and_expand, retrieve_multi, retrieve
from chat import SYSTEM_PROMPT, build_user_prompt
from ai_clients.openai_client import OpenAIClient


# 1. Define Labeled Dataset
# We include expected tickers and key reference points the answer should hit.
DATASET = [
    {
        "question": "What are the primary risk factors facing Apple, Tesla, and JPMorgan, and how do they compare?",
        "expected_tickers": ["AAPL", "TSLA", "JPM"],
    },
    {
        "question": "How has NVIDIA's revenue and growth outlook changed over the last two years?",
        "expected_tickers": ["NVDA"],
    },
    {
        "question": "What regulatory risks do the major pharmaceutical companies (Pfizer, Johnson & Johnson) face, and how are they addressing them?",
        "expected_tickers": ["PFE", "JNJ"],
    },
    {
        "question": "How is Amazon utilizing artificial intelligence in its AWS and e-commerce segments?",
        "expected_tickers": ["AMZN"],
    },
    {
        "question": "Compare the recent financial performance of Microsoft and Google in cloud computing.",
        "expected_tickers": ["MSFT", "GOOG"],
    },
    {
        "question": "What strategies are Disney and Netflix employing to increase streaming profitability?",
        "expected_tickers": ["DIS", "NFLX"],
    },
    {
        "question": "What macro-economic headwinds is Bank of America highlighting in their recent 10-Q filings?",
        "expected_tickers": ["BAC"],
    },
    {
        "question": "How did Tesla's automotive margins change from 2023 to 2024?",
        "expected_tickers": ["TSLA"],
    },
    {
        "question": "What legal proceedings or contingencies are currently affecting Johnson & Johnson?",
        "expected_tickers": ["JNJ"],
    },
    {
        "question": "Describe ExxonMobil's capital expenditure plans for renewable energy or low carbon solutions.",
        "expected_tickers": ["XOM"],
    }
]

# 2. Define LLM Judge Output Schema
class EvaluationMetrics(BaseModel):
    context_relevance: int = Field(
        description="Score 1-5: How relevant and helpful the retrieved context is for answering the question."
    )
    groundedness: int = Field(
        description="Score 1-5: Does the answer rely purely on the provided context? 1 = complete hallucination, 5 = fully grounded in context."
    )
    completeness: int = Field(
        description="Score 1-5: How completely does the generated answer address the user's original question? 1 = misses point, 5 = comprehensive."
    )
    reasoning: str = Field(
        description="Brief justification for the scores given."
    )


async def evaluate_with_llm_judge(llm: OpenAIClient, question: str, context: str, answer: str) -> EvaluationMetrics:
    """Uses LLM-as-a-judge to evaluate generation quality."""
    
    judge_prompt = f"""You are an expert evaluator grading a Retrieval-Augmented Generation (RAG) system.
Please evaluate the provided context and the final answer based on the original user question.

USER QUESTION:
{question}

RETRIEVED CONTEXT:
{context}

GENERATED ANSWER:
{answer}

Evaluate on a scale of 1-5 for:
1. context_relevance (1: Not relevant, 5: Highly relevant and sufficient)
2. groundedness (1: Answer contains severe hallucinations not in context, 5: Answer is explicitly supported by context)
3. completeness (1: Answer fails to address the question, 5: Answer completely addresses the question)

You must output valid JSON matching the exact schema provided.
"""
    
    messages = [
        {"role": "system", "content": "You are an objective AI evaluator."},
        {"role": "user", "content": judge_prompt}
    ]
    
    schema = EvaluationMetrics.model_json_schema()
    schema["additionalProperties"] = False
    
    # Force structured output using pydantic model schema
    response_json = await llm.generate(
        messages=messages,
        response_format={"type": "json_schema", "json_schema": {"name": "EvaluationMetrics", "schema": schema, "strict": True}}
    )
    
    data = json.loads(response_json)
    return EvaluationMetrics(**data)


async def run_baseline_pipeline(llm: OpenAIClient, question: str):
    """Pipeline A: Raw Query -> Retrieval -> Answer"""
    # 1. Retrieve using exact query directly (No decomposition)
    chunks = retrieve_multi([question], top_k_per_query=15, final_top_k=15, tickers=None)
    
    # 2. Generate
    user_prompt = build_user_prompt(question, chunks)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    answer = await llm.generate(messages)
    
    return chunks, answer


async def run_advanced_pipeline(llm: OpenAIClient, question: str):
    """Pipeline B: Decompose -> Multi-Retrieval -> Answer"""
    search_plan = decompose_and_expand(question)
    sub_queries = search_plan.queries
    tickers = search_plan.tickers
    
    chunks = retrieve_multi(
        sub_queries, 
        tickers=tickers if tickers else None
    )
    
    user_prompt = build_user_prompt(question, chunks)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]
    answer = await llm.generate(messages)
    
    return search_plan, chunks, answer


async def evaluate_pipeline():
    print("Initializing Database...")
    init_db()

    llm = OpenAIClient(model="gpt-4o") # Use explicit structured model

    print(f"Starting advanced evaluation of {len(DATASET)} questions...\n" + "="*80)

    # Accumulate metrics
    metrics = {
        "baseline": {"context_relevance": [], "groundedness": [], "completeness": []},
        "advanced": {"context_relevance": [], "groundedness": [], "completeness": []}
    }

    for i, item in enumerate(DATASET, 1):
        q = item["question"]
        print(f"\n[Question {i}/{len(DATASET)}] {q}")
        
        # --- RUN BASELINE ---
        print("  -> Running Baseline (No Decomposition)...")
        b_chunks, b_answer = await run_baseline_pipeline(llm, q)
        b_context_str = "\n".join([c["content"] for c in b_chunks])
        b_eval = await evaluate_with_llm_judge(llm, q, b_context_str, b_answer)
        
        metrics["baseline"]["context_relevance"].append(b_eval.context_relevance)
        metrics["baseline"]["groundedness"].append(b_eval.groundedness)
        metrics["baseline"]["completeness"].append(b_eval.completeness)
        
        print(f"     Metrics: Relevance={b_eval.context_relevance}, Groundedness={b_eval.groundedness}, Completeness={b_eval.completeness}")
        
        # --- RUN ADVANCED ---
        print("  -> Running Advanced (With Decomposition)...")
        a_plan, a_chunks, a_answer = await run_advanced_pipeline(llm, q)
        a_context_str = "\n".join([c["content"] for c in a_chunks])
        a_eval = await evaluate_with_llm_judge(llm, q, a_context_str, a_answer)
        
        metrics["advanced"]["context_relevance"].append(a_eval.context_relevance)
        metrics["advanced"]["groundedness"].append(a_eval.groundedness)
        metrics["advanced"]["completeness"].append(a_eval.completeness)
        
        print(f"     Decomposed Tickers: {a_plan.tickers}")
        print(f"     Metrics: Relevance={a_eval.context_relevance}, Groundedness={a_eval.groundedness}, Completeness={a_eval.completeness}")

        print("-" * 80)

    # --- AGGREGATE RESULTS ---
    print("\n" + "="*80)
    print("EVALUATION RESULTS ROUNDUP")
    print("="*80)
    
    def avg(lst): return sum(lst) / len(lst) if lst else 0.0
    
    print("\nBASELINE (No Decomposition):")
    print(f"  Avg Context Relevance: {avg(metrics['baseline']['context_relevance']):.2f} / 5.0")
    print(f"  Avg Groundedness:      {avg(metrics['baseline']['groundedness']):.2f} / 5.0")
    print(f"  Avg Completeness:      {avg(metrics['baseline']['completeness']):.2f} / 5.0")

    print("\nADVANCED (With Decomposition):")
    print(f"  Avg Context Relevance: {avg(metrics['advanced']['context_relevance']):.2f} / 5.0")
    print(f"  Avg Groundedness:      {avg(metrics['advanced']['groundedness']):.2f} / 5.0")
    print(f"  Avg Completeness:      {avg(metrics['advanced']['completeness']):.2f} / 5.0")
    print("\nEvaluation Complete.")


if __name__ == "__main__":
    asyncio.run(evaluate_pipeline())
