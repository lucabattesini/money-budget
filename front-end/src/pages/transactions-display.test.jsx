import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { jsonResponse, mockApi, renderApp, requestsMade } from '../test/helpers'
import TransactionsDisplay from './transactions-display'

// Sunday 15 March 2026, noon: "today" starts 15 March 00:00, "this week" 8 March, "this month" 1 March.
const CATEGORIES = { data: [{ id: 1, name: 'Alimentação' }, { id: 2, name: 'Transporte' }] }
const t = (id, label, cents, date, category_id = 1) => ({ id, label, value: cents, date, category_id })

// Deliberately NOT in group order: the page itself must put today first and the oldest last.
const TRANSACTIONS = {
  data: [
    t(4, 'Presente', 5000, '2026-02-20T10:00:00', 99), // category that no longer exists
    t(3, 'Mercado', 12000, '2026-03-02T10:00:00'),
    t(2, 'Uber', 1800, '2026-03-10T18:00:00', 2),
    t(1, 'Almoço', 2550, '2026-03-15T09:00:00'),
  ],
}

const GROUP_TITLES = ['Hoje', 'Esta Semana', 'Este Mês', 'Todo o Resto']
const cardOf = (label) => screen.getByText(label).closest('.chakra-card__root')
const groupOf = (label) => GROUP_TITLES.find((title) => within(cardOf(label).parentElement).queryByText(title))
const cardsOnPage = () => [...document.querySelectorAll('.chakra-card__root')]

const routes = (transactions = TRANSACTIONS) => ({
  'GET /categories': CATEGORIES,
  'POST /transactions': transactions,
})


