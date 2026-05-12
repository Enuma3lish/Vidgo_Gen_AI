#!/usr/bin/env python3
import asyncio
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from playwright.async_api import async_playwright, Page, Response, TimeoutError as PlaywrightTimeoutError

FRONTEND = os.getenv("VIDGO_FRONTEND_URL", "https://vidgo.co").rstrip("/")
EMAIL = os.getenv("ADMIN_ACCOUNT", "vidgo168@gmail.com")
PASSWORD = os.getenv("ADMIN_PASSWORD", "Vidgo96003146")
MAX_WAIT_SEC = int(os.getenv("VIDGO_MAX_WAIT_SEC", "420"))
POLL_INTERVAL_SEC = float(os.getenv("VIDGO_POLL_INTERVAL_SEC", "2"))
# How long to keep recording AFTER a result URL is observed, so the final UI
# state (the rendered output) is visible in the saved video.
POST_RESULT_PADDING_SEC = float(os.getenv("VIDGO_POST_PADDING_SEC", "3"))
# How long to wait when downloading the result media (image/video).
RESULT_DOWNLOAD_TIMEOUT_SEC = float(os.getenv("VIDGO_RESULT_DOWNLOAD_TIMEOUT_SEC", "120"))
# If we click the action button and ZERO matching API responses arrive within
# this window, give up and label the case "no_api_observed". Prevents the
# 7-min ceiling from burning when the click was a no-op (e.g. tab toggle).
NO_API_OBSERVED_TIMEOUT_SEC = float(os.getenv("VIDGO_NO_API_TIMEOUT_SEC", "30"))

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "TEST" / "Test_material" / "vidgo_tool_input_catalog.json"
ASSET_ROOT = ROOT / "TEST" / "Test_material"
OUT_ROOT = ROOT / "TEST" / "screen_recording"
TMP_ASSET_ROOT = OUT_ROOT / "tmp_remote_assets"
# Generated outputs (the actual produced image/video) are downloaded here so
# the saved recording is paired with a real artefact on disk.
RESULT_ROOT = OUT_ROOT / "result"
STATE_FILE = OUT_ROOT / ".auth_state.json"

