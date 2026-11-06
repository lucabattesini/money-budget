import { afterEach, describe, expect, it, vi } from 'vitest'
import { registerServiceWorker } from './pwa'

describe('registerServiceWorker', () => {
  afterEach(() => vi.unstubAllEnvs())

  it('does not register in development, where it would keep serving old files', () => {
    const register = vi.fn().mockResolvedValue()
    Object.defineProperty(navigator, 'serviceWorker', { value: { register }, configurable: true })
    vi.stubEnv('PROD', false)

    registerServiceWorker()
    window.dispatchEvent(new Event('load'))

    expect(register).not.toHaveBeenCalled()
  })

  it('registers /sw.js in the built app once the page has loaded', () => {
    const register = vi.fn().mockResolvedValue()
    Object.defineProperty(navigator, 'serviceWorker', { value: { register }, configurable: true })
    vi.stubEnv('PROD', true)

    registerServiceWorker()
    window.dispatchEvent(new Event('load'))

    expect(register).toHaveBeenCalledWith('/sw.js')
  })
})
