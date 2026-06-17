import os
import re
from typing import Any

from django.db.models import Q
from django.urls import reverse

from .models import MedService


class SymptomInputError(ValueError):
    """Raised when user symptom text fails input validation."""


SEVERITY_LABELS = ("non_emergency", "moderate", "urgent")
LOCAL_MODEL_ID = "facebook/bart-large-mnli"
GEMINI_MODEL_ID = "gemini-2.0-flash-lite"
GROQ_MODEL_ID = "meta-llama/llama-4-scout-17b-16e-instruct"
MAX_INPUT_CHARS = 600

_CHAT_SYSTEM_PROMPT = (
    "You are a helpful medical triage assistant for UIUC Med, a student health resource finder. "
    "Your role is to listen to users describe their symptoms, assess how urgent their situation is, "
    "and guide them toward the right level of care (home monitoring, clinic visit, urgent care, or emergency room). "
    "Be conversational, empathetic, and clear. Ask follow-up questions when needed to better understand symptoms. "
    "When you identify a severity level, label it clearly as non-emergency, moderate, or urgent. "
    "Always remind users you are not a substitute for professional medical advice. "
    "If someone describes an emergency (chest pain, difficulty breathing, stroke symptoms, severe bleeding, etc.), "
    "immediately tell them to call 911 or go to the nearest emergency room."
)

_LOCAL_LABEL_HINTS = {
    "non_emergency": "non_emergency - mild symptoms, stable, can monitor at home",
    "moderate": "moderate - should seek same-day clinic or urgent care",
    "urgent": "urgent - severe symptoms or possible emergency",
}

_local_classifier = None


def preprocess_symptom_text(raw_text: str) -> str:
    if not isinstance(raw_text, str):
        raise SymptomInputError("Symptoms must be provided as text.")

    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", raw_text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        raise SymptomInputError("Please describe at least one symptom.")
    if len(cleaned) < 8:
        raise SymptomInputError("Please provide a bit more detail about your symptoms.")
    if len(cleaned) > MAX_INPUT_CHARS:
        cleaned = cleaned[:MAX_INPUT_CHARS].rstrip()

    return cleaned


def extract_label(raw_output: str) -> str:
    if not raw_output:
        return "unknown"

    text = raw_output.strip().lower()
    normalized = text.replace("-", "_").replace(" ", "_")

    if re.search(r"(^|[^a-z])non[_ ]?emergency($|[^a-z])", normalized):
        return "non_emergency"
    if re.search(r"(^|[^a-z])moderate($|[^a-z])", normalized):
        return "moderate"
    if re.search(r"(^|[^a-z])urgent($|[^a-z])", normalized):
        return "urgent"
    return "unknown"


def _get_local_classifier():
    global _local_classifier
    if _local_classifier is not None:
        return _local_classifier

    try:
        from transformers import pipeline
    except Exception as exc:
        raise RuntimeError("transformers is not installed in this environment.") from exc

    _local_classifier = pipeline("zero-shot-classification", model=LOCAL_MODEL_ID)
    return _local_classifier


def classify_with_local_model(symptom_text: str) -> tuple[str, str]:
    classifier = _get_local_classifier()
    labels = list(_LOCAL_LABEL_HINTS.values())
    output = classifier(symptom_text, candidate_labels=labels, multi_label=False)
    top_label_hint = output["labels"][0]

    for label, hint in _LOCAL_LABEL_HINTS.items():
        if hint == top_label_hint:
            return label, f"local:{LOCAL_MODEL_ID}"
    return "unknown", f"local:{LOCAL_MODEL_ID}"


def classify_with_gemini(symptom_text: str) -> tuple[str, str]:
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    try:
        import google.generativeai as genai
    except Exception as exc:
        raise RuntimeError("google-generativeai is not installed.") from exc

    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel(GEMINI_MODEL_ID)

    prompt = (
        "Classify the medical severity into exactly one label: "
        "non_emergency, moderate, or urgent.\n"
        f"Symptoms: {symptom_text}\n"
        "Return only one label."
    )

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0,
            max_output_tokens=10,
        ),
    )
    raw_text = (getattr(response, "text", "") or "").strip()
    label = extract_label(raw_text)
    if label == "unknown":
        raise RuntimeError("Gemini did not return a valid severity label.")
    return label, f"gemini:{GEMINI_MODEL_ID}"


def classify_with_rules(symptom_text: str) -> tuple[str, str]:
    text = symptom_text.lower()

    urgent_terms = (
        "chest pain",
        "shortness of breath",
        "cannot breathe",
        "face drooping",
        "heavy bleeding",
        "lost vision",
        "pain level 9",
        "stroke",
    )
    moderate_terms = (
        "fever",
        "vomiting",
        "diarrhea",
        "swollen",
        "persistent cough",
        "painful",
        "ear hurts",
    )

    if any(term in text for term in urgent_terms):
        return "urgent", "rules:keyword"
    if any(term in text for term in moderate_terms):
        return "moderate", "rules:keyword"
    return "non_emergency", "rules:default"


