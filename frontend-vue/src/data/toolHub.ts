// Shared catalog used by the ProductScene tool-hub page and the AppHeader
// dropdown. Each tile carries a label key, a target route, and a thumbnail.
//
// The current thumbnails are Unsplash photos chosen to match each tile's
// visual concept from the mockup. Replace `thumb` with your own GCS asset
// once branded thumbnails exist — that's the only field consumers care
// about. Keep the `id` stable so localStorage "Recently Used" entries
// don't desync after a swap.

// Hub categories — revised 2026-05-29 to "big topic" buckets the owner
// asked for, grouped by the user's GOAL rather than the media type.
// 2026-06-12: the combined 室內室外設計 bucket was split (owner directive:
// never mix interior and exterior — each group lists its own per-tool pages):
//   advertising (廣告宣傳) — promo content: video, avatar, product scenes
//   interior    (室內設計) — room redesign / floor plan / isometric / 3D render…
//   exterior    (室外設計) — building facade / exterior sketch / exterior templates
//   branding    (品牌設計) — logo / hero image / packaging pattern / text
//   other       (其他酷炫的AI功能) — utility/effects: cutout, upscale, claymation
// Keep this list short; the 'all' tab is rendered first by the consumer
// view, so we don't include it here.
export type ToolHubCategory = 'advertising' | 'interior' | 'exterior' | 'branding' | 'other'

export interface ToolHubTile {
  id: string
  labelKey: string
  to: string
  thumb: string
  category: ToolHubCategory
}

