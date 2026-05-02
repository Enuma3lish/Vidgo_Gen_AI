import base64

from app.providers.vertex_ai_provider import VertexAIProvider


def test_parse_veo_nested_generated_video_uri():
    provider = VertexAIProvider()
    result = provider._parse_veo_predictions(
        {
            "name": "operation-123",
            "response": {
                "generatedVideos": [
                    {
                        "video": {
                            "gcsUri": "gs://vidgo-media-vidgo-ai/tmp/sample.mp4",
                        }
                    }
                ]
            },
        }
    )

    assert result == {
        "success": True,
        "task_id": "operation-123",
        "output": {"video_url": "gs://vidgo-media-vidgo-ai/tmp/sample.mp4"},
    }


def test_parse_veo_nested_base64_video(monkeypatch, tmp_path):
    provider = VertexAIProvider()
    monkeypatch.setattr("app.providers.vertex_ai_provider.Path", lambda _: tmp_path)
    video_bytes = b"fake mp4 bytes"

    result = provider._parse_veo_predictions(
        {
            "name": "operation-456",
            "response": {
                "videos": [
                    {
                        "bytesBase64Encoded": base64.b64encode(video_bytes).decode(),
                    }
                ]
            },
        }
    )

    assert result["success"] is True
    assert result["task_id"] == "operation-456"
    assert result["output"]["video_url"].startswith("/static/generated/veo_")
    assert next(tmp_path.glob("veo_*.mp4")).read_bytes() == video_bytes
