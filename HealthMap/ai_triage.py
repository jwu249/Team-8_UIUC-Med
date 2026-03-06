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
MAX_INPUT_CHARS = 600

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


def recommend_services(severity: str, limit: int = 5) -> list[dict[str, Any]]:
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

    rows = qs.order_by("name").values("id", "name", "location", "appointments_required")[:limit]
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "location": row["location"],
            "appointments_required": row["appointments_required"],
            "url": reverse("service-detail", kwargs={"pk": row["id"]}),
        }
        for row in rows
    ]


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
        "recommendations": recommend_services(severity),
        "notes": errors,
    }