// Order intentionally matches the AppHeader dropdown mockup (Image 5),
// row by row in a 4-column grid.
// Thumbnails hosted on GCS — generated via backend/scripts/generate_brand_assets.py.
// To regenerate, run that script and the URLs stay stable (same blob path).
const T = 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/hub'
export const toolHubTiles: ToolHubTile[] = [
  // Row 1
  // 2026-06-12 — recolor now has its own dedicated tool (was mis-linked to
  // the pattern generator).
  { id: 'recolor',             labelKey: 'tools.hub.tiles.recolor',            to: '/tools/recolor',                thumb: `${T}/recolor.png`,             category: 'branding'    },
  { id: 'product-beautifier',  labelKey: 'tools.hub.tiles.productBeautifier',  to: '/tools/upscale',                thumb: `${T}/product-beautifier.png`,  category: 'other'       },
  { id: 'virtual-model',       labelKey: 'tools.hub.tiles.virtualModel',       to: '/tools/try-on',                 thumb: `${T}/virtual-model.png`,       category: 'advertising' },
  { id: 'product-staging',     labelKey: 'tools.hub.tiles.productStaging',     to: '/tools/product-scene-classic',  thumb: `${T}/product-staging.png`,     category: 'advertising' },
  // Row 2
  { id: 'edit-with-ai',        labelKey: 'tools.hub.tiles.editWithAi',         to: '/tools/midjourney-imagine',     thumb: `${T}/edit-with-ai.png`,        category: 'branding'    },
  { id: 'ghost-mannequin',     labelKey: 'tools.hub.tiles.ghostMannequin',     to: '/tools/background-removal',     thumb: `${T}/ghost-mannequin.png`,     category: 'other'       },
  { id: 'ironing',             labelKey: 'tools.hub.tiles.ironing',            to: '/tools/upscale',                thumb: `${T}/ironing.png`,             category: 'other'       },
  { id: 'flat-lay',            labelKey: 'tools.hub.tiles.flatLay',            to: '/tools/product-scene-classic',  thumb: `${T}/flat-lay.png`,            category: 'advertising' },
  // Row 3
  { id: 'logo',                labelKey: 'tools.hub.tiles.logo',               to: '/tools/midjourney-imagine',     thumb: `${T}/logo.png`,                category: 'branding'    },
  { id: 'create-any-image',    labelKey: 'tools.hub.tiles.createAnyImage',     to: '/tools/midjourney-imagine',     thumb: `${T}/create-any-image.png`,    category: 'branding'    },
  { id: 'instagram-story',     labelKey: 'tools.hub.tiles.instagramStory',     to: '/tools/short-video',            thumb: `${T}/instagram-story.png`,     category: 'advertising' },
  // Row 4
  { id: 'product-photography', labelKey: 'tools.hub.tiles.productPhotography', to: '/tools/product-scene-classic',  thumb: `${T}/product-photography.png`, category: 'advertising' },
  { id: 'product-packaging',   labelKey: 'tools.hub.tiles.productPackaging',   to: '/tools/pattern-generate',       thumb: `${T}/product-packaging.png`,   category: 'branding'    },
  { id: 'background',          labelKey: 'tools.hub.tiles.background',         to: '/tools/background-removal',     thumb: `${T}/background.png`,          category: 'other'       },
  // 2026-05-19: Luma retired. Point this tile at Kling-video (premium
  // tier supports Omni / 3.0 for the cinematic-3D look the original Luma
  // slot covered).
  { id: 'three-d-illustration',labelKey: 'tools.hub.tiles.threeDIllustration', to: '/tools/kling-video',            thumb: `${T}/three-d-illustration.png`,category: 'advertising' },
  // Row 5
  { id: 'video-generator',     labelKey: 'tools.hub.tiles.videoGenerator',     to: '/tools/kling-video',            thumb: `${T}/video-generator.png`,     category: 'advertising' },
  // Row 6 — interior tools (added 2026-05-24 after QA flagged that the
  // tool-hub dropdown was missing room redesign / interior templates
  // entirely). 2026-06-12: every interior tile now has its own dedicated
  // thumbnail (owner flagged the placeholder reuse as confusing duplicates) —
  // generated via backend/scripts/generate_brand_assets.py, filename = tile id.
  { id: 'room-redesign',       labelKey: 'tools.hub.tiles.roomRedesign',       to: '/tools/room-redesign',          thumb: `${T}/room-redesign.png`,       category: 'interior'    },
  { id: 'interior-templates',  labelKey: 'tools.hub.tiles.interiorTemplates',  to: '/tools/interior-templates',     thumb: `${T}/interior-templates.png`,  category: 'interior'    },
  // 2026-06-11 — interior design workflow: 平面配置圖 / 立體圖 / 3D 效果圖.
  // The standalone floorplan-to-video tile was removed; its growth video is now
  // an output option inside 3D 效果圖 (/tools/render-3d).
  { id: 'floor-plan',          labelKey: 'tools.hub.tiles.floorPlan',          to: '/tools/floor-plan',             thumb: `${T}/floor-plan.png`,          category: 'interior'    },
  { id: 'isometric',           labelKey: 'tools.hub.tiles.isometric',          to: '/tools/isometric',              thumb: `${T}/isometric.png`,           category: 'interior'    },
  { id: 'render-3d',           labelKey: 'tools.hub.tiles.render3d',           to: '/tools/render-3d',              thumb: `${T}/render-3d.png`,           category: 'interior'    },
  // 2026-06-03 — exterior/render-enhancer/sketch tools added after the owner
  // asked to mirror mnml.ai's exterior-ai / render-enhancer / sketch2img.
  // 2026-06-12 — exterior tools moved to their own 室外設計 category (owner
  // directive: never mix interior and exterior; each group lists its own
  // per-tool pages). Commercial-space stays in interior (it designs interiors
  // of commercial venues); render-enhancer stays in interior as the generic
  // render utility.
  { id: 'commercial-space',    labelKey: 'tools.hub.tiles.commercialSpace',    to: '/tools/commercial-space',       thumb: `${T}/commercial-space.png`,    category: 'interior'    },
  { id: 'sketch-to-render-interior', labelKey: 'tools.hub.tiles.sketchToRenderInterior', to: '/tools/sketch-to-render-interior', thumb: `${T}/sketch-to-render-interior.png`, category: 'interior' },
  { id: 'render-enhancer',     labelKey: 'tools.hub.tiles.renderEnhancer',     to: '/tools/render-enhancer',        thumb: `${T}/render-enhancer.png`,     category: 'interior'    },
  // ── 室外設計 (exterior) group — each tool is its own dedicated page ──
  { id: 'exterior-ai',         labelKey: 'tools.hub.tiles.exteriorAi',         to: '/tools/exterior-ai',            thumb: `${T}/exterior-ai.png`,         category: 'exterior'    },
  { id: 'landscape-ai',        labelKey: 'tools.hub.tiles.landscapeAi',        to: '/tools/landscape-ai',           thumb: `${T}/landscape-ai.png`,        category: 'exterior'    },
  { id: 'sketch-to-render-exterior', labelKey: 'tools.hub.tiles.sketchToRenderExterior', to: '/tools/sketch-to-render-exterior', thumb: `${T}/sketch-to-render-exterior.png`, category: 'exterior' },
  { id: 'exterior-templates',  labelKey: 'tools.hub.tiles.exteriorTemplates',  to: '/tools/exterior-templates',     thumb: `${T}/exterior-templates.png`,  category: 'exterior'    },
  // Row 7 — NEW Qubico-backed tools added 2026-05-24 after the stability
  // probe. Only video-background-remove was healthy; sibling video tools
  // upscale + watermark-remove dropped because they timed out or 404'd.
  { id: 'video-bg-remove',     labelKey: 'tools.hub.tiles.videoBgRemove',      to: '/tools/video-bg-remove',        thumb: `${T}/video-bg-remove.png`,     category: 'other'       },
  // Row 8 — multi-mode generative tool added 2026-05-24 mirroring
  // pippit/piapi's Claymation playground (Seedream + Kling + Seedance).
  { id: 'claymation',          labelKey: 'tools.hub.tiles.claymation',         to: '/tools/claymation',             thumb: `${T}/claymation.png`,          category: 'other'       },
  // Row 9 — flagship video/voice tools that existed in the router but
  // were missing from the hub catalog (added 2026-05-26 after the
  // dead-routes audit). Without this, users had no path to /tools/avatar
  // from the hub page.
  { id: 'ai-avatar',           labelKey: 'tools.hub.tiles.aiAvatar',           to: '/tools/avatar',                 thumb: `${T}/ai-avatar.png`,           category: 'advertising' },
  // 2026-06-09 — Sora 2 Pro flagship video (PiAPI primary, Pollo backup).
  // Category=advertising because the flagship 5-10s clips slot into the same
  // promo workflow as Kling Omni / Veo.
  { id: 'sora2-pro',           labelKey: 'tools.hub.tiles.sora2Pro',           to: '/tools/sora2-pro',              thumb: `${T}/sora2-pro.png`,           category: 'advertising' },
]

