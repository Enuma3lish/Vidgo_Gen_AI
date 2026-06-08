import { describe, it, expect } from 'vitest'
import { subscribeRedirect, creditPackRedirect, loginWithRedirect } from '@/utils/checkout'

// A guest who clicks "Subscribe" / "Buy credits" on /pricing must be bounced
// through /auth/login and then dropped back onto the exact plan or pack they
// chose. These helpers build that round-trip; Pricing.vue calls them and replays
// route.query.redirect on mount. Breaking the URL shape silently strands paying
// users on a blank pricing page after login, so we pin the contract here.

describe('pricing-redirect', () => {
  it('subscribeRedirect carries plan, billing and payment back to /pricing', () => {
    expect(subscribeRedirect('pro', 'yearly', 'paypal')).toBe(
      '/pricing?plan=pro&billing=yearly&payment=paypal',
    )
  })

  it('creditPackRedirect carries pack + payment and targets the #credit-packs anchor', () => {
    expect(creditPackRedirect('standard_pack', 'ecpay')).toBe(
      '/pricing?pack=standard_pack&payment=ecpay#credit-packs',
    )
  })

  it('URL-encodes plan / pack names with spaces or special characters', () => {
    expect(subscribeRedirect('Test Pro $1', 'monthly', 'ecpay')).toBe(
      '/pricing?plan=Test%20Pro%20%241&billing=monthly&payment=ecpay',
    )
    expect(creditPackRedirect('A&B', 'paypal')).toBe('/pricing?pack=A%26B&payment=paypal#credit-packs')
  })

  it('loginWithRedirect bounces a guest to /auth/login carrying the return path', () => {
    const redirect = subscribeRedirect('pro', 'monthly', 'ecpay')
    expect(loginWithRedirect(redirect)).toEqual({
      path: '/auth/login',
      query: { redirect: '/pricing?plan=pro&billing=monthly&payment=ecpay' },
    })
  })
})
