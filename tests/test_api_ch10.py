"""Unit tests verifying ISD Chapter 10 API implementation and concepts."""

import unittest
from starlette.testclient import TestClient

import pymupdf

from ocr_system.api import app as ocr_app


class TestOCRSystemAPI(unittest.TestCase):
    """Test suite for ocr_system REST API based on ISD Chapter 10."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(ocr_app)

    def test_01_api_discovery_root(self):
        """Test API metadata discovery at /api/v1 (Chapter 10 slide 18)."""
        response = self.client.get("/api/v1")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("version", data)
        self.assertIn("resources", data)
        self.assertTrue(len(data["resources"]) >= 3)

    def test_02_health_check(self):
        """Test health check endpoint (Chapter 10 slides 26 & 27)."""
        response = self.client.get("/api/v1/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertIn("supported_engines", data)
        self.assertTrue(data["pipeline_ready"])

    def test_03_standard_error_format_404(self):
        """Test uniform error response on 404 (Chapter 10 slide 16)."""
        response = self.client.get("/api/v1/documents/missing-uuid-12345")
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertEqual(data["status"], 404)
        self.assertEqual(data["error"], "NotFound")
        self.assertIn("message", data)

    def test_04_unsupported_media_type_415(self):
        """Test file extension validation rejecting unsupported media (Chapter 10 slide 27)."""
        response = self.client.post(
            "/api/v1/ocr/process",
            files={"file": ("malicious.exe", b"binary content", "application/octet-stream")},
        )
        self.assertEqual(response.status_code, 415)
        data = response.json()
        self.assertEqual(data["status"], 415)
        self.assertEqual(data["error"], "UnsupportedMediaType")

    def test_05_corrupt_file_handling_422(self):
        """Test that unreadable/corrupt files return HTTP 422 (Chapter 10 slide 27)."""
        response = self.client.post(
            "/api/v1/ocr/process",
            files={"file": ("damaged.pdf", b"corrupted non-pdf stream", "application/pdf")},
        )
        self.assertEqual(response.status_code, 422)
        data = response.json()
        self.assertEqual(data["status"], 422)

    def test_06_process_document_success_201(self):
        """Test document processing returning HTTP 201 Created (Chapter 10 slide 26 & 30)."""
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text(
            (50, 72),
            "KMITL Curriculum\nStudent ID: 66010001\nDate: 2026-09-27\nEmail: student@kmitl.ac.th\nCourse: 06026240 API",
        )
        pdf_bytes = doc.tobytes()
        doc.close()

        response = self.client.post(
            "/api/v1/ocr/process",
            files={"file": ("sample_transcript.pdf", pdf_bytes, "application/pdf")},
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("doc_id", data)
        self.assertEqual(data["filename"], "sample_transcript.pdf")
        self.assertEqual(data["status"], "completed")
        self.assertGreaterEqual(data["page_count"], 1)

        # Check extracted common fields (regex)
        fields = data.get("extracted_fields", {})
        self.assertEqual(fields.get("numeric_id"), "66010001")
        self.assertEqual(fields.get("email"), "student@kmitl.ac.th")

        # Save doc_id for next tests
        TestOCRSystemAPI._created_doc_id = data["doc_id"]

    def test_07_get_document_by_id(self):
        """Test retrieving stored document by ID."""
        doc_id = getattr(TestOCRSystemAPI, "_created_doc_id", None)
        self.assertIsNotNone(doc_id)
        response = self.client.get(f"/api/v1/documents/{doc_id}")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["doc_id"], doc_id)
        self.assertEqual(data["filename"], "sample_transcript.pdf")

    def test_08_filtering_sorting_pagination(self):
        """Test query parameters for filtering and multi-field sorting (Chapter 10 slides 11-13)."""
        response = self.client.get(
            "/api/v1/documents?sort=desc&sort_fields=created_at&limit=5&offset=0"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertGreaterEqual(data["total"], 1)
        self.assertEqual(data["limit"], 5)
        self.assertEqual(data["offset"], 0)

    def test_09_delete_document_204(self):
        """Test deleting document returns HTTP 204 No Content (Chapter 10 slide 15)."""
        doc_id = getattr(TestOCRSystemAPI, "_created_doc_id", None)
        self.assertIsNotNone(doc_id)
        response = self.client.delete(f"/api/v1/documents/{doc_id}")
        self.assertEqual(response.status_code, 204)

        # Confirm 404 on subsequent get
        verify = self.client.get(f"/api/v1/documents/{doc_id}")
        self.assertEqual(verify.status_code, 404)

    def test_10_curriculum_extraction_endpoint(self):
        """Test curriculum extraction endpoint with sample OCR payload."""
        sample_payload = {
            "pages": [
                {
                    "page": 1,
                    "text": "06026240 API Development 3(3-0-6)\n06026201 Database Systems 3(2-2-5)",
                    "lines": [],
                }
            ]
        }
        response = self.client.post(
            "/api/v1/curriculum/extract",
            json={"program": "DSBA", "plan": "no_coop", "payload": sample_payload},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["program"], "DSBA")
        self.assertIn("total_courses", data)


if __name__ == "__main__":
    unittest.main()
