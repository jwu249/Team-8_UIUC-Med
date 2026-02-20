from django.test import TestCase
from django.urls import reverse

from .models import MedService


class Part1InternalApiAndChartsTests(TestCase):
    # ELI5:
    # We make a tiny sample dataset so tests don't depend on real prod data.
    # Then we ask our endpoints for data/pages and verify shape/content quickly.
    @classmethod
    def setUpTestData(cls):
        MedService.objects.create(
            name="Carle Family Clinic",
            location="Urbana",
            appointments_required=True,
        )
        MedService.objects.create(
            name="Campus Care",
            location="Champaign",
            appointments_required=False,
        )
        MedService.objects.create(
            name="Urbana Urgent Care",
            location="Urbana",
            appointments_required=False,
        )

    def test_api_summary_returns_chart_ready_json_list(self):
        response = self.client.get(reverse("api-summary"))
        self.assertEqual(response.status_code, 200)

        # Should be JSON list [{category, count}, ...]
        data = response.json()
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        self.assertIn("category", data[0])
        self.assertIn("count", data[0])

        # Quick sanity check: Urbana should have 2 in our seed data.
        urbana_row = next((row for row in data if row["category"] == "Urbana"), None)
        self.assertIsNotNone(urbana_row)
        self.assertEqual(urbana_row["count"], 2)

    def test_api_summary_appointments_returns_chart_ready_json_list(self):
        response = self.client.get(reverse("api-summary-appointments"))
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertIsInstance(data, list)
        self.assertGreaterEqual(len(data), 1)
        self.assertIn("category", data[0])
        self.assertIn("count", data[0])

        # We seeded 1 "Appointments Required" and 2 "Walk-In / Optional"
        counts = {row["category"]: row["count"] for row in data}
        self.assertEqual(counts.get("Appointments Required"), 1)
        self.assertEqual(counts.get("Walk-In / Optional"), 2)

    def test_vega_chart_hub_page_loads(self):
        response = self.client.get(reverse("service-chart"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vega-Lite Charts")

    def test_vega_chart1_page_loads_and_points_to_internal_api(self):
        response = self.client.get(reverse("vega-chart1"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("api-summary"))

    def test_vega_chart2_page_loads_and_points_to_internal_api(self):
        response = self.client.get(reverse("vega-chart2"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("api-summary-appointments"))
