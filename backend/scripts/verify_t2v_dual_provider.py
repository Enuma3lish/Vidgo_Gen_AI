"""One-off verification: dual-provider text-to-video (Hailuo).

Run inside the live backend image (Cloud Run Job) so it has the real
PIAPI_KEY / POLLO_API_KEY secrets and outbound internet. It exercises the
EXACT production routing path (TaskType.T2V), with NO DB and NO billing — it
calls the provider router directly.

TEST 1 — normal path: route(T2V, model=hailuo) should succeed via PiAPI
         (the primary) and return a video URL.
TEST 2 — forced failover: monkeypatch the in-process PiAPI provider to raise,
         then route again — the router must fall back to Pollo (pollo-v1-6)
         and still return a video URL. Proves the backup mechanism fires.

Spends ~2 real video generations of provider credit. Prints PASS/FAIL markers.
"""
import asyncio
import sys

from app.providers.provider_router import get_provider_router, TaskType

PROMPT = "A golden retriever puppy running across a sunny meadow, cinematic, slow motion"
PARAMS = {
    "prompt": PROMPT,
    "model": "hailuo",
    "aspect_ratio": "16:9",
    "duration": 5,
    "negative_prompt": "blurry, distorted, low quality",
}


def _summarize(tag, result):
    ok = bool(result.get("success"))
    out = result.get("output") or {}
    url = out.get("video_url")
    print(f"[{tag}] success={ok} provider_used={result.get('provider_used')} "
          f"used_backup={result.get('used_backup')} primary_failed={result.get('primary_failed')}")
    print(f"[{tag}] video_url={url}")
    if not ok:
        print(f"[{tag}] error={result.get('error')}")
    return ok, url, result.get("provider_used")


async def main() -> int:
    router = get_provider_router()
    failures = []

    # ── TEST 1 — normal dual-provider path (expect PiAPI primary) ──
    print("=== TEST 1: T2V Hailuo via normal routing (expect primary=piapi) ===", flush=True)
    r1 = await router.route(TaskType.T2V, dict(PARAMS), user_tier="pro")
    ok1, url1, prov1 = _summarize("TEST1", r1)
    if not (ok1 and url1):
        failures.append("TEST1: Hailuo T2V did not return a video via the normal path")

    # ── TEST 2 — force PiAPI to fail, expect Pollo backup to serve ──
    print("\n=== TEST 2: force PiAPI failure, expect failover to Pollo ===", flush=True)
    orig = router.piapi.text_to_video

    async def _boom(_params):
        raise RuntimeError("forced PiAPI failure (verification harness)")

    router.piapi.text_to_video = _boom  # type: ignore[assignment]
    try:
        r2 = await router.route(TaskType.T2V, dict(PARAMS), user_tier="pro")
    finally:
        router.piapi.text_to_video = orig  # type: ignore[assignment]
    ok2, url2, prov2 = _summarize("TEST2", r2)
    if not (ok2 and url2):
        failures.append("TEST2: failover did not return a video")
    elif prov2 != "pollo":
        failures.append(f"TEST2: expected provider_used=pollo on failover, got {prov2}")

    print("\n================ RESULT ================")
    if failures:
        for f in failures:
            print("FAIL:", f)
        print("VERIFY_RESULT=FAIL")
        return 1
    print("Both providers serve Hailuo/Pollo-v1-6 T2V; failover works.")
    print("VERIFY_RESULT=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
