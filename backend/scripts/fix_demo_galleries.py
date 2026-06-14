#!/usr/bin/env python3
"""
One-shot Cloud Run Job that rebuilds demo galleries with consistent
prompt↔image pairs and populates the input library where it was empty.

Why this exists
===============
Audit on 2026-05-11 showed multiple demo galleries serve mismatched data:
- background_removal: 5/6 cards show wrong cutout for the labeled prompt
  (prompt "bubble milk tea" → bento.png, "scallion pancake" → bubbletea.png,
   etc.); inputs library returns 0 rows so users have nothing to pick.
- product_scene: 5/5 visible cards have the same prompt ("bubble milk tea")
  on the same input product-1.png — no variety.
- short_video: prompts mention specific subjects but inputs are random
  piapi_*.png artifacts.
- try_on / ai_avatar / pattern_generate: duplicate inputs across cards.

Strategy
========
For each affected tool we soft-delete every is_active SEED Material row,
then insert a small, hand-curated set of rows whose prompt text literally
describes the asset filename. This guarantees per-card consistency.
USER-source Materials are never touched.

Curated assets live in
  gs://vidgo-media-vidgo-ai/examples/{bg,fx,ps,room,tryon,vid,avatar}/...

Usage
=====
  # Dry run:
  python -m scripts.fix_demo_galleries --dry-run
  # Real run:
  python -m scripts.fix_demo_galleries

Cloud Run Job (production)
==========================
  gcloud run jobs deploy vidgo-fix-galleries \\
    --image=asia-east1-docker.pkg.dev/vidgo-ai/vidgo-images/vidgo-backend:latest \\
    --project=vidgo-ai --region=asia-east1 \\
    --vpc-connector=vidgo-connector --vpc-egress=all-traffic \\
    --service-account=vidgo-backend@vidgo-ai.iam.gserviceaccount.com \\
    --set-env-vars=GCS_BUCKET=vidgo-media-vidgo-ai \\
    --set-secrets=DATABASE_URL=DATABASE_URL:latest \\
    --command=python --args=-m,scripts.fix_demo_galleries
  gcloud run jobs execute vidgo-fix-galleries --project=vidgo-ai --region=asia-east1 --wait
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys

sys.path.insert(0, "/app")

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.material import Material, MaterialSource, MaterialStatus, ToolType

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("fix_galleries")

GCS = "https://storage.googleapis.com/vidgo-media-vidgo-ai/examples"


# ─────────────────────────────────────────────────────────────────────────────
# CURATED PAIRS — prompt text literally matches the asset filename
# ─────────────────────────────────────────────────────────────────────────────

BG_REMOVAL_PAIRS = [
    {
        "subject": "bubbletea",
        "topic": "drinks",
        "prompt_en": "Bubble milk tea cup with tapioca pearls — clean cutout for menu, e-commerce listing, or DM creative",
        "prompt_zh": "珍珠奶茶杯去背素材 — 適合菜單、商品上架圖、社群素材使用",
    },
    {
        "subject": "bento",
        "topic": "meals",
        "prompt_en": "Taiwanese bento box with rice and side dishes — clean cutout for delivery app menu and POS thumbnail",
        "prompt_zh": "台式便當去背素材 — 適合外送 App、POS 系統菜單縮圖使用",
    },
    {
        "subject": "fried-chicken",
        "topic": "snacks",
        "prompt_en": "Crispy fried chicken cutlet — clean cutout for night market e-commerce and social ads",
        "prompt_zh": "炸雞排去背素材 — 適合夜市電商和社群廣告使用",
    },
    {
        "subject": "cake",
        "topic": "desserts",
        "prompt_en": "Layered chiffon cake slice — clean cutout for bakery menu, LINE shop and IG campaign",
        "prompt_zh": "蛋糕切片去背素材 — 適合烘焙坊菜單、LINE 商店和 IG 活動使用",
    },
    {
        "subject": "soap",
        "topic": "packaging",
        "prompt_en": "Handmade soap bar packaging — clean cutout for Shopee, Shopify and brand product page",
        "prompt_zh": "手工皂包裝去背素材 — 適合蝦皮、Shopify 和品牌商品頁使用",
    },
]


PRODUCT_SCENE_PAIRS = [
    {
        "subject": "bubbletea",
        "topic": "studio",
        "prompt_en": "Bubble milk tea cup on a soft pastel studio backdrop — overhead lighting, café-menu hero shot",
        "prompt_zh": "珍珠奶茶杯放在柔和粉彩攝影棚背景 — 頂光打亮，咖啡菜單主視覺",
    },
    {
        "subject": "coffee",
        "topic": "studio",
        "prompt_en": "Hand-pour coffee on a dark walnut tabletop, warm window light, latte-art focus shot",
        "prompt_zh": "深胡桃木桌上的手沖咖啡，溫暖窗光，拉花特寫鏡頭",
    },
    {
        "subject": "bento",
        "topic": "lifestyle",
        "prompt_en": "Bento box on a linen runner, scattered chopsticks and small bowls, midday natural light",
        "prompt_zh": "亞麻桌巾上的便當，散落的筷子與小碟，正午自然光",
    },
    {
        "subject": "cake",
        "topic": "elegant",
        "prompt_en": "Cake slice on a marble cake stand, soft window light, dessert-menu cover composition",
        "prompt_zh": "大理石蛋糕架上的蛋糕切片，柔和窗光，甜點菜單封面構圖",
    },
    {
        "subject": "fried-chicken",
        "topic": "urban",
        "prompt_en": "Fried chicken cutlet on a kraft-paper liner, neon night-market vibe, takeaway-menu hero",
        "prompt_zh": "牛皮紙襯墊上的炸雞排，霓虹夜市氛圍，外帶菜單主視覺",
    },
    {
        "subject": "soap",
        "topic": "minimal",
        "prompt_en": "Handmade soap on a beige stoneware tray, minimal Scandinavian styling, brand catalog shot",
        "prompt_zh": "米色石器盤上的手工皂，極簡北歐風格，品牌目錄商品照",
    },
]


SHORT_VIDEO_PAIRS = [
    {
        "subject": "bubbletea",
        "topic": "product_showcase",
        "prompt_en": "Bubble tea cup rotating slowly with subtle steam — 8 s vertical for IG Reels and TikTok",
        "prompt_zh": "珍珠奶茶杯緩慢旋轉，淡淡蒸氣 — IG Reels 和 TikTok 直式 8 秒短片",
    },
    {
        "subject": "coffee",
        "topic": "promo",
        "prompt_en": "Pour-over coffee close-up with rising steam — 8 s vertical for café opening promo",
        "prompt_zh": "手沖咖啡近景，升起的蒸氣 — 咖啡店開幕活動 8 秒直式短片",
    },
    {
        "subject": "fried-chicken",
        "topic": "product_showcase",
        "prompt_en": "Fried chicken close-up with steam, golden crust glistens — 8 s vertical for night-market promo",
        "prompt_zh": "炸雞排近景特寫，金黃酥皮閃亮 — 夜市促銷 8 秒直式短片",
    },
    {
        "subject": "skincare",
        "topic": "brand_intro",
        "prompt_en": "Skincare bottle slow rotation on cream backdrop — 8 s vertical for spring sale launch",
        "prompt_zh": "保養品瓶身在奶白背景緩慢旋轉 — 春季新品上市 8 秒直式短片",
    },
    {
        "subject": "backpack",
        "topic": "tutorial",
        "prompt_en": "Outdoor backpack opening detail, soft daylight — 8 s vertical for outdoor brand reel",
        "prompt_zh": "戶外背包開合細節，柔和日光 — 戶外品牌 8 秒直式短片",
    },
]


ROOM_REDESIGN_PAIRS = [
    {"subject": "living-room",       "topic": "living_room", "prompt_en": "Modern Scandinavian living room redesign — neutral palette, light oak floor",                  "prompt_zh": "現代北歐風客廳改造 — 中性色調，淺橡木地板"},
    {"subject": "living-japanese",   "topic": "living_room", "prompt_en": "Japandi living room redesign — low furniture, soft beige tones",                              "prompt_zh": "Japandi 風客廳改造 — 低矮傢俱，柔和米色調"},
    {"subject": "bedroom",           "topic": "bedroom",     "prompt_en": "Cozy bedroom redesign — warm linen bedding, accent reading lamp",                             "prompt_zh": "溫馨臥室改造 — 暖色亞麻寢具，重點閱讀燈"},
    {"subject": "kitchen",           "topic": "kitchen",     "prompt_en": "Bright kitchen redesign — matte white cabinets, brass hardware, herb garden",                 "prompt_zh": "明亮廚房改造 — 霧白櫥櫃，黃銅五金，香草盆栽"},
    {"subject": "bathroom",          "topic": "bathroom",    "prompt_en": "Hotel-style bathroom redesign — micro-cement walls, walk-in rain shower, warm task lighting", "prompt_zh": "飯店風浴室改造 — 微水泥牆面，淋浴間，溫暖工作照明"},
]


# Avatar headshots are the input; we don't have curated result videos so we
# only use these as the input library — leaving result_video_url None so the
# row is `is_input_library:true` only.
AI_AVATAR_PAIRS = [
    {"subject": "yating",  "topic": "spokesperson", "prompt_en": "Female Taiwanese spokesperson — neutral background headshot, ready for narration",                "prompt_zh": "台灣女性發言人 — 中性背景大頭照，可直接配音"},
    {"subject": "yijun",   "topic": "spokesperson", "prompt_en": "Female brand presenter — neutral studio backdrop, ready for product introduction narration",     "prompt_zh": "女性品牌主持人 — 中性攝影棚背景，可直接做產品介紹"},
    {"subject": "guanyu",  "topic": "product_intro","prompt_en": "Male product introducer — neutral background headshot, ready for tutorial narration",            "prompt_zh": "男性產品介紹員 — 中性背景大頭照，可直接做教學配音"},
    {"subject": "zhiwei",  "topic": "customer_service", "prompt_en": "Male customer-service presenter — neutral background, ready for FAQ narration",               "prompt_zh": "男性客服主持人 — 中性背景，可直接做 FAQ 配音"},
]


TRY_ON_PAIRS = [
    {"subject": "demo-female-coat",    "topic": "outerwear", "prompt_en": "Female model wearing a coat — try-on result preview for outerwear category",  "prompt_zh": "女模穿著外套 — 外套類試穿結果預覽"},
    {"subject": "demo-female-sweater", "topic": "casual",    "prompt_en": "Female model wearing a sweater — try-on result preview for casual wear",     "prompt_zh": "女模穿著毛衣 — 休閒服飾試穿結果預覽"},
]


# Pattern Generate currently has 6 NULL-input rows. We don't have curated
# pattern assets in GCS yet, so we'll seed prompt-only entries that work
# as an effect_prompt catalog (the user uploads their own product to apply
# the pattern to). result fields stay None so the gallery doesn't display
# a misleading "before/after" — the page will fall back to its prompt
# library presentation.
PATTERN_GENERATE_EFFECTS = [
    {"topic": "floral",       "prompt_en": "Cherry-blossom seamless floral pattern, vintage washi paper texture", "prompt_zh": "櫻花無縫花卉圖案，復古和紙紋理"},
    {"topic": "geometric",    "prompt_en": "Art-deco geometric gold pattern on deep emerald, repeating ornament", "prompt_zh": "深翡翠底色上的 Art-deco 金色幾何圖案，重複裝飾"},
    {"topic": "abstract",     "prompt_en": "Abstract painterly brush-stroke pattern in muted sunset palette",     "prompt_zh": "抽象畫筆筆觸圖案，沉穩晚霞色調"},
    {"topic": "traditional",  "prompt_en": "Traditional Chinese cloud pattern in cinnabar red and ink black",     "prompt_zh": "中式傳統雲紋，朱紅與墨黑配色"},
    {"topic": "seamless",     "prompt_en": "Soft pastel polka-dot seamless pattern for product packaging mockup", "prompt_zh": "柔和粉彩波點無縫圖案，適合產品包裝模擬"},
    {"topic": "3d",           "prompt_en": "3D extruded geometric pattern in matte clay tones, modern packaging",  "prompt_zh": "3D 立體幾何圖案，霧面陶土色調，現代包裝風格"},
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

async def _soft_delete_seed_rows(session: AsyncSession, tool_type: ToolType, dry_run: bool) -> int:
    """Mark existing SEED Material rows for this tool inactive. USER rows are
    preserved so we never overwrite real customer-uploaded work."""
    stmt = (
        select(Material)
        .where(Material.tool_type == tool_type)
        .where(Material.is_active == True)
        .where(Material.source != MaterialSource.USER)
    )
    rows = (await session.execute(stmt)).scalars().all()
    logger.info("[%s] soft-deleting %d existing SEED rows", tool_type.value, len(rows))
    if not dry_run:
        for r in rows:
            r.is_active = False
    return len(rows)


def _build_row(
    *,
    tool_type: ToolType,
    topic: str,
    prompt_en: str,
    prompt_zh: str,
    input_image_url: str | None,
    result_image_url: str | None = None,
    result_video_url: str | None = None,
    input_video_url: str | None = None,
    is_input_library: bool = False,
) -> Material:
    """Build a freshly-seeded Material row with consistent fields."""
    params: dict = {}
    if is_input_library:
        params["is_input_library"] = True
    return Material(
        tool_type=tool_type,
        topic=topic,
        language="en",
        source=MaterialSource.SEED,
        status=MaterialStatus.APPROVED,
        is_active=True,
        prompt=prompt_en,
        prompt_en=prompt_en,
        prompt_zh=prompt_zh,
        input_image_url=input_image_url,
        input_video_url=input_video_url,
        result_image_url=result_image_url,
        result_video_url=result_video_url,
        result_watermarked_url=result_image_url,
        result_thumbnail_url=result_image_url or input_image_url,
        input_params=params,
    )


# ─────────────────────────────────────────────────────────────────────────────
# PER-TOOL FIX FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

async def fix_background_removal(session: AsyncSession, dry_run: bool) -> None:
    await _soft_delete_seed_rows(session, ToolType.BACKGROUND_REMOVAL, dry_run)
    inserted = 0
    for p in BG_REMOVAL_PAIRS:
        bg = f"{GCS}/bg/{p['subject']}.png"
        fx = f"{GCS}/fx/{p['subject']}.png"
        # 1) Result-pair row (shows up in /demo/presets)
        row = _build_row(
            tool_type=ToolType.BACKGROUND_REMOVAL,
            topic=p["topic"],
            prompt_en=p["prompt_en"],
            prompt_zh=p["prompt_zh"],
            input_image_url=bg,
            result_image_url=fx,
        )
        # 2) Input-library row (shows up in /demo/inputs)
        input_only = _build_row(
            tool_type=ToolType.BACKGROUND_REMOVAL,
            topic=p["topic"],
            prompt_en=p["prompt_en"],
            prompt_zh=p["prompt_zh"],
            input_image_url=bg,
            is_input_library=True,
        )
        if not dry_run:
            session.add_all([row, input_only])
        inserted += 2
    logger.info("[background_removal] inserted %d rows (5 preset pairs + 5 input-library)", inserted)


async def fix_product_scene(session: AsyncSession, dry_run: bool) -> None:
    await _soft_delete_seed_rows(session, ToolType.PRODUCT_SCENE, dry_run)
    inserted = 0
    for p in PRODUCT_SCENE_PAIRS:
        bg = f"{GCS}/bg/{p['subject']}.png"
        ps = f"{GCS}/ps/{p['subject']}.png"
        row = _build_row(
            tool_type=ToolType.PRODUCT_SCENE,
            topic=p["topic"],
            prompt_en=p["prompt_en"],
            prompt_zh=p["prompt_zh"],
            input_image_url=bg,
            result_image_url=ps,
        )
        input_only = _build_row(
            tool_type=ToolType.PRODUCT_SCENE,
            topic=p["topic"],
            prompt_en=p["prompt_en"],
            prompt_zh=p["prompt_zh"],
            input_image_url=bg,
            is_input_library=True,
        )
        if not dry_run:
            session.add_all([row, input_only])
        inserted += 2
    logger.info("[product_scene] inserted %d rows (6 preset pairs + 6 input-library)", inserted)


async def _dedupe_presets_by_input(
    session: AsyncSession, tool_type: ToolType, dry_run: bool
) -> None:
    """Soft-delete pre-existing SEED preset rows that share the same
    `input_image_url` so each card on the demo gallery shows a distinct input.
    Keeps the most-recent row per unique input. Leaves USER rows alone."""
    stmt = (
        select(Material)
        .where(Material.tool_type == tool_type)
        .where(Material.is_active == True)
        .where(Material.source != MaterialSource.USER)
        .where(Material.input_image_url.isnot(None))
        .order_by(Material.created_at.desc())
    )
    rows = (await session.execute(stmt)).scalars().all()
    seen: set[str] = set()
    deleted = 0
    for r in rows:
        # Strip query string so signed-URL refreshes don't masquerade as
        # different blobs.
        key = (r.input_image_url or "").split("?")[0]
        # Normalize is_input_library rows separately so the input-library
        # half stays paired with its preset-pair half.
        is_input_lib = bool((r.input_params or {}).get("is_input_library"))
        bucket = ("input_lib" if is_input_lib else "preset_pair") + "::" + key
        if bucket in seen:
            if not dry_run:
                r.is_active = False
            deleted += 1
            continue
        seen.add(bucket)
    logger.info(
        "[%s] dedupe by input_image_url: kept %d unique, soft-deleted %d duplicates",
        tool_type.value, len(seen), deleted,
    )


async def fix_short_video(session: AsyncSession, dry_run: bool) -> None:
    """short_video has runtime-generated outputs we want to keep, so this
    function only repairs the INPUT library — soft-deletes seed rows whose
    input_image_url is a piapi_*.png artifact and adds 5 curated inputs."""
    stmt = (
        select(Material)
        .where(Material.tool_type == ToolType.SHORT_VIDEO)
        .where(Material.is_active == True)
        .where(Material.source != MaterialSource.USER)
        .where(Material.input_params["is_input_library"].astext == "true")
    )
    rows = (await session.execute(stmt)).scalars().all()
    logger.info("[short_video] soft-deleting %d existing input-library rows", len(rows))
    if not dry_run:
        for r in rows:
            r.is_active = False

    inserted = 0
    for p in SHORT_VIDEO_PAIRS:
        vid_input = f"{GCS}/vid/{p['subject']}.png"
        input_only = _build_row(
            tool_type=ToolType.SHORT_VIDEO,
            topic=p["topic"],
            prompt_en=p["prompt_en"],
            prompt_zh=p["prompt_zh"],
            input_image_url=vid_input,
            is_input_library=True,
        )
        if not dry_run:
            session.add(input_only)
        inserted += 1
    logger.info("[short_video] inserted %d input-library rows", inserted)


async def fix_room_redesign(session: AsyncSession, dry_run: bool) -> None:
    """room_redesign keeps result-pair rows (we have curated rooms but no
    paired 'after' renders), so we only refresh the INPUT library."""
    stmt = (
        select(Material)
        .where(Material.tool_type == ToolType.ROOM_REDESIGN)
        .where(Material.is_active == True)
        .where(Material.source != MaterialSource.USER)
        .where(Material.input_params["is_input_library"].astext == "true")
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not dry_run:
        for r in rows:
            r.is_active = False
    logger.info("[room_redesign] soft-deleted %d input-library rows", len(rows))

    inserted = 0
    for p in ROOM_REDESIGN_PAIRS:
        room = f"{GCS}/room/{p['subject']}.png"
        input_only = _build_row(
            tool_type=ToolType.ROOM_REDESIGN,
            topic=p["topic"],
            prompt_en=p["prompt_en"],
            prompt_zh=p["prompt_zh"],
            input_image_url=room,
            is_input_library=True,
        )
        if not dry_run:
            session.add(input_only)
        inserted += 1
    logger.info("[room_redesign] inserted %d input-library rows", inserted)


async def fix_ai_avatar(session: AsyncSession, dry_run: bool) -> None:
    """Avatar headshots → input library. We don't have curated result-videos
    paired with these so we refresh inputs only (still removes the
    duplicate-input bug)."""
    stmt = (
        select(Material)
        .where(Material.tool_type == ToolType.AI_AVATAR)
        .where(Material.is_active == True)
        .where(Material.source != MaterialSource.USER)
        .where(Material.input_params["is_input_library"].astext == "true")
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not dry_run:
        for r in rows:
            r.is_active = False
    logger.info("[ai_avatar] soft-deleted %d input-library rows", len(rows))

    inserted = 0
    for p in AI_AVATAR_PAIRS:
        head = f"{GCS}/avatar/{p['subject']}.png"
        input_only = _build_row(
            tool_type=ToolType.AI_AVATAR,
            topic=p["topic"],
            prompt_en=p["prompt_en"],
            prompt_zh=p["prompt_zh"],
            input_image_url=head,
            is_input_library=True,
        )
        if not dry_run:
            session.add(input_only)
        inserted += 1
    logger.info("[ai_avatar] inserted %d input-library rows", inserted)


async def fix_try_on(session: AsyncSession, dry_run: bool) -> None:
    """Try-on input library refresh — we only have 2 curated pairs."""
    stmt = (
        select(Material)
        .where(Material.tool_type == ToolType.TRY_ON)
        .where(Material.is_active == True)
        .where(Material.source != MaterialSource.USER)
        .where(Material.input_params["is_input_library"].astext == "true")
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not dry_run:
        for r in rows:
            r.is_active = False
    logger.info("[try_on] soft-deleted %d input-library rows", len(rows))

    inserted = 0
    for p in TRY_ON_PAIRS:
        ron = f"{GCS}/tryon/{p['subject']}.png"
        input_only = _build_row(
            tool_type=ToolType.TRY_ON,
            topic=p["topic"],
            prompt_en=p["prompt_en"],
            prompt_zh=p["prompt_zh"],
            input_image_url=ron,
            is_input_library=True,
        )
        if not dry_run:
            session.add(input_only)
        inserted += 1
    logger.info("[try_on] inserted %d input-library rows", inserted)


async def fix_pattern_generate(session: AsyncSession, dry_run: bool) -> None:
    """Pattern Generate — soft-delete the NULL-input seed rows that produced
    duplicate "NONE" entries and add prompt-only effect catalog rows. The
    page composes the user's uploaded product with these effect prompts at
    runtime; result_image_url stays NULL on purpose."""
    stmt = (
        select(Material)
        .where(Material.tool_type == ToolType.PATTERN_GENERATE)
        .where(Material.is_active == True)
        .where(Material.source != MaterialSource.USER)
    )
    rows = (await session.execute(stmt)).scalars().all()
    if not dry_run:
        for r in rows:
            r.is_active = False
    logger.info("[pattern_generate] soft-deleted %d existing seed rows", len(rows))

    inserted = 0
    for p in PATTERN_GENERATE_EFFECTS:
        # Effect-catalog row (input/result both NULL — the page picks effect
        # prompts from these and applies them to the user's own upload).
        row = Material(
            tool_type=ToolType.PATTERN_GENERATE,
            topic=p["topic"],
            language="en",
            source=MaterialSource.SEED,
            status=MaterialStatus.APPROVED,
            is_active=True,
            prompt=p["prompt_en"],
            prompt_en=p["prompt_en"],
            prompt_zh=p["prompt_zh"],
            effect_prompt=p["prompt_en"],
            effect_prompt_zh=p["prompt_zh"],
            input_params={"is_effect_catalog": True},
        )
        if not dry_run:
            session.add(row)
        inserted += 1
    logger.info("[pattern_generate] inserted %d effect-catalog rows", inserted)


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show planned changes without writing.")
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL"):
        logger.error("DATABASE_URL not set")
        return 2

    async with AsyncSessionLocal() as session:
        await fix_background_removal(session, args.dry_run)
        await fix_product_scene(session, args.dry_run)
        await fix_short_video(session, args.dry_run)
        await fix_room_redesign(session, args.dry_run)
        await fix_ai_avatar(session, args.dry_run)
        await fix_try_on(session, args.dry_run)
        await fix_pattern_generate(session, args.dry_run)
        # Dedupe preset cards on tools where my earlier fix only touched
        # the input-library half, leaving result-pair seed rows duplicated
        # by input image (e.g. female-3.png appearing in 2 avatar presets,
        # garment-blouse.png appearing in 2 try-on presets).
        for tt in (ToolType.TRY_ON, ToolType.AI_AVATAR, ToolType.SHORT_VIDEO):
            await _dedupe_presets_by_input(session, tt, args.dry_run)
        if not args.dry_run:
            await session.commit()
            logger.info("Committed all changes.")
        else:
            logger.info("DRY RUN — no changes written.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
