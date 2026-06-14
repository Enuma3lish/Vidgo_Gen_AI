#!/usr/bin/env python3
"""Seed minimal approved materials for readiness coverage.

This utility is intentionally conservative: it only inserts missing active Material
rows and reuses already generated successful media URLs from UserUpload history.
It does not call external AI providers.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import func, select

from app.config.topic_registry import (
    get_landing_topics,
    get_topic_info,
    get_topics_for_tool,
)
from app.core.database import AsyncSessionLocal
from app.models.material import Material, MaterialSource, MaterialStatus, ToolType
from app.models.user_upload import UploadStatus, UserUpload

IMAGE_TOOLS = {
    ToolType.BACKGROUND_REMOVAL,
    ToolType.TRY_ON,
    ToolType.PATTERN_GENERATE,
}
VIDEO_TOOLS = {
    ToolType.SHORT_VIDEO,
    ToolType.AI_AVATAR,
}

CORE_TARGETS: dict[ToolType, list[str]] = {
    ToolType.BACKGROUND_REMOVAL: ["equipment", "signage", "ingredients"],
    ToolType.TRY_ON: ["casual", "formal", "sportswear", "outerwear", "accessories", "dresses"],
    ToolType.SHORT_VIDEO: ["tutorial", "promo"],
    ToolType.AI_AVATAR: ["spokesperson", "product_intro", "customer_service", "social_media"],
    ToolType.PATTERN_GENERATE: ["3d", "interior", "mockup"],
}

LANDING_VIDEO_PER_TOPIC = 6
LANDING_AVATAR_PER_TOPIC = 12


def _topic_zh(tool_type: ToolType, topic: str) -> str:
    info = get_topic_info(tool_type.value, topic)
    return info["name_zh"] if info else topic


def _landing_topic_zh(topic: str) -> str:
    for item in get_landing_topics():
        if item["id"] == topic:
            return item["name_zh"]
    return topic


async def _active_count(session, tool_type: ToolType, topic: str) -> int:
    result = await session.execute(
        select(func.count(Material.id))
        .where(Material.tool_type == tool_type)
        .where(Material.topic == topic)
        .where(Material.is_active == True)
    )
    return int(result.scalar() or 0)


async def _latest_upload_url(session, tool_type: ToolType) -> str:
    url_column = UserUpload.result_video_url if tool_type in VIDEO_TOOLS else UserUpload.result_url
    result = await session.execute(
        select(url_column)
        .where(UserUpload.tool_type == tool_type.value)
        .where(UserUpload.status == UploadStatus.COMPLETED)
        .where(url_column.is_not(None))
        .order_by(UserUpload.completed_at.desc().nullslast(), UserUpload.updated_at.desc().nullslast())
        .limit(1)
    )
    url = result.scalar_one_or_none()
    if url:
        return url

    material_url_column = Material.result_video_url if tool_type in VIDEO_TOOLS else Material.result_image_url
    result = await session.execute(
        select(material_url_column)
        .where(Material.tool_type == tool_type)
        .where(Material.is_active == True)
        .where(material_url_column.is_not(None))
        .limit(1)
    )
    url = result.scalar_one_or_none()
    if url:
        return url

    raise RuntimeError(f"No reusable completed media URL found for {tool_type.value}")


def _build_material(
    *,
    tool_type: ToolType,
    topic: str,
    topic_zh: str,
    index: int,
    media_url: str,
    language: str = "en",
    landing: bool = False,
) -> Material:
    media_kind = "video" if tool_type in VIDEO_TOOLS else "image"
    label = "landing" if landing else "readiness"
    prompt = f"VidGo {label} preset for {tool_type.value} topic {topic} #{index}"
    prompt_zh = f"VidGo {label} 預設素材：{topic_zh} #{index}"
    lookup_hash = Material.generate_lookup_hash(
        tool_type.value,
        prompt,
        "readiness-seed",
        f"{topic}:{index}:{language}:{media_kind}",
    )

    material = Material(
        lookup_hash=lookup_hash,
        tool_type=tool_type,
        main_topic="landing" if landing else tool_type.value,
        main_topic_zh="首頁" if landing else tool_type.value,
        topic=topic,
        topic_zh=topic_zh,
        language=language,
        tags=["readiness_seed", topic, media_kind],
        source=MaterialSource.SEED,
        status=MaterialStatus.APPROVED,
        prompt=prompt,
        prompt_zh=prompt_zh,
        prompt_en=prompt,
        input_params={
            "readiness_seed": True,
            "reused_generated_media": True,
            "media_kind": media_kind,
        },
        generation_steps=[],
        title_en=f"{topic.replace('_', ' ').title()} preset",
        title_zh=f"{topic_zh}預設素材",
        description_en="Seeded readiness preset using an already generated VidGo output.",
        description_zh="使用已生成的 VidGo 輸出補齊素材覆蓋率。",
        quality_score=0.8,
        sort_order=10_000 + index,
        is_featured=landing,
        is_active=True,
        approved_at=datetime.now(timezone.utc),
    )

    if tool_type in VIDEO_TOOLS:
        material.result_video_url = media_url
        material.result_watermarked_url = media_url
        material.duration_seconds = 5
        material.resolution = "720p"
    else:
        material.result_image_url = media_url
        material.result_watermarked_url = media_url
        material.result_thumbnail_url = media_url
        material.input_image_url = media_url
        material.resolution = "1024p"

    return material


async def _seed_to_count(
    session,
    *,
    tool_type: ToolType,
    topic: str,
    topic_zh: str,
    target_count: int,
    media_url: str,
    landing: bool = False,
    languages: Iterable[str] = ("en",),
) -> int:
    current = await _active_count(session, tool_type, topic)
    inserted = 0
    language_list = list(languages)

    while current + inserted < target_count:
        index = current + inserted + 1
        language = language_list[inserted % len(language_list)]
        session.add(
            _build_material(
                tool_type=tool_type,
                topic=topic,
                topic_zh=topic_zh,
                index=index,
                media_url=media_url,
                language=language,
                landing=landing,
            )
        )
        inserted += 1

    return inserted


async def main() -> None:
    async with AsyncSessionLocal() as session:
        media_urls = {
            ToolType.BACKGROUND_REMOVAL: await _latest_upload_url(session, ToolType.BACKGROUND_REMOVAL),
            ToolType.TRY_ON: await _latest_upload_url(session, ToolType.TRY_ON),
            ToolType.PATTERN_GENERATE: await _latest_upload_url(session, ToolType.PATTERN_GENERATE),
            ToolType.SHORT_VIDEO: await _latest_upload_url(session, ToolType.SHORT_VIDEO),
            ToolType.AI_AVATAR: await _latest_upload_url(session, ToolType.AI_AVATAR),
        }

        total_inserted = 0

        for tool_type, topics in CORE_TARGETS.items():
            for topic in topics:
                total_inserted += await _seed_to_count(
                    session,
                    tool_type=tool_type,
                    topic=topic,
                    topic_zh=_topic_zh(tool_type, topic),
                    target_count=1,
                    media_url=media_urls[tool_type],
                )

        for item in get_landing_topics():
            topic = item["id"]
            topic_zh = item["name_zh"]
            total_inserted += await _seed_to_count(
                session,
                tool_type=ToolType.SHORT_VIDEO,
                topic=topic,
                topic_zh=topic_zh,
                target_count=LANDING_VIDEO_PER_TOPIC,
                media_url=media_urls[ToolType.SHORT_VIDEO],
                landing=True,
            )
            total_inserted += await _seed_to_count(
                session,
                tool_type=ToolType.AI_AVATAR,
                topic=topic,
                topic_zh=topic_zh,
                target_count=LANDING_AVATAR_PER_TOPIC,
                media_url=media_urls[ToolType.AI_AVATAR],
                landing=True,
                languages=("en", "zh-TW"),
            )

        await session.commit()
        print(f"Seeded {total_inserted} readiness material rows")


if __name__ == "__main__":
    asyncio.run(main())
