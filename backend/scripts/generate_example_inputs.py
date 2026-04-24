"""
Generate Example Input Images — One-time script to create input images
for example mode presets using Vertex AI Gemini, then upload to GCS.

Usage:
    cd backend
    python -m scripts.generate_example_inputs

    # Dry run (show what would be generated, no API calls):
    python -m scripts.generate_example_inputs --dry-run

    # Generate only a specific tool:
    python -m scripts.generate_example_inputs --tool effect

Requires:
    - VERTEX_AI_PROJECT env var (or GEMINI_API_KEY fallback)
    - GCS_BUCKET env var
    - google-genai, google-cloud-storage packages
"""
import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def get_genai_client():
    """Initialize google-genai client (Vertex AI or API key)."""
    from google import genai

    project = os.getenv("VERTEX_AI_PROJECT", "")
    if project:
        # Image generation models are only available in us-central1
        location = os.getenv("VERTEX_AI_IMAGE_LOCATION", "us-central1")
        client = genai.Client(vertexai=True, project=project, location=location)
        logger.info(f"Using Vertex AI: project={project}, location={location}")
    else:
        api_key = os.getenv("GEMINI_API_KEY", "")
        if not api_key:
            logger.error("Set VERTEX_AI_PROJECT or GEMINI_API_KEY")
            sys.exit(1)
        client = genai.Client(api_key=api_key)
        logger.info("Using Gemini API key")
    return client


def get_gcs_service():
    """Initialize GCS storage service."""
    from app.services.gcs_storage_service import GCSStorageService

    svc = GCSStorageService()
    if not svc.enabled:
        logger.error("GCS_BUCKET not set — cannot upload images")
        sys.exit(1)
    return svc


def generate_image(client, prompt: str) -> bytes:
    """Generate an image using Imagen on Vertex AI and return PNG bytes."""
    from google.genai import types

    model = os.getenv("IMAGEN_MODEL", "imagen-3.0-generate-002")
    logger.info(f"  Generating with {model}: {prompt[:80]}...")

    response = client.models.generate_images(
        model=model,
        prompt=prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="1:1",
            output_mime_type="image/png",
        ),
    )

    if response.generated_images:
        return response.generated_images[0].image.image_bytes

    raise Exception(f"No image in Imagen response for: {prompt[:50]}")


def iter_presets(selected_tool: str | None = None):
    from app.config.example_presets import EXAMPLE_PRESETS

    for tool_type, presets in EXAMPLE_PRESETS.items():
        if selected_tool and tool_type != selected_tool:
            continue
        yield tool_type, presets


def extract_blob_name(image_url: str) -> str | None:
    """Extract the GCS blob name under examples/ from a preset URL."""
    try:
        suffix = image_url.split("/examples/", 1)[1]
    except IndexError:
        return None
    return f"examples/{suffix}"


def verify_existing_inputs(gcs, selected_tool: str | None = None) -> tuple[int, int, int]:
    """Verify all image-based example presets point to existing GCS blobs."""
    verified = 0
    skipped = 0
    errors = 0

    for tool_type, presets in iter_presets(selected_tool):
        logger.info(f"\n{'='*60}")
        logger.info(f"Verify tool: {tool_type} ({len(presets)} presets)")
        logger.info(f"{'='*60}")

        for preset in presets:
            preset_id = preset["id"]
            gemini_prompt = preset.get("gemini_prompt", "")
            image_url = preset.get("image_url", "")

            if not gemini_prompt:
                logger.info(f"  SKIP {preset_id} (no gemini_prompt — text-only tool)")
                skipped += 1
                continue

            if not image_url:
                logger.error(f"  FAIL {preset_id} (missing image_url)")
                errors += 1
                continue

            blob_name = extract_blob_name(image_url)
            if not blob_name:
                logger.error(f"  FAIL {preset_id} (image_url is not under /examples/: {image_url})")
                errors += 1
                continue

            blob = gcs.bucket.blob(blob_name)
            if not blob.exists():
                logger.error(f"  FAIL {preset_id} (missing GCS blob: {blob_name})")
                errors += 1
                continue

            logger.info(f"  OK {preset_id} → {blob_name}")
            verified += 1

    return verified, skipped, errors


def main():
    parser = argparse.ArgumentParser(description="Generate example input images")
    parser.add_argument("--dry-run", action="store_true", help="Show plan without generating")
    parser.add_argument("--tool", type=str, help="Only generate for this tool type")
    parser.add_argument("--force", action="store_true", help="Regenerate even if image exists in GCS")
    parser.add_argument("--verify", action="store_true", help="Fail if any image-based example preset is missing in GCS")
    args = parser.parse_args()

    if args.verify and args.dry_run:
        logger.error("--verify and --dry-run cannot be used together")
        sys.exit(2)

    client = None if args.dry_run or args.verify else get_genai_client()
    gcs = None if args.dry_run else get_gcs_service()

    total = 0
    skipped = 0
    existed = 0
    errors = 0

    if args.verify:
        verified, skipped, errors = verify_existing_inputs(gcs, args.tool)
        logger.info(f"\n{'='*60}")
        logger.info(f"Verify done: {verified} verified, {skipped} skipped, {errors} errors")
        logger.info(f"{'='*60}")
        sys.exit(1 if errors else 0)

    for tool_type, presets in iter_presets(args.tool):

        logger.info(f"\n{'='*60}")
        logger.info(f"Tool: {tool_type} ({len(presets)} presets)")
        logger.info(f"{'='*60}")

        for preset in presets:
            preset_id = preset["id"]
            gemini_prompt = preset.get("gemini_prompt", "")

            if not gemini_prompt:
                logger.info(f"  SKIP {preset_id} (no gemini_prompt — text-only tool)")
                skipped += 1
                continue

            # Determine GCS path from image_url
            image_url = preset.get("image_url", "")
            if not image_url:
                logger.info(f"  SKIP {preset_id} (no image_url)")
                skipped += 1
                continue

            blob_name = extract_blob_name(image_url)
            if not blob_name:
                logger.warning(f"  SKIP {preset_id} (can't parse blob name from {image_url})")
                skipped += 1
                continue

            if args.dry_run:
                logger.info(f"  [DRY RUN] {preset_id}")
                logger.info(f"    Prompt: {gemini_prompt[:80]}...")
                logger.info(f"    Upload: {blob_name}")
                total += 1
                continue

            # Check if blob already exists in GCS — skip if so (unless --force)
            if not args.force:
                blob = gcs.bucket.blob(blob_name)
                if blob.exists():
                    logger.info(f"  EXISTS {preset_id} — already in GCS, skipping")
                    existed += 1
                    continue

            try:
                img_bytes = generate_image(client, gemini_prompt)
                public_url = gcs.upload_public(img_bytes, blob_name, "image/png")
                logger.info(f"  OK {preset_id} → {public_url}")
                total += 1
                # Rate limit: wait between Imagen API calls to avoid 429
                import time
                time.sleep(5)
            except Exception as e:
                logger.error(f"  FAIL {preset_id}: {e}")
                errors += 1
                # Back off on rate limit errors
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    logger.info("  Backing off 30s for rate limit...")
                    import time
                    time.sleep(30)

    logger.info(f"\n{'='*60}")
    logger.info(f"Done: {total} generated, {existed} already existed, {skipped} skipped, {errors} errors")
    logger.info(f"{'='*60}")


if __name__ == "__main__":
    main()
