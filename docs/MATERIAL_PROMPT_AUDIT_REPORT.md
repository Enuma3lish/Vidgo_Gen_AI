# Material Prompt Audit Report

## Executive Summary

This report audits:
1. **Prompt confidence & correctness** – prompts used to generate Material examples
2. **Effect tool scope** – Ads-only vs Creative (should be Ads only)
3. **Material DB alignment** – topic matching and Ads orientation

---

## 1. Prompts Used for Generation

### 1.1 Effect (Style Transfer)

| Source | Prompt Purpose | Current State | Correctness |
|--------|----------------|---------------|-------------|
| **EFFECT_MAPPING source_images** | T2I product photo | Product-focused (bubble tea, fried chicken, sneakers, etc.) | ✅ Correct – business products |
| **EFFECT_MAPPING styles[].prompt** | I2I style transfer (effect_prompt) | Contains "for social media and ads", "for menu and cafe branding", "for product ads" | ✅ Ads-oriented |
| **Stored in Material** | `effect_prompt` = style_data["prompt"] | From EFFECT_MAPPING | Same as above |

**Note:** Existing DB rows may have **old** effect_prompts (e.g. `"anime style illustration"` without Ads context) if generated before the Ads-focused update. Run re-generation to fix.

### 1.2 Pattern Generate

| Source | Purpose | Current State | Correctness |
|--------|---------|---------------|-------------|
| **PATTERN_GENERATE_MAPPING** | T2I pattern prompts | Contains "for packaging", "for menu border", "for cafe branding", "for social media", "for retail" | ✅ Business-oriented |

### 1.3 Product Scene, Background Removal, Room Redesign, etc.

- All use product/room/scene prompts with commercial intent
- Product Scene: PRODUCT_SCENE_MAPPING with 廣告風格 (ad style) in prompts
- Room Redesign: Uses DESIGN_STYLES from interior_design_service

---

## 2. Effect Tool: Ads vs Creative

### Intended Scope

- **Effect** = 廣告特效 (ad effects) per landing/API
- Should be **Ads only**: menu, social ads, product ads, flyers, branding
- Should **NOT** be creative-only (personal art, artistic expression without business context)

### Current Code

| Location | Content | Ads-only? |
|----------|---------|-----------|
| **main_pregenerate.py EFFECT_MAPPING styles** | `"anime style illustration for social media and ads, eye-catching for small business"` | ✅ Yes |
| **main_pregenerate.py** | `"watercolor soft style for menu design and boutique branding"` | ✅ Yes |
| **effects_service.py VIDGO_STYLES** | `"anime style"`, `"watercolor painting soft artistic style"` | ⚠️ **No Ads context** – used for live API, not pregen |

**Gap:** VIDGO_STYLES (used by `/api/v1/effects/apply-style`) has generic style prompts without Ads framing. Pre-generation uses EFFECT_MAPPING which is Ads-focused. If users generate via live API, the effect may not be explicitly Ads-oriented.

### Recommendation

- Pre-generated examples: ✅ Use EFFECT_MAPPING (Ads-focused)
- Live API: VIDGO_STYLES prompts are short style descriptors – acceptable if the *tool positioning* (UI, docs) states "for ads and marketing" and examples are Ads-focused

---

## 3. Material DB: Topic Match & Ads Orientation

### Topic Validation

| Tool Type | Valid Topics (topic_registry) | Stored As |
|-----------|-------------------------------|-----------|
| **effect** | anime, ghibli, cartoon, oil_painting, watercolor | Material.topic = style_id |
| **product_scene** | studio, nature, luxury, minimal, lifestyle, urban, seasonal, holiday | Material.topic = scene_id |
| **background_removal** | drinks, snacks, desserts, meals, packaging, equipment, signage, ingredients | Material.topic |
| **room_redesign** | room_type (living_room, bedroom, …) or style_id | Material.topic = room_type (after fix) |
| **pattern_generate** | seamless, floral, geometric, abstract, traditional | Material.topic = style_id |

**Potential issues:**
- Old room_redesign materials may have `topic` = style_id (e.g. "modern") instead of room_type – frontend matching expects room_type or input_params.room_type
- Any material with `topic` not in `get_topic_ids_for_tool(tool_type)` is a mismatch

### Ads Orientation

| Tool | Ads-oriented by design? | Notes |
|------|-------------------------|-------|
| **effect** | Should be | effect_prompt must contain Ads context; old DB rows may not |
| **product_scene** | Yes | Product photography for e-commerce/ads |
| **background_removal** | Yes | Product cutout for ads/e-commerce |
| **short_video** | Yes | Product ads, promo videos |
| **ai_avatar** | Yes | Brand spokesperson, product intro |
| **pattern_generate** | Yes (after update) | Packaging, branding, menu, retail |
| **room_redesign** | Yes | Interior for real estate/design marketing |

---

## 4. Audit Script

Run to verify current Material DB:

```bash
cd backend
python -m scripts.audit_material_prompts
```

Or via Docker:

```bash
docker compose --profile tools run --rm pregenerate python -m scripts.audit_material_prompts
```

The script reports:
- Topic mismatches (topic not in topic_registry for that tool)
- Effect materials with effect_prompt lacking Ads keywords
- Effect materials with creative-only keywords

---

## 5. Recommendations

1. **Re-run pre-generation** for effect (and optionally pattern, room_redesign) so new materials use Ads-focused prompts.
2. **Run audit script** periodically to catch topic and Ads-orientation drift.
3. **VIDGO_STYLES**: Now includes Ads context (food, product, menu, etc.) for common-purpose ads—NOT luxury.
4. **Remove creative-only wording** from any prompt that should be Ads-only.

---

## 6. Replace Non-Ads Materials (Selective Delete + Pregenerate)

**Scope:** Ads for common purpose (food, general product) — NOT luxury.

### Script: `scripts/replace_non_ads_materials.py`

- **Effect:** Deletes materials whose `effect_prompt` lacks Ads keywords.
- **Short Video / AI Avatar:** Deletes materials whose prompt contains luxury/premium keywords.

```bash
# Dry-run: report what would be deleted (no changes)
docker compose --profile tools run --rm pregenerate python -m scripts.replace_non_ads_materials

# Actually soft-delete non-conforming materials
docker compose --profile tools run --rm pregenerate python -m scripts.replace_non_ads_materials --delete

# Delete + run pregenerate for effect, short_video, ai_avatar
docker compose --profile tools run --rm pregenerate python -m scripts.replace_non_ads_materials --delete --pregenerate
```

### Pregenerate Only (after selective delete)

```bash
docker compose --profile tools run --rm pregenerate python -m scripts.main_pregenerate --tool effect --limit 40
docker compose --profile tools run --rm pregenerate python -m scripts.main_pregenerate --tool short_video --limit 40
docker compose --profile tools run --rm pregenerate python -m scripts.main_pregenerate --tool ai_avatar --limit 40
```

**Note:** Ensure `backend/.env` exists and Docker services (postgres, etc.) are running.
