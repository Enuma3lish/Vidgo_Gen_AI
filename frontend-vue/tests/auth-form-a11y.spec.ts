import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createI18n } from 'vue-i18n'
import { createRouter, createMemoryHistory } from 'vue-router'
import { createPinia } from 'pinia'
import en from '@/locales/en.json'

// reCAPTCHA v3 loads a remote script and is irrelevant to markup a11y — stub it
// so mounting the auth forms stays offline and deterministic.
vi.mock('@/composables/useRecaptcha', () => ({
  useRecaptcha: () => ({ execute: vi.fn().mockResolvedValue('') }),
}))

import Register from '@/views/auth/Register.vue'
import Login from '@/views/auth/Login.vue'

function blank() {
  return { template: '<div />' }
}

async function mountView(component: unknown, path: string) {
  const i18n = createI18n({ legacy: false, locale: 'en', fallbackLocale: 'en', messages: { en } })
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'home', component: blank() },
      { path: '/auth/login', name: 'login', component: blank() },
      { path: '/auth/register', name: 'register', component: blank() },
      { path: '/auth/forgot-password', name: 'forgot-password', component: blank() },
      { path: '/auth/verify', name: 'verify', component: blank() },
    ],
  })
  router.push(path)
  await router.isReady()
  return mount(component as never, { global: { plugins: [i18n, router, createPinia()] } })
}

describe('auth-form-a11y', () => {
  it('Register: labelled inputs, minlength password, autocomplete, novalidate, alert wiring', async () => {
    const wrapper = await mountView(Register, '/auth/register')

    const form = wrapper.find('form')
    expect(form.exists()).toBe(true)
    expect(form.attributes('novalidate')).toBeDefined()

    for (const id of ['register-email', 'register-password', 'promotion-code']) {
      expect(wrapper.find(`#${id}`).exists(), `#${id} input`).toBe(true)
      expect(wrapper.find(`label[for="${id}"]`).exists(), `<label for="${id}">`).toBe(true)
    }

    const email = wrapper.find('#register-email')
    expect(email.attributes('type')).toBe('email')
    expect(email.attributes('autocomplete')).toBe('email')
    expect(email.attributes('aria-describedby')).toBe('register-email-error')

    const password = wrapper.find('#register-password')
    expect(password.attributes('minlength')).toBe('8')
    expect(password.attributes('autocomplete')).toBe('new-password')
    expect(password.attributes('aria-describedby')).toBe('register-password-error')

    // Icon-only show/hide toggle must have an accessible name.
    expect(wrapper.find('button[type="button"]').attributes('aria-label')).toBeTruthy()
  })

  it('Register: empty submit surfaces role="alert" errors and flips aria-invalid', async () => {
    const wrapper = await mountView(Register, '/auth/register')

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(wrapper.findAll('[role="alert"]').length).toBeGreaterThan(0)
    expect(wrapper.find('#register-email').attributes('aria-invalid')).toBe('true')
    expect(wrapper.find('#register-password').attributes('aria-invalid')).toBe('true')
  })

  it('Login: labelled inputs, autocomplete, novalidate, accessible password toggle', async () => {
    const wrapper = await mountView(Login, '/auth/login')

    expect(wrapper.find('form').attributes('novalidate')).toBeDefined()

    for (const id of ['email', 'password']) {
      expect(wrapper.find(`#${id}`).exists(), `#${id} input`).toBe(true)
      expect(wrapper.find(`label[for="${id}"]`).exists(), `<label for="${id}">`).toBe(true)
    }

    expect(wrapper.find('#email').attributes('autocomplete')).toBe('email')
    expect(wrapper.find('#password').attributes('autocomplete')).toBe('current-password')
    expect(wrapper.find('button[type="button"]').attributes('aria-label')).toBeTruthy()
  })
})
