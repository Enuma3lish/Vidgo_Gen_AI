// Shared catalog used by the ProductScene tool-hub page and the AppHeader
// dropdown. Each tile carries a label key, a target route, and a thumbnail.
//
// The current thumbnails are Unsplash photos chosen to match each tile's
// visual concept from the mockup. Replace `thumb` with your own GCS asset
// once branded thumbnails exist — that's the only field consumers care
// about. Keep the `id` stable so localStorage "Recently Used" entries
// don't desync after a swap.

// Hub categories — revised 2026-05-29 to the four "big topic" buckets the
// owner asked for, grouped by the user's GOAL rather than the media type:
//   advertising (廣告宣傳) — promo content: video, avatar, product scenes
//   interior    (室內設計) — room redesign + interior templates
//   branding    (品牌設計) — logo / hero image / packaging pattern / text
//   other       (其他酷炫的AI功能) — utility/effects: cutout, upscale, claymation
// Keep this list short; the 'all' tab is rendered first by the consumer
// view, so we don't include it here.
export type ToolHubCategory = 'advertising' | 'interior' | 'branding' | 'other'

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
  { id: 'recolor',             labelKey: 'tools.hub.tiles.recolor',            to: '/tools/pattern-generate',       thumb: `${T}/recolor.png`,             category: 'branding'    },
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
  { id: 'text',                labelKey: 'tools.hub.tiles.text',               to: '/tools/image-translator',       thumb: `${T}/text.png`,                category: 'branding'    },
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
  // entirely). Thumbnails reuse hub assets that visually match.
  { id: 'room-redesign',       labelKey: 'tools.hub.tiles.roomRedesign',       to: '/tools/room-redesign',          thumb: `${T}/three-d-illustration.png`,category: 'interior'    },
  { id: 'interior-templates',  labelKey: 'tools.hub.tiles.interiorTemplates',  to: '/tools/interior-templates',     thumb: `${T}/product-photography.png`, category: 'interior'    },
  // Floor-plan → 3D growth video (Gemini → render → Kling 3.0 → opt. Trellis).
  { id: 'floorplan-video',     labelKey: 'tools.hub.tiles.floorplanVideo',     to: '/tools/floorplan-to-video',     thumb: `${T}/three-d-illustration.png`,category: 'interior'    },
  // Row 7 — NEW Qubico-backed tools added 2026-05-24 after the stability
  // probe. Only video-background-remove was healthy; sibling video tools
  // upscale + watermark-remove dropped because they timed out or 404'd.
  { id: 'video-bg-remove',     labelKey: 'tools.hub.tiles.videoBgRemove',      to: '/tools/video-bg-remove',        thumb: `${T}/background.png`,          category: 'other'       },
  // Row 8 — multi-mode generative tool added 2026-05-24 mirroring
  // pippit/piapi's Claymation playground (Seedream + Kling + Seedance).
  { id: 'claymation',          labelKey: 'tools.hub.tiles.claymation',         to: '/tools/claymation',             thumb: `${T}/edit-with-ai.png`,        category: 'other'       },
  // Row 9 — flagship video/voice tools that existed in the router but
  // were missing from the hub catalog (added 2026-05-26 after the
  // dead-routes audit). Without these, users had no path to /tools/avatar
  // or /tools/video-dubbing from the hub page.
  // TODO: replace thumbs with dedicated assets when art is ready —
  // virtual-model.png matches AI Avatar's "talking spokesperson"
  // concept; text.png evokes dubbing's voice/script swap.
  { id: 'ai-avatar',           labelKey: 'tools.hub.tiles.aiAvatar',           to: '/tools/avatar',                 thumb: `${T}/virtual-model.png`,       category: 'advertising' },
  { id: 'video-dubbing',       labelKey: 'tools.hub.tiles.videoDubbing',       to: '/tools/video-dubbing',          thumb: `${T}/text.png`,                category: 'advertising' },
]

// Stable order of categories shown in the hub-view filter bar / header
// dropdown. Advertising leads (most tiles + the main conversion path);
// interior stays visible even with only 2 tiles since it's a flagship use
// case.
export const TOOL_HUB_CATEGORIES: ToolHubCategory[] = ['advertising', 'interior', 'branding', 'other']

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
