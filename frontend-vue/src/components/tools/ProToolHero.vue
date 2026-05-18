<script setup lang="ts">
/**
 * Pro tool hero — drops in at the top of a tool page in place of the
 * plain <h1> + subline. Combines patterns observed on SellerPic.ai,
 * Photoroom and ReRoom: eyebrow badge → outcome headline → rating +
 * trust line → 3 KPI stats → 3-step "how it works".
 *
 * Stays in the existing VidGo dark palette (#09090b background, #141420
 * card, #f59e0b amber accent) — no theme change. All copy is provided
 * by the parent so this component is i18n-agnostic.
 */
interface Stat { value: string; label: string }
interface Step { icon: string; title: string; body?: string }

defineProps<{
  badge?: string                  // small eyebrow text, e.g. "AI 商品攝影"
  title: string                   // outcome headline, e.g. "用一張白底圖，生成電商級情境照"
  subtitle?: string               // 1-line supporting copy
  rating?: { score: string; label: string } // e.g. { score: '4.9', label: '深受 1,000+ 商家信賴' }
  trustLine?: string              // small line under rating — e.g. "Amazon · Shopify · TikTok 規格一鍵匯出"
  stats?: Stat[]                  // up to 3, displayed in a strip
  steps?: Step[]                  // up to 3, displayed below stats
  ctaText?: string                // optional CTA button label (renders a link if `ctaTo` is set)
  ctaTo?: string                  // router target for the CTA button
}>()
</script>

<template>
  <section class="pro-hero">
    <div class="pro-hero-text">
      <span v-if="badge" class="pro-hero-badge">{{ badge }}</span>
      <h1 class="pro-hero-title">{{ title }}</h1>
      <p v-if="subtitle" class="pro-hero-subtitle">{{ subtitle }}</p>

      <div v-if="rating || trustLine" class="pro-hero-trust">
        <span v-if="rating" class="pro-hero-rating">
          <span class="pro-hero-stars" aria-hidden="true">★★★★★</span>
          <span class="pro-hero-score">{{ rating.score }}</span>
          <span class="pro-hero-rating-label">{{ rating.label }}</span>
        </span>
        <span v-if="trustLine" class="pro-hero-trustline">{{ trustLine }}</span>
      </div>

      <div v-if="ctaText && ctaTo" class="pro-hero-cta-row">
        <RouterLink :to="ctaTo" class="pro-hero-cta">{{ ctaText }}</RouterLink>
      </div>
    </div>

    <div v-if="stats && stats.length" class="pro-hero-stats">
      <div v-for="(s, i) in stats" :key="i" class="pro-hero-stat">
        <div class="pro-hero-stat-value">{{ s.value }}</div>
        <div class="pro-hero-stat-label">{{ s.label }}</div>
      </div>
    </div>

    <div v-if="steps && steps.length" class="pro-hero-steps">
      <div v-for="(step, i) in steps" :key="i" class="pro-hero-step">
        <div class="pro-hero-step-index">{{ String(i + 1).padStart(2, '0') }}</div>
        <div class="pro-hero-step-icon">{{ step.icon }}</div>
        <div class="pro-hero-step-title">{{ step.title }}</div>
        <div v-if="step.body" class="pro-hero-step-body">{{ step.body }}</div>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* Refined for a more "developer-tool / technical" feel:
   - Sharper geometry (smaller radii, square dot-grid hint)
   - Mono numerics for KPI values
   - Amber reserved for primary accent + tiny tick marks; reduce elsewhere */
.pro-hero {
  margin-bottom: 36px;
}

.pro-hero-text {
  text-align: center;
  max-width: 780px;
  margin: 0 auto 32px;
}

.pro-hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 4px;
  background: rgba(245, 158, 11, 0.08);
  color: #fbbf24;
  border: 1px solid rgba(245, 158, 11, 0.28);
  font-family: ui-monospace, "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  margin-bottom: 16px;
}
.pro-hero-badge::before {
  content: "";
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #fbbf24;
  box-shadow: 0 0 8px rgba(251, 191, 36, 0.6);
}

