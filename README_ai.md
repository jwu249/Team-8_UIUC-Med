# README_ai

## Part 2 System Description

### Workflow Overview
`/triage/` is the user-facing symptom triage page.  
`/api/triage/` is the programmatic endpoint used for integration/testing.

Pipeline:
1. User submits symptom text.
2. Input is preprocessed and validated.
3. Local Hugging Face classifier runs first.
4. If local inference fails or returns unknown, Gemini fallback runs.
5. If Gemini is unavailable, a minimal keyword-rule fallback is used.
6. The app returns:
   - severity (`non_emergency`, `moderate`, `urgent`)
   - classifier source (`local:*`, `gemini:*`, or `rules:*`)
   - short care advice
   - recommended services from database

### Data Input
- Source: free-text symptom description entered by user.
- Entry points:
  - HTML form: `/triage/`
  - JSON/form POST: `/api/triage/`
- Expected payload:
  - form: `symptoms=<text>`
  - json: `{"symptoms": "<text>"}`

### Preprocessing
- Remove control characters.
- Normalize whitespace.
- Enforce minimum detail and non-empty input.
- Truncate long inputs to 600 characters.

### Safety Guardrails
- The model is constrained to three output labels only.
- Output is parsed and normalized before use.
- Unknown/invalid model outputs are rejected and trigger fallback.
- The UI includes non-diagnostic wording and care escalation guidance.
- Errors are handled without exposing secrets.

## Local LLM Integration (Hugging Face)

- Module: `HealthMap/ai_triage.py`
- Local model: `facebook/bart-large-mnli`
- Task: zero-shot classification over fixed labels.
- Lazy-loaded pipeline: model downloads when first used in local server runtime.

## External AI API Integration (Gemini)

- Provider: Google Gemini (`google-generativeai`)
- Model: `gemini-2.0-flash-lite`
- Role: fallback classifier only (activated when local model path fails).
- Required environment variable:
  - `GEMINI_API_KEY=...`

## Configuration

Add these keys to `.env`:
- `GEMINI_API_KEY=...`
- optional: `HF_TOKEN=...` for better Hugging Face rate limits

## Endpoints

- `GET /triage/` - render triage page
- `POST /triage/` - submit symptoms via form
- `POST /api/triage/` - triage API response in JSON

## Notes

- This feature is for triage guidance and service routing only.
- It is not a diagnosis engine and should not replace emergency services.
