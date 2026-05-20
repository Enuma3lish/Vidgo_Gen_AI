// Shared catalog used by the ProductScene tool-hub page and the AppHeader
// dropdown. Each tile carries a label key, a target route, and a thumbnail.
//
// The current thumbnails are Unsplash photos chosen to match each tile's
// visual concept from the mockup. Replace `thumb` with your own GCS asset
// once branded thumbnails exist — that's the only field consumers care
// about. Keep the `id` stable so localStorage "Recently Used" entries
// don't desync after a swap.

export interface ToolHubTile {
  id: string
  labelKey: string
  to: string
  thumb: string
}

// Order intentionally matches the AppHeader dropdown mockup (Image 5),
// row by row in a 4-column grid.
// Thumbnails hosted on GCS — generated via backend/scripts/generate_brand_assets.py.
// To regenerate, run that script and the URLs stay stable (same blob path).
const T = 'https://storage.googleapis.com/vidgo-media-vidgo-ai/static/hub'
export const toolHubTiles: ToolHubTile[] = [
  // Row 1
  { id: 'recolor',             labelKey: 'tools.hub.tiles.recolor',            to: '/tools/pattern-generate',       thumb: `${T}/recolor.png` },
  { id: 'product-beautifier',  labelKey: 'tools.hub.tiles.productBeautifier',  to: '/tools/upscale',                thumb: `${T}/product-beautifier.png` },
  { id: 'virtual-model',       labelKey: 'tools.hub.tiles.virtualModel',       to: '/tools/try-on',                 thumb: `${T}/virtual-model.png` },
  { id: 'product-staging',     labelKey: 'tools.hub.tiles.productStaging',     to: '/tools/product-scene-classic',  thumb: `${T}/product-staging.png` },
  // Row 2
  { id: 'edit-with-ai',        labelKey: 'tools.hub.tiles.editWithAi',         to: '/tools/midjourney-imagine',     thumb: `${T}/edit-with-ai.png` },
  { id: 'ghost-mannequin',     labelKey: 'tools.hub.tiles.ghostMannequin',     to: '/tools/background-removal',     thumb: `${T}/ghost-mannequin.png` },
  { id: 'ironing',             labelKey: 'tools.hub.tiles.ironing',            to: '/tools/upscale',                thumb: `${T}/ironing.png` },
  { id: 'flat-lay',            labelKey: 'tools.hub.tiles.flatLay',            to: '/tools/product-scene-classic',  thumb: `${T}/flat-lay.png` },
  // Row 3
  { id: 'logo',                labelKey: 'tools.hub.tiles.logo',               to: '/tools/midjourney-imagine',     thumb: `${T}/logo.png` },
  { id: 'text',                labelKey: 'tools.hub.tiles.text',               to: '/tools/image-translator',       thumb: `${T}/text.png` },
  { id: 'create-any-image',    labelKey: 'tools.hub.tiles.createAnyImage',     to: '/tools/midjourney-imagine',     thumb: `${T}/create-any-image.png` },
  { id: 'instagram-story',     labelKey: 'tools.hub.tiles.instagramStory',     to: '/tools/short-video',            thumb: `${T}/instagram-story.png` },
  // Row 4
  { id: 'product-photography', labelKey: 'tools.hub.tiles.productPhotography', to: '/tools/product-scene-classic',  thumb: `${T}/product-photography.png` },
  { id: 'product-packaging',   labelKey: 'tools.hub.tiles.productPackaging',   to: '/tools/pattern-generate',       thumb: `${T}/product-packaging.png` },
  { id: 'background',          labelKey: 'tools.hub.tiles.background',         to: '/tools/background-removal',     thumb: `${T}/background.png` },
  // 2026-05-19: Luma retired. Point this tile at Kling-video (premium
  // tier supports Omni / 3.0 for the cinematic-3D look the original Luma
  // slot covered).
  { id: 'three-d-illustration',labelKey: 'tools.hub.tiles.threeDIllustration', to: '/tools/kling-video',            thumb: `${T}/three-d-illustration.png` },
  // Row 5
  { id: 'video-generator',     labelKey: 'tools.hub.tiles.videoGenerator',     to: '/tools/kling-video',            thumb: `${T}/video-generator.png` },
]

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
