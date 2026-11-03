import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getToken, saveToken } from '../lib/auth'
import { jsonResponse, mockApi, networkDown, renderApp, requestsMade } from '../test/helpers'
import Dashboard from './dashboard'
import customToaster from '../utils/customToaster'

vi.mock('../utils/customToaster', () => ({ default: vi.fn() }))

// Sunday 15 March 2026, noon.
const t = (id, cents, date, category_id = 1, type = 'debit', label = `Compra ${id}`) => ({ id, label, value: cents, transactioned_at: date, category_id, type })

const budgetOf = (month, budgeted, spent, unbudgeted = 0) => ({
  month,
  totals: { budgeted, spent, remaining: budgeted - spent, unbudgeted_spent: unbudgeted },
  groups: [],
})
const MARCH = 'GET /budgets?month=2026-03'
const FEBRUARY = 'GET /budgets?month=2026-02'

const ROUTES = {
  [MARCH]: { data: budgetOf('2026-03', 100000, 62000, 5000) }, // 620,00 spent of 1.000,00
  'GET /categories': { data: [{ id: 1, name: '🛒 Alimentação' }, { id: 2, name: '🚌 Transporte' }] },
  'GET /user/me': { data: { name: 'Clara Battesini', email: 'c@example.com' } },
  'POST /transactions': {
    data: [
      t(1, 10000, '2026-03-02T10:00:00'),
      t(2, 2550, '2026-03-14T10:00:00', 2),
      t(5, 50000, '2026-03-10T10:00:00', 1, 'credit'), // money coming in: not spending
      t(6, 10000, '2026-02-10T10:00:00'), // last month, before the 15th: what this month is compared with
      t(3, 99900, '2026-02-20T10:00:00'), // last month, after the 15th
      t(4, 5000, '2025-03-10T10:00:00'), // same month, previous year: must not count
    ],
  },
}

const plain = (text) => text.replace(/\s/g, ' ') // amounts use a non-breaking space
const monthTotal = () => plain(screen.getByLabelText('Total gasto no mês').textContent)
const card = (title) => screen.getByRole('heading', { name: title }).parentElement.parentElement

