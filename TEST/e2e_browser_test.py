#!/usr/bin/env python3
"""
VidGo AI — Playwright E2E Browser Test Suite
Based on TEST/mock-user-behavior.md scenarios.

Runs a headless Chromium browser against the live GCP deployment.
Tests UI rendering, navigation, user flows, subscription gates, and generation.

Usage:
    python3.13 TEST/e2e_browser_test.py
"""
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from typing import Optional

from playwright.async_api import async_playwright, Page, Browser, expect

# ─── Configuration ───────────────────────────────────────────────────────────
FRONTEND = "https://vidgo-frontend-38714015566.asia-east1.run.app"
BACKEND  = "https://vidgo-backend-38714015566.asia-east1.run.app"
USER_EMAIL = "qaz0978005418@gmail.com"
USER_PASS  = "qaz129946858"
TIMEOUT = 15_000   # ms for page loads
NAV_TIMEOUT = 10_000

# ─── Results tracking ────────────────────────────────────────────────────────
@dataclass
class TestResult:
    name: str
    passed: bool
    message: str = ""
    duration: float = 0.0

results: list[TestResult] = []

def record(name: str, passed: bool, msg: str = "", dur: float = 0.0):
    results.append(TestResult(name, passed, msg, dur))
    icon = "✅" if passed else "❌"
    print(f"  {icon} {name}" + (f" — {msg}" if msg else ""))


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1: Visitor / Guest Scenarios (mock-user-behavior.md §2)
# ═══════════════════════════════════════════════════════════════════════════════

async def test_visitor_landing_page(page: Page):
    """§2.1 — First-Time Visitor Exploration: Landing page loads, hero visible."""
    t0 = time.time()
    await page.goto(FRONTEND, wait_until="networkidle", timeout=TIMEOUT)
    # SPA should render content
    body_text = await page.text_content("body")
    has_content = "VidGo" in (body_text or "")
    record("Landing page loads & contains VidGo", has_content, dur=time.time()-t0)

    # Hero section visible
    hero = page.locator("section").first
    hero_visible = await hero.is_visible() if await hero.count() > 0 else False
    record("Hero section visible", hero_visible)


async def test_visitor_navigation(page: Page):
    """§2.1 — Navigation: Pricing, Gallery, Tools pages reachable."""
    for label, path in [("Pricing", "/pricing"), ("Gallery", "/gallery")]:
        await page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=TIMEOUT)
        title = await page.title()
        body = await page.text_content("body") or ""
        ok = len(body) > 200
        record(f"Navigate to {label} ({path})", ok, f"body={len(body)} chars")


async def test_visitor_tool_pages(page: Page):
    """§2.2 — Anonymous Tool Testing: All tool pages render without error."""
    tool_paths = [
        ("/tools/background-removal", "Background Removal"),
        ("/tools/product-scene", "Product Scene"),
        ("/tools/try-on", "Try On"),
        ("/tools/short-video", "Short Video"),
        ("/tools/avatar", "Avatar"),
        ("/tools/effects", "Effects"),
        ("/tools/room-redesign", "Room Redesign"),
        ("/tools/pattern-generate", "Pattern Generate"),
        ("/tools/text-to-video", "Text to Video"),
        ("/tools/upscale", "Upscale"),
        ("/tools/image-transform", "Image Transform"),
        ("/tools/video-transform", "Video Transform"),
    ]
    for path, name in tool_paths:
        t0 = time.time()
        try:
            await page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=TIMEOUT)
            # Check page rendered (not blank)
            body = await page.text_content("body") or ""
            # Check no raw i18n keys visible
            has_raw_keys = "lp.allTools." in body or "common.generate" in body
            has_content = len(body) > 100 and not has_raw_keys
            record(f"Tool page: {name}", has_content,
                   f"raw_i18n={has_raw_keys}" if has_raw_keys else "",
                   dur=time.time()-t0)
        except Exception as e:
            record(f"Tool page: {name}", False, str(e)[:80])


async def test_visitor_no_raw_json(page: Page):
    """Verify no raw JSON objects (like credits) are displayed in the UI."""
    await page.goto(FRONTEND, wait_until="networkidle", timeout=TIMEOUT)
    body = await page.text_content("body") or ""
    has_raw_json = "subscription_credits" in body or "remaining_credits" in body
    record("No raw credits JSON on page", not has_raw_json,
           "FOUND raw JSON in body" if has_raw_json else "")


