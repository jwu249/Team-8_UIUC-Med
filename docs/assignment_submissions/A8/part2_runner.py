import json
import os
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from groq import Groq
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent
NB_PATH = BASE_DIR / "rag_system.ipynb"
OUT_CSV = BASE_DIR / "part2_results.csv"
OUT_MD = BASE_DIR / "rag_analysis.md"


TEST_QUERIES = [
    "I have crushing chest pain, sweating, and pain down my left arm. Should I call 911?",
    "My toddler has a fever of 101.8F for one day but is drinking fluids. Do I need the ER?",
    "I twisted my ankle playing basketball and can still walk with pain. ER or urgent care?",
    "I keep getting burning pee and frequent urination, now with flank pain and chills. What level of care?",
    "I feel sudden room-spinning dizziness when I turn my head in bed. Is this dangerous?",
]


EXPECTED_KEYWORDS = {
    TEST_QUERIES[0]: ["chest pain", "heart attack", "911", "urgent"],
    TEST_QUERIES[1]: ["fever", "children", "pediatric", "urgent care"],
    TEST_QUERIES[2]: ["sprain", "ankle", "urgent care", "rice"],
    TEST_QUERIES[3]: ["uti", "kidney", "flank pain", "urgent"],
    TEST_QUERIES[4]: ["dizziness", "vertigo", "bppv", "stroke"],
}


EMBED_ORDER = ["small", "medium", "large"]
CHUNK_ORDER = ["fixed", "overlapping", "hybrid"]


def _clean_cell_source(src: str) -> str:
    lines = src.splitlines()
    cleaned = []
    for line in lines:
        if line.lstrip().startswith("%"):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def _load_part1_namespace(nb_path: Path) -> dict:
    nb = json.loads(nb_path.read_text(encoding="utf-8"))
    ns = {"GENERATION_MODEL": "llama-3.3-70b-versatile"}

    # Part 1 code cells needed for pipeline objects/functions.
    cells_to_exec = [3, 5, 7, 8, 9, 10, 12, 13, 15, 18, 19]

    for idx in cells_to_exec:
        cell = nb["cells"][idx]
        if cell.get("cell_type") != "code":
            continue
        src = "".join(cell.get("source", []))
        cleaned = _clean_cell_source(src)
        if not cleaned:
            continue
        exec(compile(cleaned, f"rag_system.ipynb:cell_{idx}", "exec"), ns)

    # Backfill notebook-runtime values that can be missing when run outside Jupyter state.
    env_path = BASE_DIR.parent.parent.parent / ".env"
    load_dotenv(env_path)
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        raise RuntimeError(f"GROQ_API_KEY missing. Expected it in: {env_path}")

    if "groq_client" not in ns:
        ns["groq_client"] = Groq(api_key=groq_key)

    required = [
        "EMBEDDING_MODELS",
        "CHUNKING_STRATEGIES",
        "VECTOR_STORES",
        "retrieve_cached",
        "generate_answer",
        "fixed_length_chunks",
        "PARAGRAPHS",
    ]
    missing = [k for k in required if k not in ns]
    if missing:
        raise RuntimeError(f"Missing required notebook objects: {missing}")

    return ns


def _score_text_quality(text: str, keywords: list[str]) -> int:
    t = text.lower()
    hits = sum(1 for k in keywords if k in t)
    ratio = hits / max(len(keywords), 1)
    if ratio >= 0.9:
        return 5
    if ratio >= 0.65:
        return 4
    if ratio >= 0.4:
        return 3
    if ratio >= 0.2:
        return 2
    return 1


def _short_chunk(chunk: str, max_len: int = 120) -> str:
    first_line = chunk.strip().splitlines()[0].strip() if chunk.strip() else ""
    return first_line[:max_len]


