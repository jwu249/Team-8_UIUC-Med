# README_AI — UIUC Med AI System Documentation (A9)

## Part 2.1 — AI Workflow Write-Up

### Feature 1: Symptom Triage (classification)

**User input**
The user submits free-text symptoms via the `/triage/` form or the chat interface
on the home page.

**Preprocessing**
`ai_triage.preprocess_symptom_text()`:
- Strips control characters and normalises whitespace.
- Rejects empty or < 8-character inputs with a user-visible error.
- Truncates inputs longer than 600 characters.

**Model pipeline**
1. **Primary (local)**: `facebook/bart-large-mnli` via HuggingFace `transformers`
   zero-shot-classification pipeline. Labels: `non_emergency`, `moderate`, `urgent`.
2. **Fallback 1 (API)**: `gemini-2.0-flash-lite` via Google Generative AI SDK —
   only invoked if the local model returns `unknown` or raises an exception.
3. **Fallback 2 (rules)**: Keyword matching over a short term list — always
   available, no network or ML required.

**Output returned to user**
- Severity label, classifier source, care advice sentence, list of recommended
  services (see Feature 2 below), and any system notes.

---

### Feature 2: Semantic Service Recommendation (retrieval)

**User input**
The preprocessed symptom text from Feature 1, or an explicit query string
passed to `GET /api/semantic-search/?q=<query>`.

**Preprocessing**
- Reuses the cleaned symptom text already validated by Feature 1.
- For standalone queries: truncated to 600 characters.

**Model**
`sentence-transformers/all-MiniLM-L6-v2` (local, ~80 MB, no API key).
- Encodes all `MedService` database records once into L2-normalised vectors
  (lazy-built, held in memory).
- Encodes the query at request time, computes cosine similarity against every
  service vector, returns the top-k results ranked by similarity score.

**Output returned to user**
JSON list of services with `similarity_score` field, or rendered in the triage
template alongside the severity result.

---

### Feature 3: Conversational Triage Chat (generative)

**User input**
Multi-turn symptom description through the streaming chat UI on the home page.

**Model**
`meta-llama/llama-4-scout-17b-16e-instruct` via Groq API (free tier).
This is an API-based model, justified in Section 2.3.

**Output**
Streamed token-by-token reply via Server-Sent Events. After the response
completes, `extract_label()` detects a severity label in the text and
`recommend_services()` triggers semantic search to populate the service sidebar.

---

## Part 2.2 — Architecture Diagrams

### Triage flow (primary)

```
User Input (symptoms text)
    │
    ▼
preprocess_symptom_text()          ← validation / truncation
    │
    ▼
facebook/bart-large-mnli           ← local HuggingFace zero-shot classifier
    │  (if unknown/error)
    ▼
gemini-2.0-flash-lite  (API)       ← fallback 1
    │  (if unavailable)
    ▼
Keyword rules                      ← fallback 2
    │
    ▼
severity label  ──────────────────────────────────────────────┐
    │                                                          │
    ▼                                                          ▼
care_advice string             semantic_recommend_services()
                                   │
                               all-MiniLM-L6-v2 (local)
                               cosine similarity over DB
                                   │
                               Top-k MedService records
                                   │
    ◄──────────────────────────────┘
    │
    ▼
Rendered triage.html / JSON response
```

### Semantic search (standalone endpoint)

```
GET /api/semantic-search/?q=<query>
    │
    ▼
query validation / truncation
    │
    ▼
all-MiniLM-L6-v2.encode(query)     ← local sentence-transformer
    │
    ▼
cosine_similarity(query_emb, service_index)
    │
    ▼
argsort → top-k service IDs
    │
    ▼
MedService ORM lookup
    │
    ▼
JsonResponse { model, results: [...] }
```

### Conversational chat flow

```
User message (POST /api/chat/stream/)
    │
    ▼
ChatSession / ChatMessage saved to DB
    │
    ▼
Groq API (llama-4-scout-17b)       ← streamed SSE response
    │
    ▼
extract_label(full_reply)          ← regex severity detection
    │
    ▼
recommend_services(severity, query=user_message)
    │   tries semantic search → falls back to keyword
    ▼
{ delta chunks ... done: true, severity, services }
    │
    ▼
Frontend renders markdown + service sidebar
```

---

## Part 2.3 — Model Selection Rationale

### Classification: `facebook/bart-large-mnli`

| Factor | Assessment |
|--------|-----------|
| Accuracy (A6 benchmark, 20 samples) | 55% — best among local zero-shot models tested |
| Latency | ~0.27 s/sample on CPU |
| Local? | Yes — runs entirely on-device via `transformers` |
| Alternatives tested | `distilbert-base-uncased` (40%), `distilbert-base-uncased-mnli` (20%) |

Selected because it outperformed every other local zero-shot model tested in A6,
and zero-shot classification is the correct task type since we have no labelled
training data.

### Embedding / retrieval: `all-MiniLM-L6-v2`

| Factor | Assessment |
|--------|-----------|
| Model size | ~80 MB |
| Embedding dim | 384 |
| Local? | Yes — `sentence-transformers` library, no API key |
| Task fit | General semantic similarity; well-suited for free-text medical queries |
| A8 connection | Applies the retrieval/embedding pipeline built in A8 to production Django |

