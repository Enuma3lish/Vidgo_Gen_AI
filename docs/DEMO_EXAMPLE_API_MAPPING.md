# Demo Example ↔ API Mapping

This doc describes how frontend "try/play" examples map to backend APIs and Material DB so that **home style change** and other demo flows work.

## Room Redesign (Home Style Change)

- **Frontend:** `RoomRedesign.vue`
  - Loads styles from `GET /api/v1/interior/styles` (ids: `modern_minimalist`, `scandinavian`, `japanese`, `industrial`, `mid_century_modern`, …).
  - Loads room types from `GET /api/v1/interior/room-types` (ids: `living_room`, `bedroom`, `kitchen`, …).
  - Demo presets from `GET /api/v1/demo/presets/room_redesign` (no topic).
  - Matching key: `room_id` + `room_type` + `style_id` from each preset’s `input_params` and `input_image_url`.
- **Backend:**
  - Pregenerate (`main_pregenerate.py` → `generate_room_redesign`) must use the **same style IDs** as `DESIGN_STYLES` in `interior_design_service.py` so that `input_params.style_id` matches the frontend.
  - Stored fields: `input_params.room_id` (e.g. `room-1`), `input_params.room_type` (e.g. `living_room`), `input_params.style_id` (e.g. `modern_minimalist`), `input_image_url` = room image URL, `topic` = `room_type` for optional topic filter.
- **Room URLs** must match frontend `defaultRooms` in `RoomRedesign.vue` (same Unsplash URLs).

## Other Tools (Example ↔ API)

| Tool | Presets API | Frontend matching | Pregenerate / Material |
|------|-------------|--------------------|-------------------------|
| **background_removal** | `GET /api/v1/demo/presets/background_removal` | topic, prompt; optional `try_prompts` when db_empty | topic from try_prompts / topic_registry |
| **product_scene** | `GET /api/v1/demo/presets/product_scene` | topic, input_image_url / product id | PRODUCT_SCENE_MAPPING products × scenes |
| **effect** | `GET /api/v1/demo/presets/effect` | topic (style), input_image_url | VIDGO_STYLES ids, source images |
| **try_on** | `GET /api/v1/demo/presets/try_on` | model, clothing, gender | try_on mapping |
| **short_video** | `GET /api/v1/demo/presets/short_video` | topic, prompt | motion types, prompts |
| **ai_avatar** | `GET /api/v1/demo/presets/ai_avatar` | topic, script, language | A2E topics × scripts × languages |

## Important

- **Room redesign:** `style_id` in Material `input_params` must be one of `DESIGN_STYLES` keys (e.g. `modern_minimalist`, `scandinavian`), not the old topic_registry style names (`modern`, `nordic`).
- **Presets response** includes `input_params`; frontend uses it to match the current selection (room + roomType + style) to a pre-generated result.
