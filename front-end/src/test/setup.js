import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'
import { strayRequests } from './helpers'
import { resetLocale } from '../lib/locale'

// jsdom lacks these browser APIs; Chakra UI, recharts and the chatbot use them.
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.matchMedia ??= (query) => ({
  matches: false,
  media: query,
  onchange: null,
  addListener() {},
  removeListener() {},
  addEventListener() {},
  removeEventListener() {},
  dispatchEvent: () => false,
})
Element.prototype.scrollIntoView ??= function scrollIntoView() {}

beforeEach(() => {
  localStorage.clear()
  resetLocale() // the family's currency and language are global: every test starts with reais and Portuguese
  // Nothing may reach a real server: every test that needs the API mocks fetch itself.
  strayRequests.length = 0
  vi.stubGlobal('fetch', vi.fn((url, options = {}) => {
    strayRequests.push(`${(options.method || 'GET').toUpperCase()} ${url}`)
    return Promise.reject(new Error('Network access is blocked in tests: mock fetch'))
  }))
})

afterEach(() => {
  const stray = [...strayRequests]
  strayRequests.length = 0
  cleanup()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  vi.useRealTimers()
  vi.restoreAllMocks()

  if (stray.length) {
    throw new Error(
      `The test made requests it did not declare (use mockApi, or networkDown() on purpose):\n  ${stray.join('\n  ')}`,
    )
  }
})
