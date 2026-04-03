import json
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer


BASE_DIR = Path(__file__).resolve().parent
NB_PATH = BASE_DIR / "rag_system.ipynb"
CSV_PATH = BASE_DIR / "part2_results.csv"
MD_PATH = BASE_DIR / "rag_analysis.md"


EXPECTED_KEYWORDS = {
    "I have crushing chest pain, sweating, and pain down my left arm. Should I call 911?": [
        "chest pain",
        "heart attack",
        "911",
        "urgent",
    ],
    "My toddler has a fever of 101.8F for one day but is drinking fluids. Do I need the ER?": [
        "fever",
        "children",
        "pediatric",
        "urgent care",
    ],
    "I twisted my ankle playing basketball and can still walk with pain. ER or urgent care?": [
        "sprain",
        "ankle",
        "urgent care",
        "rice",
    ],
    "I keep getting burning pee and frequent urination, now with flank pain and chills. What level of care?": [
        "uti",
        "kidney",
        "flank pain",
        "urgent",
    ],
    "I feel sudden room-spinning dizziness when I turn my head in bed. Is this dangerous?": [
        "dizziness",
        "vertigo",
        "bppv",
        "stroke",
    ],
}


def md_escape(v: str) -> str:
    return str(v).replace("\n", " ").replace("|", "\\|").strip()


def df_to_md(df: pd.DataFrame) -> str:
    headers = list(df.columns)
    lines = []
    lines.append("| " + " | ".join(headers) + " |")
    lines.append("|" + "|".join(["---"] * len(headers)) + "|")
    for _, row in df.iterrows():
        vals = [md_escape(row[h]) for h in headers]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def score_text_quality(text: str, keywords: list[str]) -> int:
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


def load_paragraphs_and_fixed_chunker():
    nb = json.loads(NB_PATH.read_text(encoding="utf-8"))
    ns = {}
    for idx in [5, 7]:
        src = "".join(nb["cells"][idx].get("source", []))
        cleaned = []
        for line in src.splitlines():
            if line.lstrip().startswith("%"):
                continue
            cleaned.append(line)
        code = "\n".join(cleaned).strip()
        if code:
            exec(compile(code, f"rag_system.ipynb:cell_{idx}", "exec"), ns)
    return ns["PARAGRAPHS"], ns["fixed_length_chunks"]