DEFAULT_BUTTON_PATTERNS = [
    re.compile(r"try this example", re.I),
    re.compile(r"use example", re.I),
    re.compile(r"範例"),
    re.compile(r"示例"),
]
# EXACT button labels (whole-text match, case-insensitive). Checked FIRST so
# that the "確認生成" / "生成" / "去除背景" call-to-action wins over a tab header
# whose label merely *contains* "生成" (e.g. "設計生成（需訂閱）").
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
# Substring fallback patterns — only consulted if no exact label matched.
GENERATE_BUTTON_PATTERNS = [
    re.compile(r"remove background", re.I),
    re.compile(r"upscale", re.I),
    re.compile(r"translate", re.I),
    re.compile(r"dub\b", re.I),
    re.compile(r"dubbing", re.I),
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

# Cover every prefix the live tool views actually post to. Adding /interior/
# fixes the room-redesign blackouts; /effects/ catches imageTransform / hd-enhance;
# /uploads/ catches the product-scene async submit-then-poll pattern.
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

# Map catalog model_id values to the visible thumbnail label rendered by the
# try-on UI (六 thumbnails: 女模特 1-3, 男模特 1-3). Used to click the right
# model when params.model_id is provided.
MODEL_THUMBNAIL_MAP: dict[str, list[str]] = {
    "female-1": ["女模特 1", "Female 1"],
    "female-2": ["女模特 2", "Female 2"],
    "female-3": ["女模特 3", "Female 3"],
    "male-1":   ["男模特 1", "Male 1"],
    "male-2":   ["男模特 2", "Male 2"],
    "male-3":   ["男模特 3", "Male 3"],
}

# Room redesign: catalog params -> visible button label (zh).
ROOM_TYPE_LABELS: dict[str, list[str]] = {
    "living_room": ["客廳", "Living"],
    "bedroom":     ["臥室", "Bedroom"],
    "kitchen":     ["廚房", "Kitchen"],
    "bathroom":    ["浴室", "Bathroom"],
    "dining_room": ["餐廳", "Dining"],
    "study_room":  ["書房", "Study"],
    "balcony":     ["陽台", "Balcony"],
}
ROOM_STYLE_LABELS: dict[str, list[str]] = {
    "modern_minimalist":  ["現代極簡", "Modern Minimalist"],
    "scandinavian":       ["北歐風格", "Scandinavian"],
    "japanese":           ["日式禪風", "Japanese"],
    "industrial":         ["工業風", "Industrial"],
    "bohemian":           ["波西米亞", "Bohemian"],
    "mediterranean":      ["地中海風格", "Mediterranean"],
    "art_deco":           ["裝飾藝術", "Art Deco"],
    "mid_century_modern": ["中世紀現代", "Mid-Century"],
    "coastal":            ["海岸風格", "Coastal"],
    "farmhouse":          ["農舍風格", "Farmhouse"],
}
# Pattern generate: style param -> visible style chip label.
PATTERN_STYLE_LABELS: dict[str, list[str]] = {
    "floral":      ["花卉風格", "Floral"],
    "geometric":   ["幾何圖形", "Geometric"],
    "abstract":    ["抽象藝術", "Abstract"],
    "traditional": ["傳統紋樣", "Traditional"],
    "3d":          ["3D設計", "3D"],
    "interior":    ["室內設計", "Interior"],
    "mockup":      ["產品展示", "Mockup", "Product"],
}
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


def _ext_from_url(url: str, fallback: str = "png") -> str:
    """Return a filesystem-safe extension inferred from a URL path."""
    path = urllib.parse.urlparse(url).path
    name = path.rsplit("/", 1)[-1]
    if "." in name:
        ext = name.rsplit(".", 1)[-1].lower()
        if 1 <= len(ext) <= 5 and ext.isalnum():
            return ext
    return fallback


async def download_result(url: str, tool_type: str, case_slug: str) -> Path:
    """Download a generation result to RESULT_ROOT/<tool_type>/<case_slug>.<ext>.

    Runs the blocking urllib download in a thread so the playwright event
    loop (and the active video recording) keep running while we fetch.
    """
    if not url or not url.startswith(("http://", "https://")):
        raise ValueError(f"refusing to download non-http url: {url!r}")
    ext = _ext_from_url(url, fallback="png")
    out_dir = RESULT_ROOT / tool_type
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{case_slug}.{ext}"

    def _do_download() -> int:
        req = urllib.request.Request(
            url, headers={"User-Agent": "vidgo-screen-recorder/1.0"}
        )
        with urllib.request.urlopen(req, timeout=RESULT_DOWNLOAD_TIMEOUT_SEC) as resp:
            data = resp.read()
        dest.write_bytes(data)
        return len(data)

    await asyncio.to_thread(_do_download)
    return dest


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
        req = urllib.request.Request(remote_asset, headers={"User-Agent": "vidgo-screen-recorder/1.0"})
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


async def _enumerate_visible_enabled(page: Page) -> list[tuple[Any, str]]:
    """Return [(locator, normalized_text)] for every button that is BOTH
    visible and not disabled. Exposes a single snapshot so callers can run
    multiple matching strategies without re-scanning the DOM each time."""
    buttons = page.locator("button:visible:not([disabled])")
    n = await buttons.count()
    out: list[tuple[Any, str]] = []
    for i in range(n):
        btn = buttons.nth(i)
        try:
            if await btn.is_disabled():
                continue
            txt = (await btn.inner_text(timeout=1000)).strip()
        except Exception:
            continue
        # Collapse whitespace so multi-line labels like "確認生成\n\n生成圖片"
        # become "確認生成 生成圖片" for clean matching.
        norm = re.sub(r"\s+", " ", txt)
        if any(blocked in norm for blocked in BLOCKED_BUTTON_TEXT_SUBSTRINGS):
            continue
        out.append((btn, norm))
    return out


async def _try_click(btn) -> bool:
    try:
        await btn.scroll_into_view_if_needed(timeout=1500)
        await btn.click(timeout=3000)
        return True
    except Exception:
        return False


async def click_first_matching_button(page: Page, patterns: list[re.Pattern[str]]) -> bool:
    """Substring fallback only — `click_action_button` should be preferred."""
    snapshot = await _enumerate_visible_enabled(page)
    for pat in patterns:
        for btn, txt in snapshot:
            if pat.search(txt) and await _try_click(btn):
                return True
    return False


async def click_action_button(page: Page) -> tuple[bool, str]:
    """Pick the real call-to-action.

    Strategy 1 — EXACT-label match (case-insensitive whole-text), checked in
                 EXACT_GENERATE_LABELS order. This wins over tab headers like
                 "設計生成（需訂閱）" whose label *contains* "生成".
    Strategy 2 — substring fallback via GENERATE_BUTTON_PATTERNS.

    Returns (clicked, label_text) for diagnostics.
    """
    snapshot = await _enumerate_visible_enabled(page)

    # Strategy 1: exact label.
    for label in EXACT_GENERATE_LABELS:
        target = label.lower()
        for btn, txt in snapshot:
            if txt.lower() == target and await _try_click(btn):
                return True, txt

    # Strategy 2: substring patterns.
    for pat in GENERATE_BUTTON_PATTERNS:
        for btn, txt in snapshot:
            if pat.search(txt) and await _try_click(btn):
                return True, txt

    return False, ""


async def click_model_thumbnail(page: Page, params: dict[str, Any]) -> bool:
    """Click the model thumbnail matching params.model_id (try-on UI uses a
    button-grid, not <select>, for model selection)."""
    mid = (params or {}).get("model_id")
    if not mid:
        return False
    candidates = MODEL_THUMBNAIL_MAP.get(str(mid), [str(mid)])
    snapshot = await _enumerate_visible_enabled(page)
    for label in candidates:
        for btn, txt in snapshot:
            # Substring match — thumbnail buttons may have prefix chars like ">".
            if label in txt and await _try_click(btn):
                return True
    return False


async def _click_label_in(page: Page, candidates: list[str]) -> str:
    """Click the first visible+enabled button whose visible text *contains*
    any candidate label. Returns the label that matched or ''."""
    snapshot = await _enumerate_visible_enabled(page)
    for label in candidates:
        for btn, txt in snapshot:
            if label in txt and await _try_click(btn):
                return label
    return ""


async def prepare_for_action(page: Page, tool_type: str, case: dict[str, Any]) -> list[str]:
    """Tool-specific pre-clicks that satisfy the form prerequisites the page
    enforces, so the real action button (typically `:disabled` until form
    state is complete) becomes clickable.

    Returns the list of step descriptors that fired, for diagnostics.
    """
    steps: list[str] = []
    params = case.get("params") or {}

    if tool_type == "room_redesign":
        rt = params.get("room_type")
        if rt:
            label = await _click_label_in(page, ROOM_TYPE_LABELS.get(rt, [rt]))
            if label:
                steps.append(f"room_type:{label}")
                await page.wait_for_timeout(400)
        st = params.get("style")
        if st:
            label = await _click_label_in(page, ROOM_STYLE_LABELS.get(st, [st]))
            if label:
                steps.append(f"style:{label}")
                await page.wait_for_timeout(800)

    elif tool_type == "pattern_generate":
        st = params.get("style")
        if st:
            label = await _click_label_in(page, PATTERN_STYLE_LABELS.get(st, [st]))
            if label:
                steps.append(f"style:{label}")
                await page.wait_for_timeout(400)
        # Pattern page also has "使用此範例" preset chips that auto-fill the
        # prompt textarea. Clicking one is the cleanest way to get the action
        # button enabled even when the catalog prompt is custom.
        chip = await _click_label_in(page, ["使用此範例", "Use this example"])
        if chip:
            steps.append("preset:use-example")
            await page.wait_for_timeout(500)

    elif tool_type == "ai_avatar":
        # The avatar action button is :disabled until BOTH an avatar (image)
        # is selected AND a script is filled. We rely on fill_text_inputs to
        # populate the textarea later; here we just make sure an avatar
        # thumbnail is selected.
        avatar = params.get("avatar_id") or params.get("model_id")
        if avatar:
            label = await _click_label_in(page, MODEL_THUMBNAIL_MAP.get(str(avatar), [str(avatar)]))
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

        if text and not val and t in {"text", "search"} and ("prompt" in p or "script" in p or "描述" in p):
            try:
                await inp.fill(text)
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
    """Select first non-placeholder options for visible dropdowns still empty.

    Curated prompt selects intentionally bind to prompt IDs and often have no
    `name`/`id`, so catalog param matching cannot target them. This keeps the
    recorder compatible with the prompt-only workflow without hardcoding every
    view's local ref name.
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
    """Set a file on the FIRST input[type=file]. The Vue ImageUploader
    component reads the file via FileReader (async!) and emits the data URL
    via update:modelValue — that means the page's reactive state is NOT
    updated until the FileReader completes. Callers should `wait_for_timeout`
    for several seconds after this returns true, OR check that an <img>
    preview rendered, before clicking the action button."""
    if not asset_path or not asset_path.exists():
        return False
    # Wait briefly for the input to attach to the DOM (some pages render it
    # only after a tab is opened).
    files = page.locator("input[type='file']")
    if await files.count() == 0:
        return False
    try:
        # Use ALL file inputs — set on every one because some pages have
        # multiple (e.g. avatar uploader for body + a separate one for
        # reference voice clip).
        await files.first.set_input_files(str(asset_path))
        return True
    except Exception:
        return False


async def wait_for_upload_preview(page: Page, max_ms: int = 10000) -> bool:
    """Poll for an <img> whose `src` is a data URL or a real http URL
    (i.e. the upload preview rendered by ImageUploader after FileReader
    finishes). Returns True as soon as one appears."""
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
    """Fill the avatar script / dubbing translated-script textarea. Avatar
    page uses a plain <textarea> bound to v-model `script`."""
    if not text:
        return False
    areas = page.locator("textarea:visible")
    n = await areas.count()
    if n == 0:
        return False
    try:
        # Prefer a textarea whose placeholder hints at script/腳本/讀稿
        for i in range(n):
            try:
                ph = (await areas.nth(i).get_attribute("placeholder") or "").lower()
            except Exception:
                ph = ""
            if any(k in ph for k in ["script", "腳本", "讀稿", "讀本", "稿"]):
                await areas.nth(i).fill(text)
                return True
        # Fallback to the first visible textarea
        await areas.first.fill(text)
        return True
    except Exception:
        return False


async def login_and_save_state(browser, out_root: Path) -> None:
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
    await ctx.storage_state(path=str(out_root / ".auth_state.json"))
    await ctx.close()


PENDING_STATUS = {"processing", "pending", "queued", "running", "in_progress"}


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


def _extract_result(payload: Any) -> tuple[str, str, str]:
    """Return (status, result_url, message).

    `message` carries any backend-provided detail (e.g. provider failure
    reason) so the operator can see WHY a case failed without digging into
    server logs.

    `status="pending"` is returned for in-flight async polls (so the caller
    keeps waiting instead of returning success or failing fast)."""
    if not isinstance(payload, dict):
        return "", "", ""
    raw_status = str(payload.get("status") or "").lower()
    message = str(payload.get("message") or payload.get("error") or "")
    result_url = _find_result_url(payload)
    if result_url:
        return raw_status or "completed", result_url, message
    if payload.get("success") is False:
        return "failed", "", message
    if raw_status in TERMINAL_STATUS:
        return raw_status, "", message
    if raw_status in PENDING_STATUS:
        # Async submit-then-poll pattern (e.g. /api/v1/uploads/<id>): job is
        # still running, but presence of this response means the click DID
        # fire, so reset the no-API-observed timer.
        return "pending", "", message
    return "", "", message


async def wait_for_generation(page: Page, hits: list[dict[str, Any]]) -> dict[str, Any]:
    """Block until either:
      - any captured tool API response carries a result URL or terminal status, OR
      - NO_API_OBSERVED_TIMEOUT_SEC elapses with zero matching responses
        (fail fast when click was a no-op, e.g. a tab toggle), OR
      - MAX_WAIT_SEC ceiling.

    A response with status="pending" (e.g. /api/v1/uploads/<id> still
    processing) counts as "API observed" — we keep waiting up to MAX_WAIT_SEC
    rather than fail-fast.

    Returns immediately on success/failure — the caller is responsible for any
    post-result padding so the recording stays open while we download the file.
    """
    now = asyncio.get_event_loop().time
    deadline = now() + MAX_WAIT_SEC
    no_api_deadline = now() + NO_API_OBSERVED_TIMEOUT_SEC
    last_seen: dict[str, Any] = {"status": "", "url": "", "endpoint": "", "message": ""}
    while now() < deadline:
        if hits:
            for h in hits:
                status = h.get("status", "")
                if h.get("url") or status in TERMINAL_STATUS:
                    last_seen = h
                    if h.get("url") or status in {"failed", "error"}:
                        return last_seen
                elif status == "pending":
                    last_seen = h  # remember in-flight state
        elif now() >= no_api_deadline:
            # Click never produced a matching response — almost always a sign
            # the wrong button was clicked (tab toggle, preset selector, etc.)
            return {"status": "no_api_observed", "url": "", "endpoint": "", "message": ""}
        if hits and not any(is_generation_request_url(h.get("endpoint", "")) for h in hits) and now() >= no_api_deadline:
            return {"status": "no_generation_request", "url": "", "endpoint": hits[-1].get("endpoint", ""), "message": "upload observed, no generation request"}
        await asyncio.sleep(POLL_INTERVAL_SEC)
    # Hit the MAX_WAIT_SEC ceiling. If we have a pending hit, surface that.
    return last_seen


async def run_one_case(browser, tool_type: str, route: str, case_id: str, case: dict[str, Any], default_mode: bool = False) -> dict[str, Any]:
    tool_dir = OUT_ROOT / tool_type
    tool_dir.mkdir(parents=True, exist_ok=True)

    case_slug = slugify(case_id)
    context = await browser.new_context(
        viewport={"width": 1440, "height": 900},
        storage_state=str(STATE_FILE) if STATE_FILE.exists() else None,
        record_video_dir=str(tool_dir),
        record_video_size={"width": 1280, "height": 720},
    )
    page = await context.new_page()

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
        status, result_url, message = _extract_result(payload)
        print(
            f"[RES] {response.status} {compact_url(url)} status={status or '-'} result={'yes' if result_url else 'no'}",
            flush=True,
        )
        if status or result_url or message:
            hits.append({
                "endpoint": url,
                "http_status": response.status,
                "status": status,
                "url": result_url,
                "message": message,
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
            "message": "request_started",
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
            "message": str(failure or "request_failed"),
        })

    page.on("response", lambda r: asyncio.create_task(on_response(r)))
    page.on("request", on_request)
    page.on("requestfinished", on_request_finished)
    page.on("requestfailed", on_request_failed)

    outcome: dict[str, Any] = {
        "tool": tool_type,
        "case_id": case_id,
        "route": route,
        "default_mode": default_mode,
        "uploaded": False,
        "model_picked": False,
        "prepared_steps": [],
        "input_asset": "",
        "clicked_default": False,
        "clicked_generate": False,
        "action_button_label": "",
        "completion_status": "",
        "result_url": "",
        "result_path": "",
        "result_bytes": 0,
        "error_message": "",
        "wait_seconds": 0,
        "video_path": "",
        "screenshot_path": "",
        "error": "",
    }

    try:
        await page.goto(f"{FRONTEND}{route}", wait_until="domcontentloaded", timeout=90000)
        await page.wait_for_timeout(1500)

        if default_mode:
            # Tool views auto-load the first preset on mount; there is no
            # universal "Try this example" button. Just give it ~5s to settle,
            # screenshot the auto-loaded state, and end the recording. No
            # click → no API call → no 7-min timeout.
            await page.wait_for_timeout(5000)
            shot = tool_dir / f"{case_slug}.png"
            try:
                await page.screenshot(path=str(shot), full_page=True)
                outcome["screenshot_path"] = str(shot)
            except Exception:
                pass
            outcome["completion_status"] = "default_loaded"
        else:
            apath = await materialize_case_asset(case, case_id)
            outcome["input_asset"] = str(apath) if apath and apath.exists() else (case.get("source_asset") or case.get("remote_asset") or "")
            outcome["uploaded"] = await upload_if_possible(page, apath)
            # ImageUploader reads via FileReader (async) — wait until the
            # preview <img> renders, up to 10s. Skip silently for tools
            # without a file input.
            if outcome["uploaded"]:
                await wait_for_upload_preview(page, max_ms=10000)

            # Tool-specific pre-clicks (room_type/style/topic/avatar) that
            # satisfy the form prerequisites enforced by the page.
            outcome["prepared_steps"] = await prepare_for_action(page, tool_type, case)

            # Try-on uses a thumbnail button-grid for model_id (separate
            # from prepare_for_action because it doesn't need a tab switch).
            if tool_type == "try_on":
                outcome["model_picked"] = await click_model_thumbnail(
                    page, case.get("params", {})
                )

            # Fill text inputs / textareas.
            text = case_prompt(case) or case.get("script_zh") or case.get("script_en") \
                or case.get("translated_script_zh") or case.get("translated_script") or ""
            await fill_text_inputs(page, text, case.get("remote_asset"))
            if tool_type == "ai_avatar" and text:
                await fill_script_textarea(page, text)
            await set_select_params(page, case.get("params", {}))
            outcome["prepared_steps"].extend(await select_first_nonempty_visible_options(page))

            # Let everything settle (Vue reactivity + image preview).
            await page.wait_for_timeout(3000)

            hits.clear()
            clicked, label = await click_action_button(page)
            outcome["clicked_generate"] = clicked
            outcome["action_button_label"] = label

            if clicked:
                start_wait = asyncio.get_event_loop().time()
                final = await wait_for_generation(page, hits)
                outcome["completion_status"] = final.get("status", "")
                outcome["result_url"] = final.get("url", "")
                outcome["error_message"] = final.get("message", "")
                outcome["wait_seconds"] = round(asyncio.get_event_loop().time() - start_wait, 1)

                # Download the artefact BEFORE we stop recording so:
                #   1. screen_recording/<tool>/<case>.webm captures the click
                #      -> progress -> result-visible lifecycle, and
                #   2. screen_recording/result/<tool>/<case>.<ext> holds the
                #      actual output the user can open / share / diff.
                if outcome["result_url"]:
                    try:
                        dest = await download_result(outcome["result_url"], tool_type, case_slug)
                        outcome["result_path"] = str(dest)
                        outcome["result_bytes"] = dest.stat().st_size
                    except Exception as e:
                        outcome["error"] = outcome["error"] or f"download-failed: {e}"

                # Hold the recording open briefly so the final UI state is
                # visible at the end of the .webm.
                await page.wait_for_timeout(int(POST_RESULT_PADDING_SEC * 1000))
            else:
                outcome["completion_status"] = "no_action_button"
                await page.wait_for_timeout(2000)
    except Exception as e:
        outcome["error"] = str(e)
    finally:
        video = page.video
        await context.close()
        if video:
            try:
                src = Path(await video.path())
                dst = tool_dir / f"{case_slug}.webm"
                src.rename(dst)
                outcome["video_path"] = str(dst)
            except Exception as e:
                outcome["error"] = outcome["error"] or f"video-save-failed: {e}"

    return outcome


async def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    RESULT_ROOT.mkdir(parents=True, exist_ok=True)
    data = json.loads(CATALOG.read_text(encoding="utf-8"))

    plan: list[tuple[str, str, str, dict[str, Any], bool]] = []
    for tool in data.get("tools", []):
        t = tool["tool_type"]
        r = tool["route"]
        # Each tool view auto-selects a default demo example on mount; the
        # "default_example" pass just navigates and clicks the action button
        # without uploading or filling anything.
        plan.append((t, r, "default_example", {}, True))
        for c in tool.get("cases", []):
            plan.append((t, r, c["case_id"], c, False))

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        await login_and_save_state(browser, OUT_ROOT)

        results = []
        for t, r, cid, case, is_default in plan:
            print(f"[RUN] {t} :: {cid}", flush=True)
            res = await run_one_case(browser, t, r, cid, case, default_mode=is_default)
            result_label = "no"
            if res.get("result_path"):
                kb = res.get("result_bytes", 0) // 1024
                result_label = f"saved {kb} KB → {res['result_path']}"
            elif res.get("result_url"):
                result_label = "url-only (download failed)"
            elif res.get("screenshot_path"):
                result_label = f"screenshot {res['screenshot_path']}"
            extra = ""
            if res.get("action_button_label"):
                extra += f" btn={res['action_button_label'][:40]!r}"
            if res.get("prepared_steps"):
                extra += f" prep={res['prepared_steps']}"
            if res.get("model_picked"):
                extra += " model_picked=yes"
            if res.get("error_message"):
                extra += f" msg={res['error_message'][:80]!r}"
            print(
                f"      status={res.get('completion_status') or 'n/a'} "
                f"wait={res.get('wait_seconds')}s{extra} "
                f"result={result_label}",
                flush=True,
            )
            results.append(res)

        await browser.close()

    report = {
        "frontend": FRONTEND,
        "max_wait_sec": MAX_WAIT_SEC,
        "total_runs": len(results),
        "video_root": str(OUT_ROOT),
        "result_root": str(RESULT_ROOT),
        "results": results,
    }
    (OUT_ROOT / "run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for x in results if x.get("video_path"))
    completed = sum(1 for x in results if x.get("result_url"))
    downloaded = sum(1 for x in results if x.get("result_path"))
    print(
        f"[DONE] videos={ok}/{len(results)} "
        f"with_result_url={completed} downloaded={downloaded} "
        f"report={OUT_ROOT / 'run_report.json'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
