
import unittest
from io import BytesIO

from fastapi.testclient import TestClient
from app.api.v1.demo import router
from fastapi import FastAPI
from unittest.mock import MagicMock, patch
import os
from PIL import Image

# Create a minimal app for testing just the router
app = FastAPI()
app.include_router(router, prefix="/api/v1/demo")

client = TestClient(app)

class TestUploadEndpoint(unittest.TestCase):
    def test_upload_endpoint(self):
        """
        Test the POST /api/v1/demo/upload endpoint.
        """
        image_buffer = BytesIO()
        Image.new("RGB", (128, 128), "white").save(image_buffer, format="PNG")
        file_content = image_buffer.getvalue()
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
        self.assertIn("static_path", data)
        self.assertTrue(data["static_path"].startswith("/static/uploads/"))
        self.assertTrue(data["url"].endswith(data["static_path"]))
        self.assertTrue(data["url"].endswith(".png"))
        
        print(f"\n✅ Upload Endpoint Test Passed! URL: {data['url']}")

if __name__ == "__main__":
    unittest.main()
