#!/usr/bin/env python3
"""
Admin smoke-test for every tool on the deployed VidGo site.

- Logs in once with the admin account, then reuses the auth state.
- For every case in the catalog, navigates to the tool route,
  uploads/fills inputs, clicks the action button, and waits for an API
  response that contains a result URL or terminal status.
- No screen recording. Each case is wrapped in asyncio.wait_for so a
  single hung case cannot block the whole run.
- Writes TEST/admin_test_report.json and prints a per-tool pass/fail tally.

Env overrides:
  VIDGO_FRONTEND_URL       default https://vidgo.co
  ADMIN_ACCOUNT / ADMIN_PASSWORD
  VIDGO_MAX_WAIT_SEC       default 900   (per-case API wait)
  VIDGO_CASE_HARD_TIMEOUT  default 1000  (asyncio.wait_for cap)
"""
import asyncio
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright, BrowserContext, Page, Response, TimeoutError as PlaywrightTimeoutError

FRONTEND = os.getenv("VIDGO_FRONTEND_URL", "https://vidgo.co").rstrip("/")
EMAIL = os.getenv("ADMIN_ACCOUNT", "vidgo168@gmail.com")
PASSWORD = os.getenv("ADMIN_PASSWORD", "Vidgo96003146")
MAX_WAIT_SEC = int(os.getenv("VIDGO_MAX_WAIT_SEC", "3000"))
CASE_HARD_TIMEOUT = int(os.getenv("VIDGO_CASE_HARD_TIMEOUT", "3000"))
POLL_INTERVAL_SEC = float(os.getenv("VIDGO_POLL_INTERVAL_SEC", "10"))
NO_API_OBSERVED_TIMEOUT_SEC = float(os.getenv("VIDGO_NO_API_TIMEOUT_SEC", "45"))

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "TEST" / "Test_material" / "vidgo_tool_input_catalog.json"
ASSET_ROOT = ROOT / "TEST" / "Test_material"
OUT_ROOT = ROOT / "TEST"
TMP_ASSET_ROOT = OUT_ROOT / "tmp_remote_assets"
STATE_FILE = OUT_ROOT / ".admin_auth_state.json"
REPORT_FILE = OUT_ROOT / "admin_test_report.json"

GENERATE_BUTTON_PATTERNS = [
    re.compile(r"remove background", re.I),
    re.compile(r"upscale", re.I),
    re.compile(r"translate image", re.I),
    re.compile(r"translate", re.I),
    re.compile(r"generate dubbed", re.I),
    re.compile(r"dub", re.I),
    re.compile(r"transform", re.I),
    re.compile(r"apply", re.I),
    re.compile(r"try\s*on", re.I),
    re.compile(r"redesign", re.I),
    re.compile(r"generate", re.I),
    re.compile(r"create", re.I),
    re.compile(r"start", re.I),
    re.compile(r"去除背景"),
    re.compile(r"去背"),
    re.compile(r"放大"),
    re.compile(r"翻譯"),
    re.compile(r"配音"),
    re.compile(r"變換"),
    re.compile(r"套用"),
    re.compile(r"試穿"),
    re.compile(r"改造"),
    re.compile(r"生成"),
    re.compile(r"開始"),
]

EXACT_GENERATE_LABELS = [
    "確認生成", "立即生成", "開始生成", "生成",
    "Generate", "Render now", "Render",
    "去除背景", "Remove Background",
    "放大", "Upscale",
    "翻譯", "Translate",
    "配音", "產生配音影片", "Generate Dubbed Video", "Dub", "Dubbing",
    "套用", "Apply Style", "Apply",
    "試穿", "Try On",
    "改造", "重新設計", "Redesign",
    "AI 變換", "變換", "Transform", "Start Transform", "開始轉換",
]
BLOCKED_BUTTON_TEXT_SUBSTRINGS = (
    "AI 自由變換",
    "AI Transform",
    "設計生成",
    "Design Generation",
    "產生範例配音",
    "Generate Example",
)

