// Shared helper for the "custom prompt → subscription + bound card" gate.
//
// Backend (app/api/v1/tools.py) returns success:false with
// error_code "subscription_card_required" when a non-eligible account
// (no active paid subscription with a bound card, and not an admin/test
// account) submits a CUSTOM or edited prompt. Free accounts may still run
// an UNMODIFIED dropdown preset, which the backend serves as a cached
// example. This helper detects that block so every tool can react the
// same way: show the bilingual message and point the user at /pricing.
import type { Router } from 'vue-router'

// Minimal structural shape so this works for any tool response that carries
// the gate fields (ToolResponse from tools.ts AND GenerationResponse from
// generation.ts).
interface GateResult {
  error_code?: string
  message?: string
}

export const CARD_REQUIRED_CODE = 'subscription_card_required'

export function isCardRequired(result: unknown): boolean {
  return Boolean(
    result &&
    typeof result === 'object' &&
    (result as GateResult).error_code === CARD_REQUIRED_CODE,
  )
}

interface UiLike {
  showInfo: (msg: string) => void
}

/**
 * If `result` is the subscription/card block, surface the CTA (toast +
 * redirect to pricing) and return true so the caller can stop. Otherwise
 * return false and let the caller handle the result normally.
 */
export function handleCardRequired(
  result: GateResult | undefined | null,
  ui: UiLike,
  router: Router,
  isZh: boolean,
): boolean {
  if (!isCardRequired(result)) return false
  ui.showInfo(
    result?.message ||
      (isZh
        ? '自訂提示詞需要訂閱並綁定信用卡。免費帳號可使用範例下拉選單。'
        : 'Custom prompts require a subscription with a bound card. Free accounts can use the example presets.'),
  )
  router.push('/pricing')
  return true
}