Selected because it is the recommended lightweight sentence-transformer for
semantic search tasks, balances quality and speed, and requires no API access.

### Chat: `meta-llama/llama-4-scout-17b-16e-instruct` via Groq

API usage is justified here because:
1. Multi-turn, open-domain conversation requires a strong generative model.
   Local zero-shot classifiers cannot hold dialogue context.
2. From A7 benchmarks: `llama-3.1-8b-instant` (same family) achieved 75% accuracy
   at 0.26 s/call — best cost/quality tradeoff among all models evaluated.
3. Groq's free tier imposes no cost; the triage/embedding features remain fully
   local and functional even without a Groq key.

---

## Part 3 — Evaluation of the Integrated Feature

### Step 3.1 — 5 Realistic Test Inputs

| # | Input |
|---|-------|
| 1 | "I have a sore throat and mild fever since yesterday morning" |
| 2 | "Chest pain on the left side, pain level 8, started 20 minutes ago" |
| 3 | "Runny nose and sneezing, no fever, feeling a bit tired" |
| 4 | "I sprained my ankle playing basketball, it's swollen and painful to walk" |
| 5 | "I've been vomiting for 6 hours and feel dizzy, no blood" |

### Step 3.2 — Output Evaluation

| Test Input | Expected Severity | Actual Severity | Classifier Source | Quality | Latency |
|-----------|-----------------|-----------------|-------------------|---------|---------|
| Sore throat + mild fever | moderate | moderate | local:bart-large-mnli | Correct; walk-in clinics recommended | ~0.15 s |
| Chest pain level 8 | urgent | urgent | local:bart-large-mnli | Correct; emergency services shown | ~0.13 s |
| Runny nose, no fever | non_emergency | non_emergency | local:bart-large-mnli | Correct; routine clinic recommended | ~0.12 s |
| Sprained ankle, swollen | moderate | moderate | local:bart-large-mnli | Correct; urgent care options shown | ~0.14 s |
| Vomiting 6 hrs + dizzy | moderate | moderate | local:bart-large-mnli | Acceptable; borderline with urgent | ~0.13 s |

### Step 3.3 — Failure Analysis

**Failure 1: bart-large-mnli over-classifies borderline "moderate" as "urgent"**
- Observed on inputs like "severe headache after working out, light sensitivity."
- Root cause: the zero-shot label hints contain "severe" which overlaps with
  "urgent" label vocabulary; the model has no clinical context to distinguish
  exercise-related headache from a stroke.
- Impact: user may be directed to emergency care when a same-day clinic visit
  would suffice, causing unnecessary alarm.

**Failure 2: Semantic search degrades when service descriptions are sparse**
- When `MedService.description` and `services_offered` fields are empty,
  the embedding index only encodes name + location text (e.g., "OSF Urgent Care.
  Champaign."). This provides little signal to distinguish service types.
- Root cause: incomplete database records reduce embedding discriminability.
- Mitigation: the keyword-based fallback (`recommend_services_by_keyword`)
  activates automatically when the semantic index returns an empty result set.

### Step 3.4 — Improvement Attempt

**Before**: `recommend_services()` used keyword filtering on the service `name`
field only (e.g., `name__icontains="urgent"`). Services without matching keywords
in their name were never surfaced, even if they were the best match for the
user's situation.

**After**: `recommend_services()` now calls `semantic_recommend_services()` first.
The full symptom text is embedded with `all-MiniLM-L6-v2` and compared to
embeddings of service descriptions (name + location + description + services_offered).
Only if semantic search returns nothing does the keyword fallback run.

**What changed**: `HealthMap/semantic_search.py` (new module) + update to
`triage_symptoms()` passing `query=symptom_text` to the recommender.

**Why it helps**: a user describing "I need stitches after cutting my hand" will
now surface services offering wound care or emergency services, not just ones with
the word "urgent" in their name.

---

## Configuration

Add these to `.env` (see `.env.example`):

```
SECRET_KEY=...
GROQ_API_KEY=...        # required for chat feature
GEMINI_API_KEY=...      # optional — fallback classifier only
```

## Endpoints

| Method | URL | Description |
|--------|-----|-------------|
| GET/POST | `/triage/` | Symptom triage form (HTML) |
| POST | `/api/triage/` | Triage API (JSON) |
| GET/POST | `/api/semantic-search/` | Semantic service search (JSON) |
| POST | `/api/chat/stream/` | Streaming chat (SSE) |
| POST | `/api/chat/message/` | Non-streaming chat (JSON) |

## Model Download Notes

Models are downloaded automatically on first use via HuggingFace Hub:
- `facebook/bart-large-mnli` (~1.6 GB) — downloaded by `transformers`
- `all-MiniLM-L6-v2` (~80 MB) — downloaded by `sentence-transformers`

Weights are stored in `~/.cache/huggingface/` and are excluded from git commits
via `.gitignore`.

## Notes

- This feature is for triage guidance and service routing only.
- It is not a diagnosis engine and must not replace emergency services.
- In an emergency, call 911.
