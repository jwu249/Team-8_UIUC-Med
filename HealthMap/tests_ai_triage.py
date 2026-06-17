import json
from unittest.mock import patch

from django.contrib.auth.models import User as DjangoUser
from django.test import TestCase
from django.urls import reverse

from .ai_triage import SymptomInputError, extract_label, preprocess_symptom_text, recommend_services
from .models import MedService


class AITriageUnitTests(TestCase):
    def test_preprocess_rejects_blank_text(self):
        with self.assertRaises(SymptomInputError):
            preprocess_symptom_text("   ")

    def test_extract_label_supports_variants(self):
        self.assertEqual(extract_label("non emergency"), "non_emergency")
        self.assertEqual(extract_label("moderate"), "moderate")
        self.assertEqual(extract_label("Urgent care now"), "urgent")

    def test_recommend_services_returns_records(self):
        MedService.objects.create(
            name="Campus Clinic",
            location="Champaign",
            appointments_required=True,
            services_offered="Primary care",
        )
        MedService.objects.create(
            name="OSF Urgent Care",
            location="Urbana",
            appointments_required=False,
            services_offered="Urgent care",
        )

        recommendations = recommend_services("moderate")
        self.assertGreaterEqual(len(recommendations), 1)
        self.assertIn("name", recommendations[0])


class AITriageApiTests(TestCase):
    def setUp(self):
        self.user = DjangoUser.objects.create_user(
            username="triage_tester",
            email="triage@example.com",
            password="pass1234!",
        )
        self.client.force_login(self.user)
        self.url = reverse("api-triage")

    @patch("HealthMap.views.triage_symptoms")
    def test_api_triage_success_json(self, mock_triage):
        mock_triage.return_value = {
            "symptoms": "sore throat and fever",
            "severity": "moderate",
            "classifier_source": "local:facebook/bart-large-mnli",
            "care_advice": "Use same-day clinic or urgent care.",
            "recommendations": [],
            "notes": [],
        }

        response = self.client.post(
            self.url,
            data=json.dumps({"symptoms": "sore throat and fever"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["severity"], "moderate")
        self.assertIn("classifier_source", payload)

    @patch("HealthMap.views.triage_symptoms")
    def test_api_triage_validation_error(self, mock_triage):
        mock_triage.side_effect = SymptomInputError("Please describe at least one symptom.")

        response = self.client.post(
            self.url,
            data=json.dumps({"symptoms": ""}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json())
