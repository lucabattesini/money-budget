import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { jsonResponse, mockApi, renderApp, requestsMade } from '../test/helpers'
import TransactionsDisplay from './transactions-display'

// Sunday 15 March 2026, noon: "today" starts 15 March 00:00, "this week" 8 March, "this month" 1 March.
const CATEGORIES = { data: [{ id: 1, name: 'Alimentação' }, { id: 2, name: 'Transporte' }] }
const t = (id, label, cents, date, category_id = 1) => ({ id, label, value: cents, date, category_id })

const TRANSACTIONS = {
  data: [
    t(1, 'Almoço', 2550, '2026-03-15T09:00:00'),
    t(2, 'Uber', 1800, '2026-03-10T18:00:00', 2),
    t(3, 'Mercado', 12000, '2026-03-02T10:00:00'),
    t(4, 'Presente', 5000, '2026-02-20T10:00:00', 99), // category that no longer exists
  ],
}

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

    const card = (await screen.findByText('Almoço')).closest('.chakra-card__root')
    expect(within(card).getByText('- 25.5 R$')).toBeInTheDocument()
    expect(within(card).getByText('Alimentação')).toBeInTheDocument()
    expect(within(card).getByText('15/03/2026')).toBeInTheDocument()
  })

  it('groups transactions into today, this week, this month and older, in that order', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    const text = document.body.textContent
    const order = ['Almoço', 'Uber', 'Mercado', 'Presente'].map((label) => text.indexOf(label))
    expect(order).toEqual([...order].sort((a, b) => a - b))
    expect(screen.getByText('Todo o Resto')).toBeInTheDocument()
    expect(screen.getByText('Esta Semana')).toBeInTheDocument()
  })

  it('names the category, or says it was not found', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)

    const gift = (await screen.findByText('Presente')).closest('.chakra-card__root')
    expect(within(gift).getByText('Categoria não encontrada')).toBeInTheDocument()
    const uber = screen.getByText('Uber').closest('.chakra-card__root')
    expect(within(uber).getByText('Transporte')).toBeInTheDocument()
  })

  it('only shows the groups that have transactions', async () => {
    mockApi(routes({ data: [t(1, 'Almoço', 2550, '2026-03-15T09:00:00')] }))

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    expect(screen.queryByText('Esta Semana')).not.toBeInTheDocument()
    expect(screen.queryByText('Todo o Resto')).not.toBeInTheDocument()
  })

  it('shows no cards when there are no transactions', async () => {
    mockApi(routes({ data: [] }))

    renderApp(<TransactionsDisplay />)

    await waitFor(() => expect(screen.queryByRole('progressbar')).not.toBeInTheDocument())
    expect(screen.queryAllByRole('button')).toHaveLength(0)
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
})
