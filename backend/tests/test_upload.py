
import unittest
from fastapi.testclient import TestClient
from app.api.v1.demo import router
from fastapi import FastAPI
from unittest.mock import MagicMock, patch
import os

# Create a minimal app for testing just the router
app = FastAPI()
app.include_router(router, prefix="/api/v1/demo")

client = TestClient(app)

class TestUploadEndpoint(unittest.TestCase):
    def test_upload_endpoint(self):
        """
        Test the POST /api/v1/demo/upload endpoint.
        """
        # Create a dummy file content
        file_content = b"fake image content"
        files = {"file": ("test_image.png", file_content, "image/png")}

        # Mock the file opening/writing/pathlib to avoid actual disk I/O/mkdir
        with patch("shutil.copyfileobj") as mock_copy:
            with patch("builtins.open", MagicMock()) as mock_open:
                with patch("pathlib.Path.mkdir") as mock_mkdir:
                     response = client.post("/api/v1/demo/upload", files=files)

        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("url", data)
        self.assertTrue(data["url"].startswith("/static/uploads/"))
        self.assertTrue(data["url"].endswith(".png"))
        
        print(f"\n✅ Upload Endpoint Test Passed! URL: {data['url']}")

if __name__ == "__main__":
    unittest.main()