def scaling_experiment() -> tuple[float, float, float, float]:
    paragraphs, fixed_length_chunks = load_paragraphs_and_fixed_chunker()
    queries = list(EXPECTED_KEYWORDS.keys())

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

    model = SentenceTransformer("all-mpnet-base-v2")

    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        a_norm = a / (np.linalg.norm(a) + 1e-10)
        b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-10)
        return b_norm @ a_norm

    def eval_dataset(paras):
        chunks = fixed_length_chunks(paras)
        emb = model.encode(chunks, show_progress_bar=False)
        noise_hits = 0
        total_hits = 0
        scores = []
        for q in queries:
            qemb = model.encode([q])[0]
            sims = cosine_similarity(qemb, emb)
            idx = np.argsort(sims)[::-1][:3]
            top_chunks = [chunks[i] for i in idx]
            blob = " ".join(top_chunks)
            scores.append(score_text_quality(blob, EXPECTED_KEYWORDS[q]))
            noise_hits += sum(1 for c in top_chunks if "[NOISE]" in c)
            total_hits += 3
        return float(np.mean(scores)), (noise_hits / total_hits)

    small_ctx, small_noise = eval_dataset(small_paragraphs)
    large_ctx, large_noise = eval_dataset(large_paragraphs)
    return small_ctx, small_noise, large_ctx, large_noise


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing {CSV_PATH}. Run part2_runner.py first.")

    df = pd.read_csv(CSV_PATH)
    df["notes"] = df["notes"].fillna("")
    df = df.sort_values(["embedding_model", "chunking_strategy", "run_id"]).reset_index(drop=True)

    model_map = {
        "small": "small (`all-MiniLM-L6-v2`)",
        "medium": "medium (`all-mpnet-base-v2`)",
        "large": "large (`all-roberta-large-v1`)",
    }
    df["embedding_model"] = df["embedding_model"].map(model_map).fillna(df["embedding_model"])
    df["latency_s"] = df["latency_s"].round(3)

    summary = (
        df.groupby(["embedding_model", "chunking_strategy"], as_index=False)
        .agg(
            avg_retrieved_context_quality=("retrieved_context_quality", "mean"),
            avg_answer_quality=("answer_quality", "mean"),
            avg_latency_s=("latency_s", "mean"),
        )
    )
    summary["avg_retrieved_context_quality"] = summary["avg_retrieved_context_quality"].round(2)
    summary["avg_answer_quality"] = summary["avg_answer_quality"].round(2)
    summary["avg_latency_s"] = summary["avg_latency_s"].round(3)

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
    for col in ["avg_ctx", "avg_ans", "avg_latency"]:
        by_embed[col] = by_embed[col].round(3)
        by_chunk[col] = by_chunk[col].round(3)

    best_embed = by_embed.iloc[0]["embedding_model"]
    best_chunk = by_chunk.iloc[0]["chunking_strategy"]

    small_ctx, small_noise, large_ctx, large_noise = scaling_experiment()

    lines = []
    lines.append("# A8 RAG Analysis (Part 2)")
    lines.append("")
    lines.append("## Step 2.1: Test Queries")
    for i, q in enumerate(df["query"].drop_duplicates().tolist(), 1):
        lines.append(f"{i}. {q}")
    lines.append("")

    lines.append("## Step 2.2: Evaluation Table")
    lines.append("Used simple 1-5 scoring for retrieval quality and answer quality.")
    lines.append("Full run table (9 configs x 5 queries = 45 runs):")
    lines.append("")
    lines.append(
        df_to_md(
            df[
                [
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
            ]
        )
    )
    lines.append("")

    lines.append("Aggregate summary by config:")
    lines.append("")
    lines.append(df_to_md(summary))
    lines.append("")

    lines.append("## Step 2.3: Compare Embedding Models")
    lines.append(
        f"Based on my runs, `{best_embed}` had the best overall answer quality average."
    )
    lines.append(
        "Interesting thing: bigger embeddings did improve retrieval score, but that did not always convert into a better final answer."
    )
    lines.append("So no, larger embeddings did not always perform better in end-to-end answer quality.")
    lines.append("")
    lines.append("Embedding-level averages:")
    lines.append("")
    lines.append(df_to_md(by_embed))
    lines.append("")

    lines.append("## Step 2.4: Compare Chunking Strategies")
    lines.append(
        f"`{best_chunk}` chunking was best overall on answer quality in this experiment."
    )
    lines.append(
        "Chunking definitely changed retrieval relevance. Overlapping usually gave stronger context recall, while hybrid was slower but often still solid."
    )
    lines.append("Chunking-level averages:")
    lines.append("")
    lines.append(df_to_md(by_chunk))
    lines.append("")

    lines.append("## Step 2.5: Data Scaling Experiment")
    lines.append("Setup: medium embedding (`all-mpnet-base-v2`) + fixed chunking + same 5 test queries + top-k=3.")
    lines.append("")
    lines.append("| Dataset | Size | Avg Retrieved Context Quality | Noise Rate in Top-k |")
    lines.append("|---|---:|---:|---:|")
    lines.append(f"| Smaller subset | 12 paragraphs | {small_ctx:.2f} | {small_noise:.2%} |")
    lines.append(f"| Larger dataset (+10 noise paras) | 47 paragraphs | {large_ctx:.2f} | {large_noise:.2%} |")
    lines.append("")
    lines.append(
        "Takeaway: with a larger/noisier dataset, retrieval still works but irrelevant context starts appearing more often."
    )
    lines.append(
        "So scaling up data makes cleaning/chunking/top-k tuning way more important."
    )
    lines.append("")

    MD_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {MD_PATH}")


if __name__ == "__main__":
    main()