async def test_visitor_i18n_translations(page: Page):
    """§6.1 — Verify all tool names on landing page are translated (no raw keys)."""
    await page.goto(FRONTEND, wait_until="networkidle", timeout=TIMEOUT)
    body = await page.text_content("body") or ""
    raw_keys = [k for k in [
        "lp.allTools.textToVideo", "lp.allTools.hdUpscale",
        "lp.allTools.imageTransform", "lp.allTools.videoTransform",
        "lp.allTools.patternGenerate",
    ] if k in body]
    record("All tool names translated (no raw i18n keys)", len(raw_keys) == 0,
           f"Missing: {raw_keys}" if raw_keys else "All translated")


async def test_guest_demo_blocked(page: Page):
    """§2.3 — Guest: download/upload gates enforced."""
    await page.goto(f"{FRONTEND}/tools/background-removal", wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(2000)  # let Vue render

    # Check for subscribe/upgrade CTA
    body = await page.text_content("body") or ""
    has_subscribe_cta = any(w in body for w in ["訂閱", "Subscribe", "升級", "Upgrade", "立即訂閱"])
    record("Guest sees subscribe/upgrade CTA", has_subscribe_cta)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2: Auth Flow (mock-user-behavior.md §3.1)
# ═══════════════════════════════════════════════════════════════════════════════

async def test_auth_login_page(page: Page):
    """§3.1 — Login page renders correctly."""
    await page.goto(f"{FRONTEND}/auth/login", wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(1000)

    # Check for email and password inputs
    email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="mail"]')
    pass_input = page.locator('input[type="password"]')

    has_email = await email_input.count() > 0
    has_pass = await pass_input.count() > 0
    record("Login page has email input", has_email)
    record("Login page has password input", has_pass)


async def test_auth_register_page(page: Page):
    """Registration page renders."""
    await page.goto(f"{FRONTEND}/auth/register", wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(1000)
    body = await page.text_content("body") or ""
    has_register = any(w in body for w in ["註冊", "Register", "Sign Up", "建立帳號", "Create"])
    record("Register page renders", has_register)


async def login_user(page: Page) -> bool:
    """Helper: log in the test user and return success."""
    await page.goto(f"{FRONTEND}/auth/login", wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(1500)

    # Fill email
    email_input = page.locator('input[type="email"], input[name="email"], input[placeholder*="mail"]').first
    await email_input.fill(USER_EMAIL)

    # Fill password
    pass_input = page.locator('input[type="password"]').first
    await pass_input.fill(USER_PASS)

    # Click submit
    submit = page.locator('button[type="submit"], button:has-text("登入"), button:has-text("Login"), button:has-text("Sign In")').first
    await submit.click()

    # Wait for redirect (dashboard or home)
    try:
        await page.wait_for_url(lambda url: "/auth/login" not in url, timeout=10_000)
        return True
    except Exception:
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3: Paid Subscriber Scenarios (mock-user-behavior.md §4)
# ═══════════════════════════════════════════════════════════════════════════════

async def test_subscriber_login(page: Page) -> bool:
    """§4.1 — Subscriber logs in successfully."""
    ok = await login_user(page)
    record("Subscriber login successful", ok)
    return ok


async def test_subscriber_credits_display(page: Page):
    """§4.1 — Credits shown as number (not raw JSON) after login."""
    await page.wait_for_timeout(2000)
    body = await page.text_content("body") or ""

    # Should NOT see raw JSON
    has_raw = "subscription_credits" in body
    record("Credits display: no raw JSON after login", not has_raw,
           "Raw JSON visible!" if has_raw else "Clean display")

    # Should see a number with '點數' or 'credits'
    has_credits_label = "點數" in body or "credits" in body.lower()
    record("Credits label visible", has_credits_label)


async def test_subscriber_dashboard(page: Page):
    """§4.1 — Dashboard accessible for subscribers."""
    await page.goto(f"{FRONTEND}/dashboard", wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(2000)
    body = await page.text_content("body") or ""
    # Should not redirect to login
    is_dashboard = "dashboard" in page.url.lower() or "控制" in body or "Dashboard" in body or "我的" in body
    record("Dashboard accessible", is_dashboard)


async def test_subscriber_no_preview_mode(page: Page):
    """Subscriber should NOT see preview mode banner on tool pages."""
    for path, name in [
        ("/tools/try-on", "Try On"),
        ("/tools/background-removal", "BG Removal"),
        ("/tools/effects", "Effects"),
    ]:
        await page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=TIMEOUT)
        await page.wait_for_timeout(2000)
        body = await page.text_content("body") or ""
        has_preview = "預覽模式" in body and "立即訂閱" in body
        record(f"Subscriber: no preview mode on {name}", not has_preview,
               "Preview mode banner visible!" if has_preview else "")


async def test_subscriber_upload_visible(page: Page):
    """§4.1 — Subscriber can see upload interface on tool pages."""
    await page.goto(f"{FRONTEND}/tools/background-removal", wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(2000)

    # Look for upload elements
    upload_area = page.locator('input[type="file"], [class*="upload"], [class*="dropzone"], button:has-text("上傳"), button:has-text("Upload")')
    has_upload = await upload_area.count() > 0
    record("Subscriber: upload UI visible on BG Removal", has_upload)


async def test_subscriber_generate_button(page: Page):
    """§4.5 — Generate button exists and is NOT labeled 'Preview Mode' for subscribers."""
    await page.goto(f"{FRONTEND}/tools/background-removal", wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(2000)

    # Find generate button
    gen_btn = page.locator('button:has-text("生成"), button:has-text("Generate"), button:has-text("去背"), button:has-text("Remove")')
    if await gen_btn.count() > 0:
        btn = gen_btn.first
        btn_text = await btn.text_content() or ""
        # Button may be disabled until an image is selected — that's OK.
        # What matters: it should NOT say "Preview Mode" / "預覽模式" for subscribers.
        is_preview = "預覽模式" in btn_text or "Preview Mode" in btn_text
        record("Generate button not in preview mode for subscriber", not is_preview,
               f"text='{btn_text.strip()[:40]}'")
    else:
        record("Generate button found", False, "No generate button found")


async def test_subscriber_pricing_page(page: Page):
    """§4.4 — Pricing page shows plans correctly."""
    await page.goto(f"{FRONTEND}/pricing", wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(2000)
    body = await page.text_content("body") or ""

    has_plans = any(w in body for w in ["Starter", "Pro", "入門", "專業", "進階"])
    has_price = "NT$" in body or "TWD" in body or "$" in body or "月" in body
    record("Pricing page shows plans", has_plans)
    record("Pricing page shows prices", has_price)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4: Gallery Tests (mock-user-behavior.md §6)
# ═══════════════════════════════════════════════════════════════════════════════

async def test_gallery_loads(page: Page):
    """§6.1 — Gallery page loads with content."""
    await page.goto(f"{FRONTEND}/gallery", wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(2000)
    body = await page.text_content("body") or ""
    has_gallery = len(body) > 200
    record("Gallery page loads", has_gallery)


async def test_gallery_tool_cards(page: Page):
    """§6.1 — Gallery shows tool categories."""
    await page.goto(f"{FRONTEND}/gallery", wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(2000)

    # Check for tool category tabs/filters
    body = await page.text_content("body") or ""
    tools_present = sum(1 for t in ["去背", "場景", "試穿", "影片", "效果", "Background", "Scene", "Try", "Video", "Effect"]
                        if t in body)
    record("Gallery shows tool categories", tools_present >= 3, f"{tools_present} tool labels found")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5: Edge Cases (mock-user-behavior.md §8)
# ═══════════════════════════════════════════════════════════════════════════════

async def test_404_page(page: Page):
    """§8.1 — Invalid route handled gracefully."""
    await page.goto(f"{FRONTEND}/nonexistent-page-xyz", wait_until="networkidle", timeout=TIMEOUT)
    # SPA should show something (not crash)
    body = await page.text_content("body") or ""
    not_blank = len(body) > 50
    record("404 page handled gracefully", not_blank)


async def test_language_switch(page: Page):
    """§10.3 — Language switching works."""
    await page.goto(FRONTEND, wait_until="networkidle", timeout=TIMEOUT)
    await page.wait_for_timeout(2000)

    # Look for language selector
    lang_btn = page.locator('[class*="language"], [class*="locale"], button:has-text("繁體中文"), button:has-text("EN"), [class*="lang"]')
    has_lang = await lang_btn.count() > 0
    record("Language selector visible", has_lang)


async def test_mobile_responsive(page: Page, browser: Browser):
    """§7.1 — Mobile viewport renders correctly."""
    mobile_page = await browser.new_page(viewport={"width": 375, "height": 812})
    try:
        await mobile_page.goto(FRONTEND, wait_until="networkidle", timeout=TIMEOUT)
        await mobile_page.wait_for_timeout(2000)
        body = await mobile_page.text_content("body") or ""
        has_content = "VidGo" in body and len(body) > 200
        record("Mobile viewport renders", has_content)

        # Check hamburger menu exists
        hamburger = mobile_page.locator('[class*="menu"], [class*="hamburger"], button[aria-label*="menu"], svg')
        has_menu = await hamburger.count() > 0
        record("Mobile has menu/hamburger", has_menu)
    finally:
        await mobile_page.close()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6: Performance (mock-user-behavior.md §9)
# ═══════════════════════════════════════════════════════════════════════════════

async def test_page_load_performance(page: Page):
    """§9.3 — Key pages load within acceptable time."""
    pages_to_test = [
        ("/", "Landing"),
        ("/pricing", "Pricing"),
        ("/gallery", "Gallery"),
        ("/tools/background-removal", "BG Removal"),
    ]
    for path, name in pages_to_test:
        t0 = time.time()
        await page.goto(f"{FRONTEND}{path}", wait_until="networkidle", timeout=TIMEOUT)
        dur = time.time() - t0
        ok = dur < 5.0  # 5 second threshold
        record(f"Load time: {name}", ok, f"{dur:.2f}s")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    print("=" * 70)
    print("  VidGo AI — E2E Browser Test Suite (Playwright)")
    print(f"  Frontend: {FRONTEND}")
    print(f"  Backend:  {BACKEND}")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="zh-TW",
        )
        page = await context.new_page()

        # ── Section 1: Visitor / Guest ──
        print("\n📋 Section 1: Visitor / Guest Scenarios")
        print("-" * 50)
        await test_visitor_landing_page(page)
        await test_visitor_navigation(page)
        await test_visitor_tool_pages(page)
        await test_visitor_no_raw_json(page)
        await test_visitor_i18n_translations(page)
        await test_guest_demo_blocked(page)

        # ── Section 2: Auth Flow ──
        print("\n📋 Section 2: Authentication")
        print("-" * 50)
        await test_auth_login_page(page)
        await test_auth_register_page(page)

        # ── Section 3: Subscriber ──
        print("\n📋 Section 3: Paid Subscriber Scenarios")
        print("-" * 50)
        logged_in = await test_subscriber_login(page)
        if logged_in:
            await test_subscriber_credits_display(page)
            await test_subscriber_dashboard(page)
            await test_subscriber_no_preview_mode(page)
            await test_subscriber_upload_visible(page)
            await test_subscriber_generate_button(page)
            await test_subscriber_pricing_page(page)
        else:
            record("SKIP subscriber tests", False, "Login failed")

        # ── Section 4: Gallery ──
        print("\n📋 Section 4: Gallery Tests")
        print("-" * 50)
        await test_gallery_loads(page)
        await test_gallery_tool_cards(page)

        # ── Section 5: Edge Cases ──
        print("\n📋 Section 5: Edge Cases")
        print("-" * 50)
        await test_404_page(page)
        await test_language_switch(page)
        await test_mobile_responsive(page, browser)

        # ── Section 6: Performance ──
        print("\n📋 Section 6: Performance")
        print("-" * 50)
        await test_page_load_performance(page)

        await browser.close()

    # ── Summary ──
    print("\n" + "=" * 70)
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)
    print(f"  RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 70)

    if failed > 0:
        print("\n❌ FAILED TESTS:")
        for r in results:
            if not r.passed:
                print(f"  • {r.name}: {r.message}")

    print(f"\n{'✅ ALL TESTS PASSED' if failed == 0 else f'⚠️  {failed} TESTS FAILED'}")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