def recommend_services_by_keyword(severity: str, limit: int = 5) -> list[dict[str, Any]]:
    qs = MedService.objects.all()

    if severity == "urgent":
        qs = qs.filter(
            Q(name__icontains="urgent")
            | Q(name__icontains="emergency")
            | Q(appointments_required=False)
        )
    elif severity == "moderate":
        qs = qs.filter(
            Q(name__icontains="clinic")
            | Q(name__icontains="urgent")
            | Q(appointments_required=False)
        )
    else:
        qs = qs.filter(Q(name__icontains="clinic") | Q(appointments_required=True))

    if not qs.exists():
        qs = MedService.objects.all()

    rows = qs.order_by("name").values(
        "id", "name", "location", "appointments_required",
        "google_rating", "hours", "description",
    )[:limit]
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "location": row["location"],
            "appointments_required": row["appointments_required"],
            "google_rating": float(row["google_rating"]) if row["google_rating"] else None,
            "hours": row["hours"],
            "description": row["description"],
            "url": reverse("service-detail", kwargs={"pk": row["id"]}),
        }
        for row in rows
    ]


def recommend_services(severity: str, query: str = "", limit: int = 5) -> list[dict[str, Any]]:
    """
    Primary recommendation function.

    Tries semantic search first (sentence-transformers, local model).
    Falls back to keyword filtering if semantic search is unavailable or returns
    nothing.

    `query` should be the preprocessed symptom text so the embeddings can find
    services whose descriptions best match the user's specific situation.
    """
    # Build a combined search query from both the symptom text and severity.
    search_query = query or severity

    if search_query:
        try:
            from .semantic_search import semantic_recommend_services
            results = semantic_recommend_services(search_query, top_k=limit)
            if results:
                return results
        except Exception:
            pass  # fall through to keyword fallback

    # Keyword-based fallback (always available, no ML required)
    return recommend_services_by_keyword(severity, limit=limit)


def stream_chat_with_groq(messages: list[dict]):
    """
    Stream a conversation from Groq, yielding (delta, full_text, is_done) tuples.
    The final tuple has is_done=True and delta="".
    """
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    try:
        from groq import Groq
    except Exception as exc:
        raise RuntimeError("groq is not installed. Run: pip install groq") from exc

    client = Groq(api_key=groq_api_key)
    full_messages = [{"role": "system", "content": _CHAT_SYSTEM_PROMPT}] + messages

    stream = client.chat.completions.create(
        model=GROQ_MODEL_ID,
        messages=full_messages,
        temperature=0.3,
        max_tokens=600,
        stream=True,
    )

    full_reply = ""
    for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        full_reply += delta
        yield delta, full_reply, False
    yield "", full_reply, True


def chat_with_groq(messages: list[dict]) -> str:
    """
    Send a multi-turn conversation to Groq and return the assistant's reply.

    `messages` is a list of {"role": "user"|"assistant", "content": "..."} dicts
    representing the full conversation so far (including the latest user message).
    """
    groq_api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not groq_api_key:
        raise RuntimeError("GROQ_API_KEY is not configured.")

    try:
        from groq import Groq
    except Exception as exc:
        raise RuntimeError("groq is not installed. Run: pip install groq") from exc

    client = Groq(api_key=groq_api_key)
    full_messages = [{"role": "system", "content": _CHAT_SYSTEM_PROMPT}] + messages

    response = client.chat.completions.create(
        model=GROQ_MODEL_ID,
        messages=full_messages,
        temperature=0.3,
        max_tokens=600,
    )
    return response.choices[0].message.content.strip()


def triage_symptoms(raw_text: str) -> dict[str, Any]:
    symptom_text = preprocess_symptom_text(raw_text)
    errors: list[str] = []

    try:
        severity, source = classify_with_local_model(symptom_text)
        if severity == "unknown":
            raise RuntimeError("Local model returned unknown label.")
    except Exception as exc:
        errors.append(f"local_error={exc}")
        try:
            severity, source = classify_with_gemini(symptom_text)
        except Exception as gemini_exc:
            errors.append(f"gemini_error={gemini_exc}")
            severity, source = classify_with_rules(symptom_text)

    care_advice = {
        "non_emergency": "Monitor symptoms and consider a routine clinic visit if not improving.",
        "moderate": "Use same-day clinic or urgent care. Seek help sooner if symptoms worsen.",
        "urgent": "Seek emergency care now or call emergency services if symptoms are severe.",
    }[severity]

    return {
        "symptoms": symptom_text,
        "severity": severity,
        "classifier_source": source,
        "care_advice": care_advice,
        "recommendations": recommend_services(severity, query=symptom_text),
        "notes": errors,
    }
