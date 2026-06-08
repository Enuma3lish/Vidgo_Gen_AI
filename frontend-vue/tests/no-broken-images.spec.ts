import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// Regression guard for the broken-image fixes (T-01 / T-02): the GCS thumbnail
// assets can 404 (missing upload, expired signed URL), so every <img> on the
// user-facing pages MUST carry an @error fallback — otherwise a missing asset
// renders the browser's broken-image icon. We scan only the <template> block so
// commented-out samples or `<img>` mentioned in <script> comments don't count.

// cwd is the frontend-vue package root both locally (npm run test) and in CI
// (working-directory: frontend-vue), so resolve sources from there.
function readSrc(rel: string): string {
  return readFileSync(resolve(process.cwd(), 'src', rel), 'utf8')
}

function templateBlock(src: string): string {
  const match = src.match(/<template>[\s\S]*<\/template>/i)
  return (match ? match[0] : '').replace(/<!--[\s\S]*?-->/g, '')
}

function imgTags(template: string): string[] {
  return template.match(/<img\b[\s\S]*?>/gi) ?? []
}

const KEY_VIEWS = [
  'views/LandingPage.vue', // /
  'views/tools/RoomRedesign.vue', // /tools/room-redesign
  'views/tools/InteriorTemplates.vue', // /tools/interior-templates
]

describe('no-broken-images', () => {
  for (const view of KEY_VIEWS) {
    const tags = imgTags(templateBlock(readSrc(view)))

    it(`${view} renders at least one <img>`, () => {
      expect(tags.length).toBeGreaterThan(0)
    })

    it(`every <img> in ${view} has an @error fallback`, () => {
      const unguarded = tags.filter((tag) => !/(@error|v-on:error)\b/.test(tag))
      expect(unguarded, `These <img> tags lack an @error handler:\n${unguarded.join('\n')}`).toEqual([])
    })
  }

  it('LandingPage fallback image URLs are absolute https, not broken local paths', () => {
    const src = readSrc('views/LandingPage.vue')
    const urls = src.match(/https:\/\/[^\s"'`)]+\.(?:png|jpg|jpeg|webp|gif)/gi) ?? []
    expect(urls.length).toBeGreaterThan(0)
    for (const url of urls) {
      expect(url.startsWith('https://'), `${url} should be an absolute https URL`).toBe(true)
    }
  })
})
