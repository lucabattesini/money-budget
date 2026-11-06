import { afterEach, describe, expect, it, vi } from 'vitest'

describe('API address', () => {
  afterEach(() => {
    vi.resetModules()
  })

  it('uses VITE_API_URL when it is set', async () => {
    vi.stubEnv('VITE_API_URL', 'https://api.example.com')
    vi.resetModules()

    const { API_URL } = await import('./config')
    const { endpoints } = await import('./endpoints')

    expect(API_URL).toBe('https://api.example.com')
    expect(endpoints.categories).toBe('https://api.example.com/categories')
  })

  it('falls back to the local development address instead of "undefined"', async () => {
    vi.stubEnv('VITE_API_URL', '')
    vi.resetModules()

    const { endpoints } = await import('./endpoints')

    expect(endpoints.categories).toBe('http://localhost:8000/categories')
    expect(endpoints.transactions).not.toContain('undefined')
  })

  it('in the production build, with no address set, uses the page\'s own address (the API serves the app)', async () => {
    vi.stubEnv('VITE_API_URL', '')
    vi.stubEnv('PROD', true)
    vi.resetModules()

    const { endpoints } = await import('./endpoints')

    expect(endpoints.categories).toBe('/categories')
    expect(endpoints.transactions).not.toContain('localhost')
  })
})