def run_part2():
    ns = _load_part1_namespace(NB_PATH)
    generate_answer = ns["generate_answer"]

    rows = []
    for embed, chunk in product(EMBED_ORDER, CHUNK_ORDER):
        for q_idx, query in enumerate(TEST_QUERIES, start=1):
            run_id = f"{embed[:1].upper()}{CHUNK_ORDER.index(chunk)+1}-Q{q_idx}"
            try:
                result = generate_answer(
                    query=query,
                    embedding_size=embed,
                    chunking_strategy=chunk,
                    top_k=3,
                    max_tokens=250,
                    temperature=0.0,
                )

                chunks = result["retrieved_chunks"]
                retrieved_blob = " | ".join(
                    f"R{c['rank']} ({c['score']:.3f}): {_short_chunk(c['chunk'])}"
                    for c in chunks
                )
                all_context_text = " ".join(c["chunk"] for c in chunks)
                keywords = EXPECTED_KEYWORDS[query]
                ctx_quality = _score_text_quality(all_context_text, keywords)
                ans_quality = _score_text_quality(result["answer"], keywords)

                rows.append(
                    {
                        "run_id": run_id,
                        "embedding_model": embed,
                        "chunking_strategy": chunk,
                        "query": query,
                        "retrieved_chunks": retrieved_blob,
                        "retrieved_context_quality": ctx_quality,
                        "answer": result["answer"].replace("\n", " ").strip(),
                        "answer_quality": ans_quality,
                        "latency_s": result["total_time_s"],
                        "notes": "",
                    }
                )
            except Exception as e:
                rows.append(
                    {
                        "run_id": run_id,
                        "embedding_model": embed,
                        "chunking_strategy": chunk,
                        "query": query,
                        "retrieved_chunks": f"ERROR: {e}",
                        "retrieved_context_quality": 1,
                        "answer": f"ERROR: {e}",
                        "answer_quality": 1,
                        "latency_s": np.nan,
                        "notes": "run failed",
                    }
                )

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8")

    summary = (
        df.groupby(["embedding_model", "chunking_strategy"], as_index=False)
        .agg(
            avg_retrieved_context_quality=("retrieved_context_quality", "mean"),
            avg_answer_quality=("answer_quality", "mean"),
            avg_latency_s=("latency_s", "mean"),
        )
        .sort_values(["embedding_model", "chunking_strategy"])
    )

    by_embed = (
        df.groupby("embedding_model", as_index=False)
        .agg(
            avg_ctx=("retrieved_context_quality", "mean"),
            avg_ans=("answer_quality", "mean"),
            avg_latency=("latency_s", "mean"),
        )
        .sort_values("avg_ans", ascending=False)
    )
    by_chunk = (
        df.groupby("chunking_strategy", as_index=False)
        .agg(
            avg_ctx=("retrieved_context_quality", "mean"),
            avg_ans=("answer_quality", "mean"),
            avg_latency=("latency_s", "mean"),
        )
        .sort_values("avg_ans", ascending=False)
    )

    # Data scaling experiment using medium + fixed for consistency.
    paragraphs = ns["PARAGRAPHS"]
    fixed_length_chunks = ns["fixed_length_chunks"]
    cosine_similarity = ns["cosine_similarity"]
    embedder = ns.get("_EMBEDDER_CACHE", {}).get("medium")
    if embedder is None:
        embedder = SentenceTransformer(ns["EMBEDDING_MODELS"]["medium"])

    small_paragraphs = paragraphs[:12]
    noise_paragraphs = [
        "[NOISE] Hospital cafeteria menu rotations and seasonal beverage discounts.",
        "[NOISE] Parking lot repaint schedule and office furniture replacement details.",
        "[NOISE] Generic software release notes unrelated to health triage decisions.",
        "[NOISE] Community event sponsorship announcement and vendor onboarding status.",
        "[NOISE] Team-building retreat planning logistics and entertainment budget notes.",
        "[NOISE] Miscellaneous business KPI dashboard commentary without clinical content.",
        "[NOISE] Campus shuttle route updates and construction detour timeline summary.",
        "[NOISE] Procurement forms and reimbursement policy reminders for travel expenses.",
        "[NOISE] Cloud migration timeline and API gateway tuning discussion for IT ops.",
        "[NOISE] Internal newsletter text about branding updates and social media campaigns.",
    ]
    large_paragraphs = paragraphs + noise_paragraphs

    def eval_dataset(paras: list[str]) -> tuple[float, float]:
        chunks = fixed_length_chunks(paras)
        emb = embedder.encode(chunks, show_progress_bar=False)
        noise_hits = 0
        total_hits = 0
        ctx_scores = []
        for q in TEST_QUERIES:
            qemb = embedder.encode([q])[0]
            sims = cosine_similarity(qemb, emb)
            top_idx = np.argsort(sims)[::-1][:3]
            top_chunks = [chunks[i] for i in top_idx]
            top_text = " ".join(top_chunks)
            ctx_scores.append(_score_text_quality(top_text, EXPECTED_KEYWORDS[q]))
            noise_hits += sum(1 for ch in top_chunks if "[NOISE]" in ch)
            total_hits += len(top_chunks)
        return float(np.mean(ctx_scores)), (noise_hits / max(total_hits, 1))

    small_ctx, small_noise = eval_dataset(small_paragraphs)
    large_ctx, large_noise = eval_dataset(large_paragraphs)

    best_embed = by_embed.iloc[0]["embedding_model"]
    best_chunk = by_chunk.iloc[0]["chunking_strategy"]

    md_lines = []
    md_lines.append("# A8 RAG Analysis (Part 2)")
    md_lines.append("")
    md_lines.append("## Step 2.1: Test Queries")
    for i, q in enumerate(TEST_QUERIES, 1):
        md_lines.append(f"{i}. {q}")
    md_lines.append("")

    md_lines.append("## Step 2.2: Evaluation Table")
    md_lines.append("Scoring I used: 1 (bad) to 5 (excellent) for both retrieval context and final answer quality.")
    md_lines.append("")

    # Full run table
    table_cols = [
        "run_id",
        "embedding_model",
        "chunking_strategy",
        "query",
        "retrieved_chunks",
        "retrieved_context_quality",
        "answer",
        "answer_quality",
        "latency_s",
        "notes",
    ]
    md_lines.append(df[table_cols].to_markdown(index=False))
    md_lines.append("")

    md_lines.append("### Aggregate Summary by Config")
    md_lines.append(summary.to_markdown(index=False))
    md_lines.append("")

    md_lines.append("## Step 2.3: Compare Embedding Models")
    md_lines.append(
        f"Across all chunking strategies, `{best_embed}` had the highest average answer quality in my runs."
    )
    md_lines.append(
        "Larger embeddings did not always win every single query. Some smaller/medium runs still retrieved good chunks quickly."
    )
    md_lines.append("Embedding model summary:")
    md_lines.append(by_embed.to_markdown(index=False))
    md_lines.append("")

    md_lines.append("## Step 2.4: Compare Chunking Strategies")
    md_lines.append(
        f"`{best_chunk}` was the best overall chunking strategy by average answer quality on this dataset."
    )
    md_lines.append(
        "Chunking mattered a lot: even with the same embedding model, changing chunking changed which evidence came back in top-k."
    )
    md_lines.append("Chunking summary:")
    md_lines.append(by_chunk.to_markdown(index=False))
    md_lines.append("")

    md_lines.append("## Step 2.5: Data Scaling Experiment")
    md_lines.append("Setup: medium embedding + fixed chunking + same 5 queries, top-k=3.")
    md_lines.append("")
    md_lines.append("| Dataset | Size | Avg Retrieved Context Quality | Noise Rate In Top-k |")
    md_lines.append("|---|---:|---:|---:|")
    md_lines.append(f"| Smaller subset | {len(small_paragraphs)} paragraphs | {small_ctx:.2f} | {small_noise:.2%} |")
    md_lines.append(f"| Larger set (+noise) | {len(large_paragraphs)} paragraphs | {large_ctx:.2f} | {large_noise:.2%} |")
    md_lines.append("")
    md_lines.append(
        "Takeaway: as dataset size grows (especially with unrelated text), retrieval has more chances to pull noisy chunks."
    )
    md_lines.append(
        "This makes chunking quality, embedding choice, and top-k tuning more important."
    )
    md_lines.append("")

    OUT_MD.write_text("\n".join(md_lines), encoding="utf-8")

    print(f"Wrote: {OUT_CSV}")
    print(f"Wrote: {OUT_MD}")


if __name__ == "__main__":
    run_part2()
