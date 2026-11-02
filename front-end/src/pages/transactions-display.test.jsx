import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { jsonResponse, mockApi, renderApp, requestsMade } from '../test/helpers'
import TransactionsDisplay from './transactions-display'

// Sunday 15 March 2026, noon: "today" starts 15 March 00:00, "this week" 8 March, "this month" 1 March.
const CATEGORIES = { data: [{ id: 1, name: 'Alimentação' }, { id: 2, name: 'Transporte' }] }
const t = (id, label, cents, date, category_id = 1) => ({ id, label, value: cents, transactioned_at: date, category_id })

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
const rowOf = (label) => screen.getByText(label).closest('tr')
// Rows with transactions have 5 cells; the group headings are one wide cell
const rowsOnPage = () => [...document.querySelectorAll('tbody tr')].filter((row) => row.children.length > 1)
// The group of a row is the closest heading row above it
const groupOf = (label) => {
  const rows = [...document.querySelectorAll('tbody tr')]
  const heading = rows.slice(0, rows.indexOf(rowOf(label))).reverse().find((row) => row.children.length === 1)
  return GROUP_TITLES.find((title) => heading?.textContent === title)
}
// The side panel (new or edit); the filter popover is a dialog too, so find it by its title
const drawer = async () => within((await screen.findByText(/^(Nova|Editar) transação$/)).closest('[role="dialog"]'))
const openMenuOf = async (label) => {
  await userEvent.click(within(rowOf(label)).getByRole('button', { name: /ações/i }))
  return screen.findByRole('menuitem', { name: /excluir/i })
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

  it('shows a table row per transaction with date, description, category and amount', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)

    await screen.findByText('Almoço')
    expect(screen.getAllByRole('columnheader').map((h) => h.textContent)).toEqual(
      ['Data', 'Descrição', 'Categoria', 'Valor', ''],
    )
    const cells = [...rowOf('Almoço').children].map((cell) => cell.textContent)
    expect(cells.slice(0, 4)).toEqual(['15/03/2026', 'Almoço', 'Alimentação', 'R$ 25,50'])
  })

  it('always shows the amount with two decimals, a comma and a dot between thousands', async () => {
    mockApi(routes({ data: [
      t(1, 'inteiro', 1800, '2026-03-15T09:00:00'),
      t(2, 'centavos', 5, '2026-03-15T09:00:00'),
      t(3, 'mil', 123456, '2026-03-15T09:00:00'),
      t(4, 'milhão', 100000000, '2026-03-15T09:00:00'),
    ] }))

    renderApp(<TransactionsDisplay />)
    await screen.findByText('inteiro')

    const amountOf = (label) => rowOf(label).children[3].textContent
    expect(['inteiro', 'centavos', 'mil', 'milhão'].map(amountOf)).toEqual(
      ['R$ 18,00', 'R$ 0,05', 'R$ 1.234,56', 'R$ 1.000.000,00'],
    )
  })

  it('groups transactions into today, this week, this month and older, in that order', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    const labels = ['Almoço', 'Uber', 'Mercado', 'Presente']
    expect(rowsOnPage().map((row) => labels.find((l) => row.textContent.includes(l)))).toEqual(labels)
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

    await screen.findByText(label)
    expect(groupOf(label)).toBe(group)
  })

  it('names the category, or says it was not found', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)

    await screen.findByText('Presente')
    expect(within(rowOf('Presente')).getByText('Categoria não encontrada')).toBeInTheDocument()
    expect(within(rowOf('Uber')).getByText('Transporte')).toBeInTheDocument()
  })

  it('only shows the groups that have transactions', async () => {
    mockApi(routes({ data: [t(1, 'Almoço', 2550, '2026-03-15T09:00:00')] }))

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    expect(screen.queryByText('Esta Semana')).not.toBeInTheDocument()
    expect(screen.queryByText('Todo o Resto')).not.toBeInTheDocument()
  })

  it('shows no rows when there are no transactions', async () => {
    const api = mockApi(routes({ data: [] }))

    renderApp(<TransactionsDisplay />)

    expect(document.querySelector('.chakra-spinner')).toBeInTheDocument()
    await waitFor(() => expect(document.querySelector('.chakra-spinner')).not.toBeInTheDocument())
    expect(api).toHaveBeenCalledTimes(2) // the data really arrived: this is not just the loading state
    expect(rowsOnPage()).toHaveLength(0)
    expect(screen.getByText('Nenhuma transação ainda.')).toBeInTheDocument()
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

  it('has no delete button visible: it lives in the three-dot menu of each row', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    expect(screen.getAllByRole('button', { name: /ações/i })).toHaveLength(4)
    expect(screen.queryByRole('menuitem', { name: /excluir/i })).not.toBeInTheDocument()
  })

  it('deletes a transaction from its menu and then shows the refreshed list', async () => {
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
    await screen.findByText('Almoço')

    await userEvent.click(await openMenuOf('Almoço'))

    await waitFor(() => expect(screen.queryByText('Almoço')).not.toBeInTheDocument())
    expect(requestsMade(api)).toContain('DELETE /transactions/1')
    expect(screen.getByText('Uber')).toBeInTheDocument()
  })

  it('reloads the list only after the delete has finished', async () => {
    let finishDelete
    const api = mockApi({
      'GET /categories': CATEGORIES,
      'POST /transactions': TRANSACTIONS,
      'DELETE /transactions/1': () => new Promise((resolve) => { finishDelete = () => resolve(new Response('{}', { status: 202 })) }),
    })
    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    await userEvent.click(await openMenuOf('Almoço'))

    // while the delete is still running, the list must not be reloaded yet
    await waitFor(() => expect(requestsMade(api)).toContain('DELETE /transactions/1'))
    expect(requestsMade(api).filter((r) => r === 'POST /transactions')).toHaveLength(1)
    finishDelete()
    await waitFor(() => expect(requestsMade(api).filter((r) => r === 'POST /transactions')).toHaveLength(2))
  })

  it('tells the user when a delete did not work', async () => {
    mockApi({
      ...routes(),
      'DELETE /transactions/1': [{ detail: 'Transaction not found' }, 404],
    })
    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    await userEvent.click(await openMenuOf('Almoço'))

    expect(await screen.findByText('Não foi possível excluir a transação.')).toBeInTheDocument()
  })

  it.skip('TKT-32: survives an expired session instead of showing a blank page', async () => {
    mockApi({
      'GET /categories': [{ detail: 'Token expired' }, 401],
      'POST /transactions': [{ detail: 'Token expired' }, 401],
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})

    renderApp(<TransactionsDisplay />)

    await waitFor(() => expect(document.querySelector('.chakra-spinner')).not.toBeInTheDocument())
    expect(rowsOnPage()).toHaveLength(0)
  })

  describe('adding a transaction', () => {
    it('has an add button that opens the sidebar with the form', async () => {
      mockApi(routes())
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')
      expect(screen.queryByLabelText('Valor')).not.toBeInTheDocument()

      await userEvent.click(screen.getByRole('button', { name: /adicionar/i }))

      expect(await screen.findByText('Nova transação')).toBeInTheDocument()
      expect(screen.getByLabelText('Valor')).toBeInTheDocument()
    })

    it('saves the new transaction and then shows it in the table', async () => {
      let saved = []
      const api = mockApi({
        'GET /categories': CATEGORIES,
        'POST /transactions': () => jsonResponse({ data: [...TRANSACTIONS.data, ...saved] }),
        'POST /transactions/create': (_url, options) => {
          const body = JSON.parse(options.body)
          saved = [t(9, body.label, body.value, '2026-03-15T11:00:00', body.category_id)]
          return jsonResponse({ data: body }, 201)
        },
      })
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      await userEvent.click(screen.getByRole('button', { name: /adicionar/i }))
      const form = await drawer()
      await userEvent.type(form.getByLabelText('Valor'), '1234567')
      await userEvent.type(form.getByLabelText('Descrição'), 'Cinema')
      await userEvent.selectOptions(form.getByLabelText('Categoria'), 'Transporte')
      await userEvent.click(form.getByRole('button', { name: 'Salvar' }))

      expect(await screen.findByText('Cinema')).toBeInTheDocument()
      expect(rowOf('Cinema').children[3].textContent).toBe('R$ 12.345,67')
      expect(within(rowOf('Cinema')).getByText('Transporte')).toBeInTheDocument()
      expect(JSON.parse(api.mock.calls.find(([url]) => url.endsWith('/create'))[1].body).value).toBe(1234567)
      await waitFor(() => expect(screen.queryByLabelText('Valor')).not.toBeInTheDocument()) // sidebar closed
    })
  })

  describe('editing a transaction', () => {
    const editRoutes = () => {
      let rows = TRANSACTIONS.data
      const api = mockApi({
        'GET /categories': CATEGORIES,
        'POST /transactions': () => jsonResponse({ data: rows }),
        'PUT /transactions/1': (_url, options) => {
          const body = JSON.parse(options.body)
          rows = rows.map((row) => (row.id === 1 ? { ...row, ...body } : row))
          return jsonResponse({ data: {} })
        },
        'DELETE /transactions/1': () => jsonResponse({ data: {} }, 202),
      })
      return api
    }
    const dialog = async () => (await drawer())

    it('opens the sidebar filled with the transaction from the row menu', async () => {
      editRoutes()
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      await userEvent.click(within(rowOf('Almoço')).getByRole('button', { name: /ações/i }))
      await userEvent.click(await screen.findByRole('menuitem', { name: /editar/i }))

      const form = await dialog()
      expect(form.getByText('Editar transação')).toBeInTheDocument()
      expect(form.getByLabelText('Valor')).toHaveValue('25,50')
      expect(form.getByLabelText('Descrição')).toHaveValue('Almoço')
      expect(form.getByLabelText('Categoria')).toHaveValue('1')
    })

    it('shows the date of the transaction in the edit form', async () => {
      mockApi(routes({ data: [t(1, 'Salário', 150000, '2026-03-02T09:15:00')] }))
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Salário')

      await userEvent.click(screen.getByText('Salário'))

      const form = await drawer()
      expect(form.getByLabelText('Data')).toHaveValue('2026-03-02')
    })

    it('changes the day but keeps the time of day when the date is edited', async () => {
      const api = editRoutes()
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')
      await userEvent.click(screen.getByText('Almoço'))
      const form = await drawer()

      fireEvent.change(form.getByLabelText('Data'), { target: { value: '2026-03-01' } })
      await userEvent.click(form.getByRole('button', { name: 'Salvar' }))

      await waitFor(() => expect(requestsMade(api)).toContain('PUT /transactions/1'))
      const put = api.mock.calls.find(([, o]) => o.method === 'put')
      expect(JSON.parse(put[1].body).transactioned_at).toBe('2026-03-01T09:00:00')
    })

    it('opens the same sidebar when the row is clicked', async () => {
      editRoutes()
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Uber')

      await userEvent.click(screen.getByText('Uber'))

      const form = await dialog()
      expect(form.getByLabelText('Descrição')).toHaveValue('Uber')
      expect(form.getByLabelText('Valor')).toHaveValue('18,00')
      expect(form.getByLabelText('Categoria')).toHaveValue('2')
    })

    it('saves the changes with PUT and shows the updated row', async () => {
      const api = editRoutes()
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      await userEvent.click(screen.getByText('Almoço'))
      const form = await dialog()
      await userEvent.clear(form.getByLabelText('Valor'))
      await userEvent.type(form.getByLabelText('Valor'), '3099')
      await userEvent.clear(form.getByLabelText('Descrição'))
      await userEvent.type(form.getByLabelText('Descrição'), 'Jantar')
      await userEvent.selectOptions(form.getByLabelText('Categoria'), 'Transporte')
      await userEvent.click(form.getByRole('button', { name: 'Salvar' }))

      expect(await screen.findByText('Jantar')).toBeInTheDocument()
      const put = api.mock.calls.find(([, o]) => o.method === 'put')
      expect(JSON.parse(put[1].body)).toEqual({
        label: 'Jantar', value: 3099, category_id: 2, transactioned_at: '2026-03-15T09:00:00',
      })
      expect(put[1].headers.Authorization).toBe('Bearer tok')
      expect(screen.queryByText('Almoço')).not.toBeInTheDocument()
      expect(rowOf('Jantar').children[3].textContent).toBe('R$ 30,99')
      await waitFor(() => expect(screen.queryByText(/^(Nova|Editar) transação$/)).not.toBeInTheDocument())
    })

    it('does not send anything when the edit is cancelled', async () => {
      const api = editRoutes()
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')
      await userEvent.click(screen.getByText('Almoço'))

      await userEvent.click((await drawer()).getByRole('button', { name: 'Cancelar' }))

      expect(requestsMade(api).filter((r) => r.startsWith('PUT'))).toHaveLength(0)
    })

    it('does not open the editor when an action in the row menu is used', async () => {
      editRoutes()
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      await userEvent.click(within(rowOf('Almoço')).getByRole('button', { name: /ações/i }))
      expect(screen.queryByText(/^(Nova|Editar) transação$/)).not.toBeInTheDocument() // opening the menu alone is not an edit
      await userEvent.click(await screen.findByRole('menuitem', { name: /excluir/i }))

      await waitFor(() => expect(screen.queryByText('Almoço')).toBeInTheDocument())
      expect(screen.queryByText(/^(Nova|Editar) transação$/)).not.toBeInTheDocument()
    })
  })

  describe('categories', () => {
    it('are listed alphabetically in the form', async () => {
      mockApi({
        'GET /categories': { data: [{ id: 2, name: 'Transporte' }, { id: 3, name: 'Água' }, { id: 1, name: 'Alimentação' }, { id: 4, name: 'zebra' }] },
        'POST /transactions': TRANSACTIONS,
      })
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')
      const names = (select) => within(select).getAllByRole('option').map((o) => o.textContent)

      await userEvent.click(screen.getByRole('button', { name: /adicionar/i }))
      const form = await drawer()
      expect(names(form.getByLabelText('Categoria'))).toEqual(['Selecione', 'Água', 'Alimentação', 'Transporte', 'zebra'])
    })
  })

})
