import { vi } from 'vitest'

// Requests the test did not declare. setup.js fails the test in afterEach if any were made,
// because the app swallows network errors and would otherwise carry on as if the server were down.
export const strayRequests = []
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { Provider } from '../components/ui/provider'
import { Toaster } from '../components/ui/toaster'

/** Shows the current route, so tests can assert where the app navigated to. */
export function LocationDisplay() {
  const location = useLocation()
  return <div data-testid="location">{location.pathname + location.search}</div>
}

/** Render a component inside the Chakra provider and a router, with the toast area the app layout provides. */
export function renderApp(ui, { route = '/' } = {}) {
  return render(
    <Provider>
      <MemoryRouter initialEntries={[route]}>
        <Toaster />
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
      strayRequests.push(`${method} ${path}`)
      return Promise.reject(new Error(`Unexpected request in test: ${method} ${path}`))
    }
    if (typeof handler === 'function') return handler(url, options)
    if (Array.isArray(handler)) return jsonResponse(handler[0], handler[1])
    return jsonResponse(handler)
  })
  vi.stubGlobal('fetch', mock)
  return mock
}

/** Simulate the back-end being unreachable: every request fails, and that is expected. */
export function networkDown() {
  const mock = vi.fn(() => Promise.reject(new TypeError('Failed to fetch')))
  vi.stubGlobal('fetch', mock)
  return mock
}

/** Requests made so far, as "METHOD /path" strings. */
export function requestsMade(mock) {
  return mock.mock.calls.map(([url, options = {}]) =>
    `${(options.method || 'GET').toUpperCase()} ${String(url).replace('http://api.test', '')}`,
  )
}

/**
 * Choose a category in the shared category picker: open it from its box (by its label, "Categoria" for example) and click
 * the option. The list is only in the page while it is open.
 */
export async function chooseCategory(label, optionName) {
  await userEvent.click(typeof label === 'string' ? screen.getByRole('combobox', { name: label }) : label)
  await userEvent.click(await screen.findByRole('option', { name: optionName }))
}