TOOL_API_HINTS = (
    "/api/v1/tools/",
    "/api/v1/generate/",
    "/api/v1/demo/",
    "/api/v1/avatar/",
    "/api/v1/interior/",
    "/api/v1/effects/",
    "/api/v1/uploads/",
)
IGNORED_API_HINTS = (
    "/api/v1/demo/inputs/",
    "/api/v1/demo/presets/",
    "/api/v1/demo/effects/",
    "/api/v1/demo/tool-showcases/",
    "/api/v1/demo/inspiration",
    "/api/v1/session/",
)
RESULT_KEYS = (
    "result_url",
    "image_url",
    "video_url",
    "result_image_url",
    "result_video_url",
    "result_watermarked_url",
    "output_url",
)
TERMINAL_STATUS = {"completed", "succeeded", "success", "failed", "error"}
PENDING_STATUS = {"processing", "pending", "queued", "running", "in_progress"}

MODEL_THUMBNAIL_MAP: dict[str, list[str]] = {
    "female-1": ["女模特 1", "Female 1"],
    "female-2": ["女模特 2", "Female 2"],
    "female-3": ["女模特 3", "Female 3"],
    "male-1": ["男模特 1", "Male 1"],
    "male-2": ["男模特 2", "Male 2"],
    "male-3": ["男模特 3", "Male 3"],
}

ROOM_TYPE_LABELS: dict[str, list[str]] = {
    "living_room": ["客廳", "Living"],
    "bedroom": ["臥室", "Bedroom"],
    "kitchen": ["廚房", "Kitchen"],
    "bathroom": ["浴室", "Bathroom"],
    "dining_room": ["餐廳", "Dining"],
    "study_room": ["書房", "Study"],
    "balcony": ["陽台", "Balcony"],
}
ROOM_STYLE_LABELS: dict[str, list[str]] = {
    "modern_minimalist": ["現代極簡", "Modern Minimalist"],
    "scandinavian": ["北歐風格", "Scandinavian"],
    "japanese": ["日式禪風", "Japanese"],
    "industrial": ["工業風", "Industrial"],
    "bohemian": ["波西米亞", "Bohemian"],
    "mediterranean": ["地中海風格", "Mediterranean"],
    "art_deco": ["裝飾藝術", "Art Deco"],
    "mid_century_modern": ["中世紀現代", "Mid-Century"],
    "coastal": ["海岸風格", "Coastal"],
    "farmhouse": ["農舍風格", "Farmhouse"],
}
PATTERN_STYLE_LABELS: dict[str, list[str]] = {
    "floral": ["花卉風格", "Floral"],
    "geometric": ["幾何圖形", "Geometric"],
    "abstract": ["抽象藝術", "Abstract"],
    "traditional": ["傳統紋樣", "Traditional"],
    "3d": ["3D設計", "3D"],
    "interior": ["室內設計", "Interior"],
    "mockup": ["產品展示", "Mockup", "Product"],
}


def is_tool_action_url(url: str) -> bool:
    if any(ignored in url for ignored in IGNORED_API_HINTS):
        return False
    return any(hint in url for hint in TOOL_API_HINTS)


def is_generation_request_url(url: str) -> bool:
    return is_tool_action_url(url) and "/api/v1/demo/upload" not in url


def compact_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    query = f"?{parsed.query[:80]}" if parsed.query else ""
    return f"{parsed.path}{query}"


def slugify(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "_", name).strip("_")


def _ext_from_url(url: str, fallback: str = "bin") -> str:
    path = urllib.parse.urlparse(url).path
    name = path.rsplit("/", 1)[-1]
    if "." in name:
        ext = name.rsplit(".", 1)[-1].lower()
        if 1 <= len(ext) <= 5 and ext.isalnum():
            return ext
    return fallback