describe('transactions page', () => {
  beforeEach(() => {
    saveToken('tok')
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 2, 15, 12, 0, 0))
  })

  it('asks for the categories and for all transactions, with the user token', async () => {
    const api = mockApi(routes())

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    expect(requestsMade(api).sort()).toEqual(['GET /categories', 'POST /transactions'])
    const post = api.mock.calls.find(([, o]) => o.method === 'post')
    expect(JSON.parse(post[1].body)).toEqual({ organized_by: null, date: null })
    expect(post[1].headers.Authorization).toBe('Bearer tok')
  })

  it('shows each transaction with its label, amount in reais and category name', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)

    await screen.findByText('Almoço')
    const card = cardOf('Almoço')
    expect(within(card).getByText(/25[.,]5/)).toBeInTheDocument() // 2550 cents, shown in reais (format: see TKT-32)
    expect(within(card).getByText('Alimentação')).toBeInTheDocument()
    expect(within(card).getByText('15/03/2026')).toBeInTheDocument()
  })

  it('groups transactions into today, this week, this month and older, in that order', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    const labels = ['Almoço', 'Uber', 'Mercado', 'Presente']
    expect(cardsOnPage().map((card) => labels.find((l) => card.textContent.includes(l)))).toEqual(labels)
    expect(labels.map(groupOf)).toEqual(['Hoje', 'Esta Semana', 'Este Mês', 'Todo o Resto'])
  })

  it.each([
    // [label, date, group it must appear in]
    ['today start', '2026-03-15T00:00:00', 'Hoje'],
    ['just before today', '2026-03-14T23:59:00', 'Esta Semana'],
    ['week start', '2026-03-08T00:00:00', 'Esta Semana'],
    ['just before the week', '2026-03-07T23:59:00', 'Este Mês'],
    ['month start', '2026-03-01T00:00:00', 'Este Mês'],
    ['just before the month', '2026-02-28T23:59:00', 'Todo o Resto'],
  ])('puts the "%s" transaction (%s) in "%s"', async (label, date, group) => {
    mockApi(routes({ data: [t(1, label, 1000, date)] }))

    renderApp(<TransactionsDisplay />)

    const card = (await screen.findByText(label)).closest('.chakra-card__root')
    expect(within(card.parentElement).getByText(group)).toBeInTheDocument()
  })

  it('names the category, or says it was not found', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)

    await screen.findByText('Presente')
    expect(within(cardOf('Presente')).getByText('Categoria não encontrada')).toBeInTheDocument()
    expect(within(cardOf('Uber')).getByText('Transporte')).toBeInTheDocument()
  })

  it('only shows the groups that have transactions', async () => {
    mockApi(routes({ data: [t(1, 'Almoço', 2550, '2026-03-15T09:00:00')] }))

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    expect(screen.queryByText('Esta Semana')).not.toBeInTheDocument()
    expect(screen.queryByText('Todo o Resto')).not.toBeInTheDocument()
  })

  it('shows no cards when there are no transactions', async () => {
    const api = mockApi(routes({ data: [] }))

    renderApp(<TransactionsDisplay />)

    expect(document.querySelector('.chakra-spinner')).toBeInTheDocument()
    await waitFor(() => expect(document.querySelector('.chakra-spinner')).not.toBeInTheDocument())
    expect(api).toHaveBeenCalledTimes(2) // the data really arrived: this is not just the loading state
    expect(cardsOnPage()).toHaveLength(0)
    for (const title of ['Esta Semana', 'Todo o Resto']) expect(screen.queryByText(title)).not.toBeInTheDocument()
  })

  it('puts a transaction in the last 7 days even when that window reaches into the previous month', async () => {
    vi.setSystemTime(new Date(2026, 2, 4, 12, 0, 0)) // Wednesday 4 March
    mockApi(routes({ data: [
      t(1, 'hoje', 100, '2026-03-04T09:00:00'),
      t(2, 'na semana', 100, '2026-02-27T10:00:00'),
      t(3, 'antes da semana', 100, '2026-02-24T23:59:00'),
    ] }))

    renderApp(<TransactionsDisplay />)
    await screen.findByText('hoje')

    expect(['hoje', 'na semana', 'antes da semana'].map(groupOf)).toEqual(['Hoje', 'Esta Semana', 'Todo o Resto'])
  })

  it('deletes a transaction and then shows the refreshed list', async () => {
    let remaining = TRANSACTIONS.data
    const api = mockApi({
      'GET /categories': CATEGORIES,
      'POST /transactions': () => jsonResponse({ data: remaining }),
      'DELETE /transactions/1': () => {
        remaining = remaining.filter((x) => x.id !== 1)
        return jsonResponse({ data: {} }, 202)
      },
    })
    renderApp(<TransactionsDisplay />)
    const card = (await screen.findByText('Almoço')).closest('.chakra-card__root')

    await userEvent.click(within(card).getByRole('button'))

    await waitFor(() => expect(screen.queryByText('Almoço')).not.toBeInTheDocument())
    expect(requestsMade(api)).toContain('DELETE /transactions/1')
    expect(screen.getByText('Uber')).toBeInTheDocument()
  })

  it.skip('TKT-32: reloads the list only after the delete has finished', async () => {
    let finishDelete
    const api = mockApi({
      'GET /categories': CATEGORIES,
      'POST /transactions': TRANSACTIONS,
      'DELETE /transactions/1': () => new Promise((resolve) => { finishDelete = () => resolve(new Response('{}', { status: 202 })) }),
    })
    renderApp(<TransactionsDisplay />)
    const card = (await screen.findByText('Almoço')).closest('.chakra-card__root')

    await userEvent.click(within(card).getByRole('button'))

    // while the delete is still running, the list must not be reloaded yet
    expect(requestsMade(api).filter((r) => r === 'POST /transactions')).toHaveLength(1)
    finishDelete()
    await waitFor(() => expect(requestsMade(api).filter((r) => r === 'POST /transactions')).toHaveLength(2))
  })

  it.skip('TKT-32: the delete button has a name that screen readers can announce', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    expect(screen.getAllByRole('button', { name: /excluir|remover|delete/i })).toHaveLength(4)
  })

  it.skip('TKT-32: shows the amount like the rest of the app (R$ 25,50), not as "- 25.5 R$"', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    expect(within(cardOf('Almoço')).getByText(/R\$\s*25,50/)).toBeInTheDocument()
    expect(within(cardOf('Uber')).getByText(/R\$\s*18,00/)).toBeInTheDocument()
  })

  it.skip('TKT-32: survives an expired session instead of showing a blank page', async () => {
    mockApi({
      'GET /categories': [{ detail: 'Token expired' }, 401],
      'POST /transactions': [{ detail: 'Token expired' }, 401],
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})

    renderApp(<TransactionsDisplay />)

    await waitFor(() => expect(document.querySelector('.chakra-spinner')).not.toBeInTheDocument())
    expect(cardsOnPage()).toHaveLength(0)
  })
})
