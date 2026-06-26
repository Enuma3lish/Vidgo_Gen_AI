# VidGo — Official Frontend Route Reference

Canonical list of SPA routes (source of truth: `frontend-vue/src/router/index.ts`).
Anything not listed here 404s by design — the SPA catch-all (`/:pathMatch(.*)*`)
renders NotFound. Use this to avoid linking to non-existent paths.

## ⚠️ Known non-existent paths (these 404 — not a bug)

| Path people try | Why it 404s | Use instead |
|---|---|---|
| `/dashboard/billing` | No such route. Billing/subscription management lives on the pricing page and invoices page. | `/pricing` (current plan, status, cancel) · `/dashboard/invoices` (invoice history) |
| `/tools/interior-design` | No single "interior design" route — the feature is split across several tools. | `/tools/room-redesign`, `/tools/floor-plan`, `/tools/render-3d`, `/tools/isometric`, `/tools/interior-templates`, `/tools/sketch-to-render-interior` |

## Core / public

| Path | Purpose |
|---|---|
| `/` | Landing page |
| `/pricing` | Plans, current subscription status + cancel, credit packs |
| `/info/:slug` and `/:slug` | Static pages: about, contact, blog, affiliate, terms, terms-of-service, terms-and-conditions, privacy, privacy-policy, cookies, refunds, refund, refund-policy |

## Auth

| Path | Purpose |
|---|---|
| `/auth/login` | Login |
| `/auth/register` | Register |
| `/auth/verify` | Email verification |
| `/auth/forgot-password` | Request password reset |
| `/auth/reset-password` | Complete password reset |

## Dashboard (authenticated)

| Path | Purpose |
|---|---|
| `/dashboard` | Dashboard home |
| `/dashboard/my-works` | Generated works gallery |
| `/dashboard/invoices` | Invoices / billing history |
| `/dashboard/referrals` | Referral program |
| `/dashboard/share-links` | Share links |
| `/dashboard/social-accounts` | Connected social accounts |

## Tools — canonical

`/tools/background-removal`, `/tools/product-scene`, `/tools/product-scene-classic`,
`/tools/try-on`, `/tools/recolor`, `/tools/room-redesign`, `/tools/floor-plan`,
`/tools/isometric`, `/tools/render-3d`, `/tools/exterior-ai`, `/tools/commercial-space`,
`/tools/landscape-ai`, `/tools/sketch-to-render-exterior`, `/tools/sketch-to-render-interior`,
`/tools/render-enhancer`, `/tools/interior-templates`, `/tools/exterior-templates`,
`/tools/commercial-templates`, `/tools/video-bg-remove`, `/tools/claymation`,
`/tools/short-video`, `/tools/upscale`, `/tools/avatar`, `/tools/pattern-generate`,
`/tools/midjourney-imagine`, `/tools/kling-video`, `/tools/sora2-pro`

Topic landing pages: `/topics/pattern`, `/topics/product`, `/topics/video`

## Tools — redirect aliases (legacy → canonical)

| Alias | Redirects to |
|---|---|
| `/tools/effects`, `/tools/image-transform` | `/tools/room-redesign` |
| `/tools/floorplan-to-video` | `/tools/render-3d` |
| `/tools/sketch-to-render` | `/tools/sketch-to-render-exterior` |
| `/tools/image-to-video`, `/tools/text-to-video`, `/tools/luma-video`, `/tools/product-video` | `/tools/short-video` |
| `/tools/image-upscale`, `/tools/product-enhance` | `/tools/upscale` |
| `/tools/remove-watermark` | `/tools/effects` |
| `/tools/image-translator`, `/tools/video-dubbing`, `/tools/ai-templates` | `/tools/product-scene` |
| `/tools/ai-model-swap`, `/tools/try-on-accessories` | `/tools/try-on` |
| `/tools/pattern-transfer`, `/tools/pattern-seamless` | `/tools/pattern-generate` |

## Subscription callbacks

`/subscription/success`, `/subscription/cancelled`, `/subscription/mock-checkout`, `/subscription/ecpay-result`

## Admin (`/admin/*`, superuser only)

`/admin/dashboard`, `/admin/users`, `/admin/promotions`, `/admin/materials`,
`/admin/moderation`, `/admin/revenue`, `/admin/system`, `/admin/plans`,
`/admin/branding`, `/admin/costs`, `/admin/models`, `/admin/settings/payment`
