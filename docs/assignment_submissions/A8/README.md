# A8: RAG System — UIUC-Med

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Add your Groq API key to `UIUC-Med/.env`:
   ```
   GROQ_API_KEY=gsk_...
   ```

3. Run the notebook from the `A8/` directory:
   ```bash
   jupyter notebook rag_system.ipynb
   ```

## Notebook Structure

| Section | Content |
|---|---|
| Step 1.1 | Knowledge base — 35 medical triage paragraphs |
| Step 1.2 | 3 chunking strategies (fixed, overlapping, hybrid) |
| Step 1.3 | 3 embedding models (small/medium/large) + vector stores |
| Step 1.4 | Cosine similarity retrieval with top-k |
| Step 1.5 | Generation pipeline using Groq llama-4-maverick |

## Models Used

- **Generation**: `meta-llama/llama-4-maverick-17b-128e-instruct` (Groq) — best model from A7
- **Embedding small**: `all-MiniLM-L6-v2` (384-dim)
- **Embedding medium**: `all-mpnet-base-v2` (768-dim)
- **Embedding large**: `all-roberta-large-v1` (1024-dim)

## Notes

- Embedding models are downloaded automatically from HuggingFace on first run
- Use relative paths; do not hardcode machine-specific directories
- The `.env` file must be one level up (`../env` relative to `A8/`)