async def materialize_case_asset(case: dict[str, Any], case_id: str) -> Path | None:
    rel = case.get("source_asset")
    local_path = (ASSET_ROOT / rel) if rel else None
    if local_path and local_path.exists():
        return local_path
    remote_asset = case.get("remote_asset")
    if not isinstance(remote_asset, str) or not remote_asset.startswith(("http://", "https://")):
        return None
    TMP_ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    ext = _ext_from_url(remote_asset, fallback="mp4" if remote_asset.lower().endswith(".mp4") else "png")
    dest = TMP_ASSET_ROOT / f"{slugify(case_id)}.{ext}"
    if dest.exists() and dest.stat().st_size > 0:
        return dest

    def _download() -> None:
        req = urllib.request.Request(remote_asset, headers={"User-Agent": "vidgo-admin-test/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            dest.write_bytes(resp.read())

    try:
        await asyncio.to_thread(_download)
        return dest if dest.exists() and dest.stat().st_size > 0 else None
    except Exception as exc:
        print(f"[WARN] remote asset download failed for {case_id}: {exc}", flush=True)
        return None


def case_prompt(case: dict[str, Any]) -> str:
    return (
        case.get("prompt_en")
        or case.get("prompt_zh")
        or case.get("instructions_en")
        or case.get("instructions_zh")
        or case.get("script_en")
        or case.get("script_zh")
        or case.get("source_script_en")
        or ""
    )


def _find_result_url(value: Any) -> str:
    if isinstance(value, dict):
        for key in RESULT_KEYS:
            candidate = value.get(key)
            if isinstance(candidate, str) and candidate.startswith(("http://", "https://")):
                return candidate
        for nested in value.values():
            found = _find_result_url(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_result_url(nested)
            if found:
                return found
    return ""


def _extract_result(payload: Any) -> tuple[str, str, int]:
    if not isinstance(payload, dict):
        return "", "", 0
    status = str(payload.get("status") or "").lower()
    result_url = _find_result_url(payload)
    if result_url:
        return status or "completed", result_url, 200
    if payload.get("success") is False:
        return "failed", "", 200
    if status in TERMINAL_STATUS:
        return status, "", 200
    if status in PENDING_STATUS:
        return "pending", "", 200
    return "", "", 0


async def _enumerate_visible_enabled(page: Page) -> list[tuple[Any, str]]:
    buttons = page.locator("button:visible:not([disabled])")
    count = await buttons.count()
    snapshot: list[tuple[Any, str]] = []
    for index in range(count):
        button = buttons.nth(index)
        try:
            if await button.is_disabled():
                continue
            text = (await button.inner_text(timeout=1000)).strip()
        except Exception:
            continue
        text = re.sub(r"\s+", " ", text)
        if any(blocked in text for blocked in BLOCKED_BUTTON_TEXT_SUBSTRINGS):
            continue
        snapshot.append((button, text))
    return snapshot


async def _try_click(button: Any) -> bool:
    try:
        await button.scroll_into_view_if_needed(timeout=1500)
        await button.click(timeout=3000)
        return True
    except Exception:
        return False


async def click_action_button(page: Page) -> str | None:
    snapshot = await _enumerate_visible_enabled(page)
    for label in EXACT_GENERATE_LABELS:
        target = label.lower()
        for button, text in snapshot:
            if text.lower() == target and await _try_click(button):
                return text
    for pattern in GENERATE_BUTTON_PATTERNS:
        for button, text in snapshot:
            if pattern.search(text) and await _try_click(button):
                return text
    return None


async def _click_label_in(page: Page, candidates: list[str]) -> str:
    snapshot = await _enumerate_visible_enabled(page)
    for label in candidates:
        for button, text in snapshot:
            if label in text and await _try_click(button):
                return label
    return ""


async def click_model_thumbnail(page: Page, params: dict[str, Any]) -> bool:
    model_id = (params or {}).get("model_id")
    if not model_id:
        return False
    candidates = MODEL_THUMBNAIL_MAP.get(str(model_id), [str(model_id)])
    return bool(await _click_label_in(page, candidates))


async def prepare_for_action(page: Page, tool_type: str, case: dict[str, Any]) -> list[str]:
    params = case.get("params") or {}
    steps: list[str] = []
    if tool_type == "room_redesign":
        room_type = params.get("room_type")
        if room_type:
            label = await _click_label_in(page, ROOM_TYPE_LABELS.get(room_type, [room_type]))
            if label:
                steps.append(f"room_type:{label}")
                await page.wait_for_timeout(400)
        room_style = params.get("style")
        if room_style:
            label = await _click_label_in(page, ROOM_STYLE_LABELS.get(room_style, [room_style]))
            if label:
                steps.append(f"style:{label}")
                await page.wait_for_timeout(800)
    elif tool_type == "pattern_generate":
        pattern_style = params.get("style")
        if pattern_style:
            label = await _click_label_in(page, PATTERN_STYLE_LABELS.get(pattern_style, [pattern_style]))
            if label:
                steps.append(f"style:{label}")
                await page.wait_for_timeout(400)
        chip = await _click_label_in(page, ["使用此範例", "Use this example"])
        if chip:
            steps.append("preset:use-example")
            await page.wait_for_timeout(500)
    elif tool_type == "ai_avatar":
        avatar_id = params.get("avatar_id") or params.get("model_id")
        if avatar_id:
            label = await _click_label_in(page, MODEL_THUMBNAIL_MAP.get(str(avatar_id), [str(avatar_id)]))
            if label:
                steps.append(f"avatar:{label}")
                await page.wait_for_timeout(400)
    return steps


async def fill_text_inputs(page: Page, text: str, remote_asset: str | None) -> None:
    if text:
        areas = page.locator("textarea")
        if await areas.count() > 0:
            try:
                await areas.first.fill(text)
            except Exception:
                pass

    inputs = page.locator("input:not([type='hidden']):not([type='file'])")
    icount = await inputs.count()
    for i in range(icount):
        inp = inputs.nth(i)
        try:
            t = (await inp.get_attribute("type") or "text").lower()
            p = (await inp.get_attribute("placeholder") or "").lower()
            n = (await inp.get_attribute("name") or "").lower()
        except Exception:
            continue

        is_url_field = ("url" in p) or ("http" in p) or ("url" in n) or (t == "url")
        try:
            val = await inp.input_value()
        except Exception:
            val = ""

        if remote_asset and is_url_field and not val:
            try:
                await inp.fill(remote_asset)
                continue
            except Exception:
                pass


async def set_select_params(page: Page, params: dict[str, Any]) -> None:
    if not params:
        return
    selects = page.locator("select")
    scount = await selects.count()
    for i in range(scount):
        sel = selects.nth(i)
        name = (await sel.get_attribute("name") or "").lower()
        pid = (await sel.get_attribute("id") or "").lower()
        keyspace = f"{name} {pid}"
        for k, v in params.items():
            if k.lower() in keyspace:
                try:
                    await sel.select_option(str(v))
                except Exception:
                    pass


async def select_first_nonempty_visible_options(page: Page) -> list[str]:
    """Select a sane default for visible dropdowns that are still empty.

    The prompt-only MVP renders curated prompt dropdowns without semantic
    `name`/`id` attributes, so catalog param matching cannot target them.
    Selecting the first non-placeholder option unlocks those forms while still
    letting `set_select_params` win for named selects.
    """
    selected: list[str] = []
    selects = page.locator("select:visible:not([disabled])")
    select_count = await selects.count()
    for select_index in range(select_count):
        select = selects.nth(select_index)
        try:
            current_value = await select.input_value()
        except Exception:
            current_value = ""
        if current_value:
            continue
        options = select.locator("option")
        option_count = await options.count()
        for option_index in range(option_count):
            option = options.nth(option_index)
            try:
                value = await option.get_attribute("value")
                label = (await option.inner_text(timeout=500)).strip()
            except Exception:
                continue
            if not value:
                continue
            try:
                await select.select_option(value)
                selected.append(label or value)
                break
            except Exception:
                continue
    return selected


async def upload_if_possible(page: Page, asset_path: Path | None) -> bool:
    if not asset_path or not asset_path.exists():
        return False
    files = page.locator("input[type='file']")
    if await files.count() == 0:
        return False
    try:
        await files.first.set_input_files(str(asset_path))
        return True
    except Exception:
        return False


async def wait_for_upload_preview(page: Page, max_ms: int = 10000) -> bool:
    deadline = asyncio.get_event_loop().time() + (max_ms / 1000.0)
    while asyncio.get_event_loop().time() < deadline:
        try:
            count = await page.locator(
                "img[src^='data:image/'], img[src^='blob:'], img[src*='/uploads/']"
            ).count()
            if count > 0:
                return True
        except Exception:
            pass
        await page.wait_for_timeout(400)
    return False


async def fill_script_textarea(page: Page, text: str) -> bool:
    if not text:
        return False
    areas = page.locator("textarea:visible")
    area_count = await areas.count()
    if area_count == 0:
        return False
    try:
        for area_index in range(area_count):
            placeholder = (await areas.nth(area_index).get_attribute("placeholder") or "").lower()
            if any(keyword in placeholder for keyword in ["script", "腳本", "讀稿", "讀本", "稿"]):
                await areas.nth(area_index).fill(text)
                return True
        await areas.first.fill(text)
        return True
    except Exception:
        return False


async def login_and_save_state(browser) -> None:
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
    page = await ctx.new_page()
    await page.goto(f"{FRONTEND}/auth/login", wait_until="networkidle", timeout=60000)
    await page.fill("input[type='email']", EMAIL)
    await page.fill("input[type='password']", PASSWORD)
    await page.click("button[type='submit']")
    try:
        await page.wait_for_url(lambda u: "/auth/login" not in u, timeout=20000)
    except PlaywrightTimeoutError:
        pass
    await ctx.storage_state(path=str(STATE_FILE))
    await ctx.close()


async def wait_for_generation(hits: list[dict[str, Any]]) -> dict[str, Any]:
    now = asyncio.get_event_loop().time
    deadline = now() + MAX_WAIT_SEC
    no_api_deadline = now() + NO_API_OBSERVED_TIMEOUT_SEC
    last: dict[str, Any] = {"status": "", "url": "", "endpoint": "", "http_status": 0}
    while now() < deadline:
        for h in hits:
            status = h.get("status", "")
            if h.get("url") or status in TERMINAL_STATUS:
                return h
            if h.get("http_status") and h["http_status"] >= 400:
                last = h
            elif status == "pending":
                last = h
        if not hits and now() >= no_api_deadline:
            return {"status": "no_api_observed", "url": "", "endpoint": "", "http_status": 0}
        if hits and not any(is_generation_request_url(h.get("endpoint", "")) for h in hits) and now() >= no_api_deadline:
            return {"status": "no_generation_request", "url": "", "endpoint": hits[-1].get("endpoint", ""), "http_status": 0}
        await asyncio.sleep(POLL_INTERVAL_SEC)
    return last


async def run_one_case(ctx: BrowserContext, tool_type: str, route: str, case_id: str, case: dict[str, Any]) -> dict[str, Any]:
    outcome: dict[str, Any] = {
        "tool": tool_type,
        "case_id": case_id,
        "route": route,
        "uploaded": False,
        "clicked": "",
        "completion_status": "",
        "result_url": "",
        "wait_seconds": 0,
        "http_status": 0,
        "prepared_steps": [],
        "selected_dropdowns": [],
        "error": "",
    }

    page = await ctx.new_page()
    hits: list[dict[str, Any]] = []

    async def on_response(response: Response) -> None:
        url = response.url
        if not is_tool_action_url(url):
            return
        try:
            ct = (response.headers.get("content-type") or "").lower()
            if "json" not in ct:
                print(f"[RES] {response.status} {compact_url(url)} non-json content_type={ct or '-'}", flush=True)
                return
            payload = await asyncio.wait_for(response.json(), timeout=10)
        except Exception as exc:
            print(f"[RES] {response.status} {compact_url(url)} parse_error={type(exc).__name__}", flush=True)
            return
        status, result_url, http_ok = _extract_result(payload)
        print(
            f"[RES] {response.status} {compact_url(url)} status={status or '-'} result={'yes' if result_url else 'no'}",
            flush=True,
        )
        # Always record the bare HTTP status when something terminal-ish appeared
        # or there was an HTTP error.
        if status or result_url or response.status >= 400:
            hits.append({
                "endpoint": url,
                "http_status": response.status,
                "status": status,
                "url": result_url,
            })

    def on_request(request: Any) -> None:
        if not is_tool_action_url(request.url):
            return
        print(f"[REQ] {request.method} {compact_url(request.url)}", flush=True)
        hits.append({
            "endpoint": request.url,
            "http_status": 0,
            "status": "pending",
            "url": "",
        })

    def on_request_finished(request: Any) -> None:
        if is_tool_action_url(request.url):
            print(f"[DONE] {request.method} {compact_url(request.url)}", flush=True)

    def on_request_failed(request: Any) -> None:
        if not is_tool_action_url(request.url):
            return
        failure = getattr(request, "failure", "")
        if callable(failure):
            failure = failure()
        print(f"[FAILREQ] {request.method} {compact_url(request.url)} failure={failure or '-'}", flush=True)
        hits.append({
            "endpoint": request.url,
            "http_status": 0,
            "status": "failed",
            "url": "",
        })

    page.on("response", lambda r: asyncio.create_task(on_response(r)))
    page.on("request", on_request)
    page.on("requestfinished", on_request_finished)
    page.on("requestfailed", on_request_failed)

    try:
        await page.goto(f"{FRONTEND}{route}", wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(1500)

        apath = await materialize_case_asset(case, case_id)
        outcome["uploaded"] = await upload_if_possible(page, apath)
        if outcome["uploaded"]:
            await wait_for_upload_preview(page, max_ms=10000)
        outcome["prepared_steps"] = await prepare_for_action(page, tool_type, case)
        if tool_type == "try_on":
            await click_model_thumbnail(page, case.get("params", {}))
        await fill_text_inputs(page, case_prompt(case), case.get("remote_asset"))
        if tool_type == "ai_avatar":
            await fill_script_textarea(page, case_prompt(case))
        await set_select_params(page, case.get("params", {}))
        outcome["selected_dropdowns"] = await select_first_nonempty_visible_options(page)
        await page.wait_for_timeout(2500)

        hits.clear()
        outcome["clicked"] = await click_action_button(page) or ""
        if not outcome["clicked"]:
            outcome["error"] = "no enabled action button found"
            return outcome

        start = asyncio.get_event_loop().time()
        final = await wait_for_generation(hits)
        outcome["completion_status"] = final.get("status", "")
        outcome["result_url"] = final.get("url", "")
        outcome["http_status"] = final.get("http_status", 0)
        outcome["wait_seconds"] = round(asyncio.get_event_loop().time() - start, 1)
    except Exception as e:
        outcome["error"] = str(e)
    finally:
        try:
            await page.close()
        except Exception:
            pass

    return outcome


async def safe_run_case(ctx: BrowserContext, tool_type: str, route: str, case_id: str, case: dict[str, Any]) -> dict[str, Any]:
    try:
        return await asyncio.wait_for(
            run_one_case(ctx, tool_type, route, case_id, case),
            timeout=CASE_HARD_TIMEOUT,
        )
    except asyncio.TimeoutError:
        return {
            "tool": tool_type,
            "case_id": case_id,
            "route": route,
            "uploaded": False,
            "clicked": "",
            "completion_status": "hard_timeout",
            "result_url": "",
            "wait_seconds": CASE_HARD_TIMEOUT,
            "http_status": 0,
            "error": f"asyncio.wait_for hit {CASE_HARD_TIMEOUT}s",
        }


def is_pass(res: dict[str, Any]) -> bool:
    if res.get("result_url"):
        return True
    if res.get("completion_status") in {"completed", "succeeded", "success"}:
        return True
    return False


async def main() -> int:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))

    plan: list[tuple[str, str, str, dict[str, Any]]] = []
    for tool in data.get("tools", []):
        t = tool["tool_type"]
        r = tool["route"]
        for c in tool.get("cases", []):
            plan.append((t, r, c["case_id"], c))

    print(f"[INFO] frontend={FRONTEND} cases={len(plan)} max_wait={MAX_WAIT_SEC}s hard_timeout={CASE_HARD_TIMEOUT}s", flush=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        await login_and_save_state(browser)
        ctx = await browser.new_context(
            viewport={"width": 1440, "height": 900},
            storage_state=str(STATE_FILE),
        )

        results = []
        for t, r, cid, case in plan:
            print(f"[RUN] {t} :: {cid}", flush=True)
            res = await safe_run_case(ctx, t, r, cid, case)
            verdict = "PASS" if is_pass(res) else "FAIL"
            print(
                f"      [{verdict}] status={res.get('completion_status') or 'n/a'} "
                f"wait={res.get('wait_seconds')}s "
                f"http={res.get('http_status')} "
                f"clicked={res.get('clicked') or '-'}"
                + (f" err={res.get('error')}" if res.get("error") else ""),
                flush=True,
            )
            results.append(res)

        await ctx.close()
        await browser.close()

    by_tool: dict[str, dict[str, int]] = {}
    for r in results:
        d = by_tool.setdefault(r["tool"], {"pass": 0, "fail": 0})
        if is_pass(r):
            d["pass"] += 1
        else:
            d["fail"] += 1

    report = {
        "frontend": FRONTEND,
        "max_wait_sec": MAX_WAIT_SEC,
        "total": len(results),
        "passed": sum(1 for r in results if is_pass(r)),
        "failed": sum(1 for r in results if not is_pass(r)),
        "by_tool": by_tool,
        "results": results,
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=========== SUMMARY ===========", flush=True)
    for t, d in sorted(by_tool.items()):
        print(f"  {t:20s}  pass={d['pass']}  fail={d['fail']}", flush=True)
    print(f"  {'TOTAL':20s}  pass={report['passed']}  fail={report['failed']}", flush=True)
    print(f"\n[DONE] report={REPORT_FILE}", flush=True)

    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