.pro-hero-title {
  font-size: clamp(28px, 4vw, 46px);
  font-weight: 800;
  color: #f5f5fa;
  line-height: 1.12;
  letter-spacing: -0.02em;
  margin-bottom: 14px;
}

.pro-hero-subtitle {
  font-size: 16px;
  line-height: 1.55;
  color: #a8a8c4;
  max-width: 620px;
  margin: 0 auto;
}

.pro-hero-trust {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 12px 20px;
  margin-top: 20px;
  font-size: 12px;
  font-family: ui-monospace, "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
}

.pro-hero-rating {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #d6d3d1;
}
.pro-hero-stars { color: #fbbf24; letter-spacing: 1px; font-size: 13px; }
.pro-hero-score { font-weight: 700; color: #f5f5fa; }
.pro-hero-rating-label { color: #8b8ba8; font-family: inherit; }

.pro-hero-trustline {
  color: #8b8ba8;
  position: relative;
  padding-left: 14px;
}
.pro-hero-trustline::before {
  content: "/";
  position: absolute;
  left: 0;
  color: #3a3a4d;
}

.pro-hero-cta-row {
  margin-top: 24px;
}
.pro-hero-cta {
  display: inline-block;
  padding: 11px 22px;
  border-radius: 6px;
  font-weight: 700;
  font-size: 14px;
  background: #f59e0b;
  color: #0a0a0a;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.pro-hero-cta:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 18px rgba(245, 158, 11, 0.32);
}

.pro-hero-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
  margin-bottom: 24px;
}
.pro-hero-stat {
  position: relative;
  padding: 18px 20px;
  border-radius: 8px;
  background: #0f0f17;
  border: 1px solid rgba(255, 255, 255, 0.06);
  text-align: left;
  transition: border-color 0.18s ease, transform 0.18s ease;
  overflow: hidden;
}
.pro-hero-stat::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  width: 3px;
  height: 100%;
  background: linear-gradient(180deg, #f59e0b 0%, rgba(245, 158, 11, 0) 100%);
  opacity: 0.5;
}
.pro-hero-stat:hover {
  transform: translateY(-1px);
  border-color: rgba(245, 158, 11, 0.4);
}
.pro-hero-stat-value {
  font-family: ui-monospace, "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
  font-size: clamp(22px, 2.8vw, 30px);
  font-weight: 700;
  color: #f5f5fa;
  line-height: 1.1;
  letter-spacing: -0.02em;
  margin-bottom: 6px;
}
.pro-hero-stat-label {
  font-size: 12px;
  color: #8b8ba8;
  line-height: 1.4;
  letter-spacing: 0.02em;
}

.pro-hero-steps {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 10px;
  margin-bottom: 8px;
}
.pro-hero-step {
  position: relative;
  padding: 22px 20px 20px;
  border-radius: 8px;
  background: #0f0f17;
  border: 1px solid rgba(255, 255, 255, 0.06);
  transition: border-color 0.18s ease;
}
.pro-hero-step:hover {
  border-color: rgba(245, 158, 11, 0.22);
}
.pro-hero-step-index {
  position: absolute;
  top: 14px;
  right: 18px;
  font-family: ui-monospace, "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: rgba(245, 158, 11, 0.6);
}
.pro-hero-step-icon {
  font-size: 22px;
  margin-bottom: 10px;
  opacity: 0.92;
}
.pro-hero-step-title {
  font-size: 15px;
  font-weight: 700;
  color: #f5f5fa;
  margin-bottom: 6px;
  letter-spacing: -0.01em;
}
.pro-hero-step-body {
  font-size: 13px;
  line-height: 1.55;
  color: #8b8ba8;
}
</style>
