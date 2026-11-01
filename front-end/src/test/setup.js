import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach, vi } from 'vitest'

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
  // Nothing may reach a real server: every test that needs the API mocks fetch itself.
  vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('Network access is blocked in tests: mock fetch'))))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.unstubAllEnvs()
  vi.useRealTimers()
  vi.restoreAllMocks()
})