// Stable order of categories shown in the hub-view filter bar / header
// dropdown. Advertising leads (most tiles + the main conversion path);
// interior and exterior sit side by side as separate flagship groups
// (2026-06-12 split).
export const TOOL_HUB_CATEGORIES: ToolHubCategory[] = ['advertising', 'interior', 'exterior', 'branding', 'other']

// localStorage-backed list of recently used tool IDs (max 4). Keep this
// outside of pinia so the AppHeader dropdown and the hub page can both read
// it without touching a store on first render.
const RECENT_STORAGE_KEY = 'vidgo.toolHub.recent'
const RECENT_MAX = 4

export function getRecentToolIds(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.slice(0, RECENT_MAX) : []
  } catch {
    return []
  }
}

export function pushRecentTool(id: string): void {
  try {
    const current = getRecentToolIds().filter((existing) => existing !== id)
    current.unshift(id)
    localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(current.slice(0, RECENT_MAX)))
  } catch {
    // localStorage unavailable (private mode, etc.) — silently drop.
  }
}

export function getRecentTiles(): ToolHubTile[] {
  const ids = getRecentToolIds()
  return ids
    .map((id) => toolHubTiles.find((tile) => tile.id === id))
    .filter((tile): tile is ToolHubTile => Boolean(tile))
}