describe('dashboard', () => {
  beforeEach(() => {
    saveToken('tok')
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 2, 15, 12, 0, 0))
  })

  it('loads categories, transactions and the profile with the user token', async () => {
    const api = mockApi(ROUTES)

    renderApp(<Dashboard />)
    await screen.findByText(/Olá, /)

    expect(requestsMade(api).sort()).toEqual([MARCH, 'GET /categories', 'GET /user/me', 'POST /transactions'])
    expect(api.mock.calls.every(([, o]) => o.headers.Authorization === 'Bearer tok')).toBe(true)
  })

  it('greets the user by first name', async () => {
    mockApi(ROUTES)

    renderApp(<Dashboard />)

    expect(await screen.findByText(/Olá, Clara 👋/)).toBeInTheDocument()
  })

  it('shows this month\'s spending only, in reais, without the credits', async () => {
    mockApi(ROUTES)

    renderApp(<Dashboard />)

    await screen.findByText('Gastos')
    expect(monthTotal()).toBe('R$ 125,50') // 100,00 + 25,50
  })

  it('shows zero when there are no transactions', async () => {
    mockApi({ ...ROUTES, 'POST /transactions': { data: [] } })

    renderApp(<Dashboard />)

    await screen.findByText('Gastos')
    expect(monthTotal()).toBe('R$ 0,00')
  })

  it('still shows the page, with zero spending and no greeting, when the back-end cannot be reached', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    networkDown()

    renderApp(<Dashboard />)

    expect(await screen.findByText('Gastos')).toBeInTheDocument()
    expect(monthTotal()).toBe('R$ 0,00')
    expect(screen.queryByText(/Olá, /)).not.toBeInTheDocument()
  })

  it('shows a spinner until the data has loaded', async () => {
    mockApi(ROUTES)

    renderApp(<Dashboard />)

    expect(document.querySelector('.chakra-spinner')).toBeInTheDocument()
    expect(screen.queryByText('Gastos')).not.toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('Gastos')).toBeInTheDocument())
    expect(document.querySelector('.chakra-spinner')).not.toBeInTheDocument()
  })

  it('survives an expired session instead of showing a blank page', async () => {
    mockApi({
      'GET /categories': [{ detail: 'Token expired' }, 401],
      'POST /transactions': [{ detail: 'Token expired' }, 401],
      'GET /user/me': [{ detail: 'Token expired' }, 401],
      [MARCH]: [{ detail: 'Token expired' }, 401],
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})

    renderApp(<Dashboard />)

    // the login is forgotten and the user is sent to log in again, without an extra error message
    await waitFor(() => expect(getToken()).toBeNull())
    expect(window.location.hash).toBe('#/login-google')
    expect(customToaster).not.toHaveBeenCalled()
  })

  it('tells the user when the data could not be loaded', async () => {
    mockApi({ 'GET /categories': [{ detail: 'boom' }, 500], 'POST /transactions': [{ detail: 'boom' }, 500], 'GET /user/me': ROUTES['GET /user/me'], [MARCH]: ROUTES[MARCH] })
    vi.spyOn(console, 'error').mockImplementation(() => {})

    renderApp(<Dashboard />)

    await waitFor(() => expect(customToaster).toHaveBeenCalledWith('Error', 'error', expect.any(String)))
    expect(monthTotal()).toBe('R$ 0,00') // the page still shows, with zero spending
  })

  it('shows how much is left of the month\'s plan', async () => {
    mockApi(ROUTES)

    renderApp(<Dashboard />)

    const panel = within(await waitFor(() => card('Orçamento')))
    await panel.findByText('R$ 380,00') // 1.000,00 - 620,00
    expect(panel.getByText('restantes')).toBeInTheDocument()
    expect(plain(panel.getByText(/gastos de/).textContent)).toBe('R$ 620,00 gastos de R$ 1.000,00')
    expect(plain(panel.getByText(/sem orçamento/).textContent)).toBe('+ R$ 50,00 em categorias sem orçamento')
    expect(panel.getByRole('img', { name: '62% do orçamento gasto' })).toBeInTheDocument()
  })

  it('says how much the plan was exceeded by', async () => {
    mockApi({ ...ROUTES, [MARCH]: { data: budgetOf('2026-03', 100000, 120000) } })

    renderApp(<Dashboard />)

    const panel = within(await waitFor(() => card('Orçamento')))
    await panel.findByText('acima do orçamento')
    expect(panel.getByText('R$ 200,00')).toBeInTheDocument()
    expect(panel.getByRole('img', { name: '100% do orçamento gasto' })).toBeInTheDocument()
  })

  it('invites the user to plan when nothing is planned for the month', async () => {
    mockApi({ ...ROUTES, [MARCH]: { data: budgetOf('2026-03', 0, 0) } })

    renderApp(<Dashboard />)

    const panel = within(await waitFor(() => card('Orçamento')))
    expect(await panel.findByText(/Nenhum orçamento definido/)).toBeInTheDocument()
    expect(panel.getByRole('link', { name: 'Definir orçamentos' })).toHaveAttribute('href', '/budgets')
  })

  it('still shows the rest of the page, without an error message, when the budgets cannot be loaded', async () => {
    mockApi({ ...ROUTES, [MARCH]: [{ detail: 'boom' }, 500] })
    vi.spyOn(console, 'error').mockImplementation(() => {})

    renderApp(<Dashboard />)

    expect(await screen.findByText('Não foi possível carregar os orçamentos.')).toBeInTheDocument()
    expect(monthTotal()).toBe('R$ 125,50')
    expect(customToaster).not.toHaveBeenCalled()
  })

  it('does not wait forever for the plan when there is no login', async () => {
    const api = mockApi(ROUTES)
    localStorage.clear()

    renderApp(<Dashboard />)

    expect(await screen.findByText('Não foi possível carregar os orçamentos.')).toBeInTheDocument()
    expect(requestsMade(api)).not.toContain(MARCH)
  })

  it('compares the month with the one before, up to the same day', async () => {
    mockApi(ROUTES)

    renderApp(<Dashboard />)

    await screen.findByText('Gastos')
    // 125,50 against 100,00 by the 15th of February (the 20th does not count yet)
    expect(plain(screen.getByText(/a mais que/).textContent)).toBe('▲ 26% a mais que fevereiro até o dia 15')
  })

  it('lists the latest spending of the month, newest first, with the emoji of the category', async () => {
    mockApi(ROUTES)

    renderApp(<Dashboard />)

    const list = await screen.findByRole('list', { name: 'Últimas transações' })
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(2) // not the credit, not February
    expect(items[0]).toHaveTextContent('Compra 2')
    expect(items[0]).toHaveTextContent('🚌')
    expect(plain(items[0].textContent)).toContain('R$ 25,50')
    expect(items[1]).toHaveTextContent('Compra 1')
    expect(items[1]).toHaveTextContent('🛒')
  })

  it('lists at most six transactions', async () => {
    const many = [1, 2, 3, 4, 5, 6, 7, 8].map((id) => t(id, 100, `2026-03-0${id}T10:00:00`))
    mockApi({ ...ROUTES, 'POST /transactions': { data: many } })

    renderApp(<Dashboard />)

    const list = await screen.findByRole('list', { name: 'Últimas transações' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(6)
    expect(within(list).queryByText('Compra 1')).not.toBeInTheDocument() // the oldest ones are left out
  })

  it('ranks the categories by this month\'s spending only', async () => {
    mockApi({
      ...ROUTES,
      'POST /transactions': {
        data: [
          t(1, 10000, '2026-03-02T10:00:00'),
          t(2, 2550, '2026-03-14T10:00:00', 2),
          t(3, 99900, '2026-02-20T10:00:00', 2), // last month: would put Transporte first
          t(4, 50000, '2026-03-10T10:00:00', 1, 'credit'), // a credit: would add to Alimentação
        ],
      },
    })

    renderApp(<Dashboard />)

    await screen.findByText('Principais categorias')
    // the chart prints compact numbers: 100,00 -> "100", 25,50 -> "25.5"
    expect(screen.getByText('100')).toBeInTheDocument()
    expect(screen.getByText('25.5')).toBeInTheDocument()
  })

  describe('transfers and income are not spending', () => {
    const GROUPED = {
      ...ROUTES,
      'GET /categories': {
        data: [
          { id: 1, name: '🛒 Alimentação', group_name: 'Alimentação' },
          { id: 2, name: '🚌 Transporte', group_name: 'Auto e Transporte' },
          { id: 3, name: '💳 Pagamento de fatura do cartão', group_name: 'Transferências' },
          { id: 4, name: '💰 Salário', group_name: 'Receitas' },
        ],
      },
      'POST /transactions': {
        data: [
          t(1, 10000, '2026-03-02T10:00:00'),
          t(2, 2550, '2026-03-14T10:00:00', 2),
          t(3, 777700, '2026-03-12T10:00:00', 3, 'debit', 'Fatura'), // paying the card bill: a debit, but not spending
          t(4, 555500, '2026-03-12T10:00:00', 3, 'credit'), // the other side of a transfer
          t(5, 300000, '2026-03-05T10:00:00', 4, 'credit'), // salary
          t(6, 40000, '2026-03-06T10:00:00', 4, 'debit', 'Ajuste'), // a debit in an income category
          t(7, 888800, '2026-02-12T10:00:00', 3), // last month's card bill: must not make the comparison look huge
        ],
      },
    }

    it('counts only what was really spent in the total of the month', async () => {
      mockApi(GROUPED)

      renderApp(<Dashboard />)

      await waitFor(() => expect(monthTotal()).toBe('R$ 125,50')) // 100,00 + 25,50, none of the 7.777,00 of the bill
    })

    it('leaves them out of the recent list too', async () => {
      mockApi(GROUPED)

      renderApp(<Dashboard />)

      await screen.findByText('Compra 1')
      expect(screen.queryByText('Fatura')).not.toBeInTheDocument()
      expect(screen.queryByText('Ajuste')).not.toBeInTheDocument()
    })

    it('leaves them out of the ranking of categories', async () => {
      mockApi(GROUPED)

      renderApp(<Dashboard />)

      await screen.findByText('Principais categorias')
      expect(screen.getByText('100')).toBeInTheDocument()
      expect(screen.getByText('25.5')).toBeInTheDocument()
      expect(screen.queryByText(/Pagamento de fatura/)).not.toBeInTheDocument()
    })

    it('agrees with the budget, which leaves the same groups out', async () => {
      mockApi({ ...GROUPED, [MARCH]: { data: budgetOf('2026-03', 100000, 12550) } })

      renderApp(<Dashboard />)

      await waitFor(() => expect(monthTotal()).toBe('R$ 125,50'))
      const panel = within(await waitFor(() => card('Orçamento')))
      expect(plain((await panel.findByText(/gastos de/)).textContent)).toBe('R$ 125,50 gastos de R$ 1.000,00') // the same amount
    })
  })

  describe('what came in and what went out', () => {
    const text = (label) => plain(screen.getByLabelText(label).textContent)
    const FLOW = {
      ...ROUTES,
      'GET /categories': {
        data: [
          { id: 1, name: '🛒 Alimentação', group_name: 'Alimentação' },
          { id: 3, name: '💳 Fatura', group_name: 'Transferências' },
          { id: 4, name: '💰 Salário', group_name: 'Receitas' },
        ],
      },
      'POST /transactions': {
        data: [
          t(1, 10000, '2026-03-02T10:00:00'), // out
          t(2, 2550, '2026-03-14T10:00:00'), // out
          t(3, 300000, '2026-03-05T10:00:00', 4, 'credit'), // salary: in
          t(4, 5000, '2026-03-08T10:00:00', 1, 'credit'), // a refund: in
          t(5, 777700, '2026-03-12T10:00:00', 3, 'debit'), // card bill: neither
          t(6, 555500, '2026-03-12T10:00:00', 3, 'credit'), // the other side of the transfer: neither
          t(7, 99900, '2026-02-10T10:00:00', 4, 'credit'), // last month's salary
          t(8, 20000, '2026-02-11T10:00:00'), // last month's spending
        ],
      },
    }

    it('shows the entries, the exits and the balance of the month', async () => {
      mockApi(FLOW)

      renderApp(<Dashboard />)

      await waitFor(() => expect(text('Entradas do mês')).toBe('R$ 3.050,00')) // 3.000,00 salary + 50,00 refund
      expect(text('Saídas do mês')).toBe('R$ 125,50') // 100,00 + 25,50
      expect(text('Saldo do mês')).toBe('R$ 2.924,50')
    })

    it('leaves transfers out of both sides', async () => {
      mockApi(FLOW)

      renderApp(<Dashboard />)

      await waitFor(() => expect(text('Entradas do mês')).toBe('R$ 3.050,00')) // not 8.605,00
      expect(text('Saídas do mês')).not.toContain('7.777')
    })

    it('follows the month chosen', async () => {
      mockApi({ ...FLOW, [FEBRUARY]: { data: budgetOf('2026-02', 0, 0) } })
      renderApp(<Dashboard />)
      await waitFor(() => expect(text('Entradas do mês')).toBe('R$ 3.050,00'))

      await userEvent.click(screen.getByRole('button', { name: 'Mês anterior' }))

      await waitFor(() => expect(text('Entradas do mês')).toBe('R$ 999,00'))
      expect(text('Saídas do mês')).toBe('R$ 200,00')
      expect(text('Saldo do mês')).toBe('R$ 799,00')
    })

    it('shows zeros for a month with nothing in it', async () => {
      mockApi({ ...FLOW, 'POST /transactions': { data: [] } })

      renderApp(<Dashboard />)

      await waitFor(() => expect(text('Entradas do mês')).toBe('R$ 0,00'))
      expect(screen.getByText('Nenhuma entrada ou saída neste mês.')).toBeInTheDocument()
    })

    it('comes right after the budget in the left column, before the chart', async () => {
      mockApi(FLOW)

      renderApp(<Dashboard />)

      const [budget, flow, chart] = await Promise.all(
        ['Orçamento', 'Entradas e saídas', 'Gastos'].map((title) => screen.findByRole('heading', { name: title })),
      )
      expect(budget.compareDocumentPosition(flow) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
      expect(flow.compareDocumentPosition(chart) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })
  })

  describe('month switcher', () => {
    it('starts on the current month and cannot go past it', async () => {
      mockApi(ROUTES)

      renderApp(<Dashboard />)

      await screen.findByText('Gastos')
      expect(screen.getByRole('heading', { name: 'março de 2026' })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Próximo mês' })).toBeDisabled()
    })

    it('moves every panel to the previous month', async () => {
      const api = mockApi({ ...ROUTES, [FEBRUARY]: { data: budgetOf('2026-02', 200000, 150000) } })
      const user = userEvent.setup()

      renderApp(<Dashboard />)
      await screen.findByText('Gastos')
      await user.click(screen.getByRole('button', { name: 'Mês anterior' }))

      expect(screen.getByRole('heading', { name: 'fevereiro de 2026' })).toBeInTheDocument()
      expect(monthTotal()).toBe('R$ 1.099,00') // 999,00 + 100,00
      expect(await within(card('Orçamento')).findByText('R$ 500,00')).toBeInTheDocument() // 2.000,00 - 1.500,00
      expect(requestsMade(api)).toContain('GET /budgets?month=2026-02')
      const list = screen.getByRole('list', { name: 'Últimas transações' })
      expect(within(list).getAllByRole('listitem')).toHaveLength(2) // the two of February
      expect(within(list).queryByText('Compra 1')).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Próximo mês' })).toBeEnabled()
    })

    it('does not ask for the transactions again', async () => {
      const api = mockApi({ ...ROUTES, [FEBRUARY]: { data: budgetOf('2026-02', 0, 0) } })
      const user = userEvent.setup()

      renderApp(<Dashboard />)
      await screen.findByText('Gastos')
      await user.click(screen.getByRole('button', { name: 'Mês anterior' }))

      expect(requestsMade(api).filter((r) => r === 'POST /transactions')).toHaveLength(1)
    })

    it('ignores a late answer for a month that is no longer on the page', async () => {
      let answerFebruary
      mockApi({
        ...ROUTES,
        [FEBRUARY]: () => new Promise((resolve) => (answerFebruary = () => resolve(jsonResponse({ data: budgetOf('2026-02', 200000, 150000) })))),
      })
      const user = userEvent.setup()

      renderApp(<Dashboard />)
      await screen.findByText('Gastos')
      await user.click(screen.getByRole('button', { name: 'Mês anterior' }))
      await user.click(screen.getByRole('button', { name: 'Próximo mês' }))
      await within(card('Orçamento')).findByText('R$ 380,00') // March is back
      answerFebruary()
      await act(async () => {})

      expect(within(card('Orçamento')).getByText('R$ 380,00')).toBeInTheDocument()
      expect(within(card('Orçamento')).queryByText('R$ 500,00')).not.toBeInTheDocument()
    })
  })
})
