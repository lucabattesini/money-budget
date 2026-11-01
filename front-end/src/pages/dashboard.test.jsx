import { screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { mockApi, renderApp, requestsMade } from '../test/helpers'
import Dashboard from './dashboard'

// Sunday 15 March 2026, noon.
const t = (id, cents, date, category_id = 1) => ({ id, label: 'x', value: cents, date, category_id })

const ROUTES = {
  'GET /categories': { data: [{ id: 1, name: 'Alimentação' }, { id: 2, name: 'Transporte' }] },
  'GET /user/me': { data: { name: 'Clara Battesini', email: 'c@example.com' } },
  'POST /transactions': {
    data: [
      t(1, 10000, '2026-03-02T10:00:00'),
      t(2, 2550, '2026-03-14T10:00:00', 2),
      t(3, 99900, '2026-02-20T10:00:00'), // last month: must not count
      t(4, 5000, '2025-03-10T10:00:00'), // same month, previous year: must not count
    ],
  },
}

const monthTotal = () => screen.getByText(/^R\$/).textContent.replace(/\s/g, ' ')

describe('dashboard', () => {
  beforeEach(() => {
    saveToken('tok')
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 2, 15, 12, 0, 0))
  })

  it('loads categories, transactions and the profile with the user token', async () => {
    const api = mockApi(ROUTES)

    renderApp(<Dashboard />)
    await screen.findByText(/Bem-vindo de volta/)

    expect(requestsMade(api).sort()).toEqual(['GET /categories', 'GET /user/me', 'POST /transactions'])
    expect(api.mock.calls.every(([, o]) => o.headers.Authorization === 'Bearer tok')).toBe(true)
  })

  it('greets the user by first name', async () => {
    mockApi(ROUTES)

    renderApp(<Dashboard />)

    expect(await screen.findByText(/Bem-vindo de volta, Clara 👋/)).toBeInTheDocument()
  })

  it('shows this month\'s spending only, in reais, labelled with the month name', async () => {
    mockApi(ROUTES)

    renderApp(<Dashboard />)

    expect(await screen.findByText('Gastos de março')).toBeInTheDocument()
    expect(monthTotal()).toBe('R$ 125,50') // 100,00 + 25,50
  })

  it('shows zero when there are no transactions', async () => {
    mockApi({ ...ROUTES, 'POST /transactions': { data: [] } })

    renderApp(<Dashboard />)

    await screen.findByText('Gastos de março')
    expect(monthTotal()).toBe('R$ 0,00')
  })

  it('still shows the page, with zero spending and no greeting, when the back-end cannot be reached', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    // every request fails (the default test fetch rejects)

    renderApp(<Dashboard />)

    expect(await screen.findByText('Gastos de março')).toBeInTheDocument()
    expect(monthTotal()).toBe('R$ 0,00')
    expect(screen.queryByText(/Bem-vindo de volta/)).not.toBeInTheDocument()
  })

  it('shows a spinner until the data has loaded', async () => {
    mockApi(ROUTES)

    renderApp(<Dashboard />)

    expect(screen.queryByText('Gastos de março')).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('Gastos de março')).toBeInTheDocument())
  })
})
