import { vi } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { Provider } from '../components/ui/provider'

/** Shows the current route, so tests can assert where the app navigated to. */
export function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}

/** Render a component inside the Chakra provider and a router. */
export function renderApp(ui, { route = '/' } = {}) {
  return render(
    <Provider>
      <MemoryRouter initialEntries={[route]}>
        {ui}
        <LocationDisplay />
      </MemoryRouter>
    </Provider>,
  )
}

/** A fetch() response with a JSON body. */
export function jsonResponse(body, status = 200) {
  return Promise.resolve(
    new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }),
  )
}

/**
 * Route-based fetch mock: `routes` maps "METHOD /path" (relative to the API) to
 * a response body, a [body, status] pair or a function returning a Promise.
 * Unmatched requests fail loudly. Returns the mock so tests can inspect calls.
 */
export function mockApi(routes) {
  const mock = vi.fn((url, options = {}) => {
    const method = (options.method || 'GET').toUpperCase()
    const path = String(url).replace('http://api.test', '')
    const handler = routes[`${method} ${path}`]
    if (handler === undefined) {
      return Promise.reject(new Error(`Unexpected request in test: ${method} ${path}`))
    }
    if (typeof handler === 'function') return handler(url, options)
    if (Array.isArray(handler)) return jsonResponse(handler[0], handler[1])
    return jsonResponse(handler)
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

/** Requests made so far, as "METHOD /path" strings. */
export function requestsMade(mock) {
  return mock.mock.calls.map(([url, options = {}]) =>
    `${(options.method || 'GET').toUpperCase()} ${String(url).replace('http://api.test', '')}`,
  )
}
