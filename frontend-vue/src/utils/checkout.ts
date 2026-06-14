/**
 * Checkout redirect helpers.
 *
 * When a guest clicks "Subscribe" or "Buy credits" on /pricing we bounce them
 * through /auth/login and then drop them back onto the exact plan / credit pack
 * they chose, so they don't have to hunt for the same card again after signing
 * in. Pricing.vue builds the redirect with these helpers and replays it on
 * mount via `route.query.redirect`.
 *
 * Extracted into pure functions so the redirect contract is unit-testable
 * without mounting the whole Pricing view.
 */

export type PaymentMethod = 'paypal' | 'ecpay'
export type BillingPeriod = 'monthly' | 'yearly'

/** Return path that resumes a plan subscription after login. */
export function subscribeRedirect(
  planName: string,
  billing: BillingPeriod,
  payment: PaymentMethod,
): string {
  return `/pricing?plan=${encodeURIComponent(planName)}&billing=${billing}&payment=${payment}`
}

/** Return path that resumes a credit-pack purchase after login. */
export function creditPackRedirect(packName: string, payment: PaymentMethod): string {
  return `/pricing?pack=${encodeURIComponent(packName)}&payment=${payment}#credit-packs`
}

/** router.push() target that sends a guest to login carrying a return path. */
export function loginWithRedirect(redirect: string) {
  return { path: '/auth/login', query: { redirect } } as const
}
