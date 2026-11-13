import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useNavigate } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getToken, saveToken } from '../lib/auth'
import { jsonResponse, mockApi, renderApp, requestsMade, chooseCategory } from '../test/helpers'
import TransactionsDisplay from './transactions-display'

// The family the pages ask for, to show whose each transaction is
const FAMILY = {
  data: { me: '1', members: [{ id: '1', name: 'Clara Battesini', picture: null }, { id: '2', name: 'Bia Souza', picture: null }] },
}

// Sunday 15 March 2026, noon: "today" starts 15 March 00:00, "this week" 8 March, "this month" 1 March.
// Ids are opaque text (UUIDs on the real server), never numbers
const CATEGORIES = { data: [{ id: '1', name: 'Alimentação' }, { id: '2', name: 'Transporte' }] }
const t = (id, label, cents, date, category_id = 1) => ({
  id: String(id), label, value: cents, transactioned_at: date, category_id: String(category_id),
})

// Deliberately NOT in group order: the page itself must put today first and the oldest last.
const TRANSACTIONS = {
  data: [
    t(4, 'Presente', 5000, '2026-02-20T10:00:00', 99), // category that no longer exists
    t(3, 'Mercado', 12000, '2026-03-02T10:00:00'),
    t(2, 'Uber', 1800, '2026-03-10T18:00:00', 2),
    t(1, 'Almoço', 2550, '2026-03-15T09:00:00'),
  ],
}

const rowOf = (label) => screen.getByText(label).closest('tr')
// Rows with transactions have 6 cells (a tick box is added in front in selection mode); the day headings are one wide cell
const rowsOnPage = () => [...document.querySelectorAll('tbody tr')].filter((row) => row.children.length > 1)
// The filters live in a popover next to the add button
const openFilters = async () => {
  await userEvent.click(screen.getByRole('button', { name: /filtros/i }))
  await screen.findByLabelText('Buscar') // the popover content appears a moment after the click
}
// The side panel (new or edit); the filter popover is a dialog too, so find it by its title
const drawer = async () => within((await screen.findByText(/^(Nova|Editar) transação$/)).closest('[role="dialog"]'))
const openMenuOf = async (label) => {
  await userEvent.click(within(rowOf(label)).getByRole('button', { name: /ações/i }))
  return screen.findByRole('menuitem', { name: /excluir/i })
}

const routes = (transactions = TRANSACTIONS) => ({
  'GET /families/me': FAMILY, 'GET /categories': CATEGORIES,
  'POST /transactions': transactions,
})


const BackButton = () => {
  const navigate = useNavigate()
  return <button onClick={() => navigate(-1)}>voltar</button>
}

describe('transactions page', () => {
  beforeEach(() => {
    saveToken('tok')
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 2, 15, 12, 0, 0))
  })

  describe('opened from a link with filters', () => {
    it('shows only the transactions of the month in the link, and says the filters are on', async () => {
      mockApi(routes())

      renderApp(<TransactionsDisplay />, { route: '/transactions?from=2026-03-01&to=2026-03-31&type=debit' })

      await screen.findByText('Mercado')
      expect(rowsOnPage()).toHaveLength(3)
      ;['Almoço', 'Mercado', 'Uber'].forEach((label) => expect(screen.getByText(label)).toBeInTheDocument())
      expect(screen.queryByText('Presente')).not.toBeInTheDocument() // February
      await openFilters()
      expect(screen.getByLabelText('De')).toHaveValue('2026-03-01')
      expect(screen.getByLabelText('Até')).toHaveValue('2026-03-31')
      expect(screen.getByLabelText('Tipo')).toHaveValue('debit')
    })

    it('leaves out credits when the link asks for debits only', async () => {
      mockApi(routes({ data: [{ ...t(1, 'Salário', 300000, '2026-03-05T10:00:00'), type: 'credit' }, t(2, 'Mercado', 12000, '2026-03-06T10:00:00')] }))

      renderApp(<TransactionsDisplay />, { route: '/transactions?from=2026-03-01&to=2026-03-31&type=debit' })

      await screen.findByText('Mercado')
      expect(screen.queryByText('Salário')).not.toBeInTheDocument()
    })

    it('includes the last day of the month', async () => {
      mockApi(routes({ data: [t(1, 'Último dia', 100, '2026-03-31T23:30:00'), t(2, 'Dia seguinte', 100, '2026-04-01T00:10:00')] }))

      renderApp(<TransactionsDisplay />, { route: '/transactions?from=2026-03-01&to=2026-03-31' })

      await screen.findByText('Último dia')
      expect(screen.queryByText('Dia seguinte')).not.toBeInTheDocument()
    })

    it('shows everything without a link, and ignores a link that makes no sense', async () => {
      mockApi(routes())
      const { unmount } = renderApp(<TransactionsDisplay />)
      await screen.findByText('Presente')
      unmount()

      mockApi(routes())
      renderApp(<TransactionsDisplay />, { route: '/transactions?from=ontem&type=pix' })

      expect(await screen.findByText('Presente')).toBeInTheDocument()
    })
  })

  it('asks for the categories and for all transactions, with the user token', async () => {
    const api = mockApi(routes())

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    expect(requestsMade(api).sort()).toEqual(['GET /categories', 'GET /families/me', 'POST /transactions'])
    const post = api.mock.calls.find(([, o]) => o.method === 'post')
    expect(JSON.parse(post[1].body)).toEqual({ organized_by: null, date: null })
    expect(post[1].headers.Authorization).toBe('Bearer tok')
  })

  it('shows a table row per transaction with date, description, category and amount, without a header row', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)

    await screen.findByText('Almoço')
    expect(screen.queryAllByRole('columnheader')).toHaveLength(0) // no header row, just the transactions
    const cells = [...rowOf('Almoço').children].map((cell) => cell.textContent)
    expect(cells.slice(0, 5)).toEqual(['15/03/2026', 'Almoço', '', '', '- R$ 25,50']) // the category is a box, not text
    expect(within(rowOf('Almoço')).getByRole('combobox', { name: 'Categoria de Almoço' })).toHaveValue('Alimentação')
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

    const amountOf = (label) => rowOf(label).children[4].textContent
    expect(['inteiro', 'centavos', 'mil', 'milhão'].map(amountOf)).toEqual(
      ['- R$ 18,00', '- R$ 0,05', '- R$ 1.234,56', '- R$ 1.000.000,00'],
    )
  })

  it('lists every transaction in one list, newest first, whatever order the server sent them in', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    const labels = ['Almoço', 'Uber', 'Mercado', 'Presente'] // 15 March, 10 March, 2 March, 20 February
    expect(rowsOnPage().map((row) => labels.find((l) => row.textContent.includes(l)))).toEqual(labels)
  })

  it('has no headings that split the list into today, this week, this month and older', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    for (const title of ['Hoje', 'Esta Semana', 'Este Mês', 'Todo o Resto']) {
      expect(screen.queryByText(title, { selector: 'td *, td' })).not.toBeInTheDocument()
    }
  })

  it('puts transactions of the same minute in a steady order', async () => {
    mockApi(routes({ data: [t(1, 'primeira', 100, '2026-03-15T09:00:00'), t(2, 'segunda', 100, '2026-03-15T09:00:00')] }))

    renderApp(<TransactionsDisplay />)
    await screen.findByText('primeira')

    expect(rowsOnPage()).toHaveLength(2)
  })

  it('names the category, or says it was not found', async () => {
    mockApi(routes())

    renderApp(<TransactionsDisplay />)

    await screen.findByText('Presente')
    expect(within(rowOf('Presente')).getByPlaceholderText('Categoria não encontrada')).toBeInTheDocument()
    expect(within(rowOf('Uber')).getByRole('combobox')).toHaveValue('Transporte')
  })

  it('shows no rows when there are no transactions', async () => {
    const api = mockApi(routes({ data: [] }))

    renderApp(<TransactionsDisplay />)

    expect(document.querySelector('.chakra-spinner')).toBeInTheDocument()
    await waitFor(() => expect(document.querySelector('.chakra-spinner')).not.toBeInTheDocument())
    expect(api).toHaveBeenCalledTimes(3) // the data really arrived: this is not just the loading state
    expect(rowsOnPage()).toHaveLength(0)
    expect(screen.getByText('Nenhuma transação ainda.')).toBeInTheDocument()
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
      'GET /families/me': FAMILY, 'GET /categories': CATEGORIES,
      'POST /transactions': () => jsonResponse({ data: remaining }),
      'DELETE /transactions/1': () => {
        remaining = remaining.filter((x) => x.id !== '1')
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
      'GET /families/me': FAMILY, 'GET /categories': CATEGORIES,
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

  it('survives an expired session instead of showing a blank page', async () => {
    mockApi({
      'GET /families/me': FAMILY, 'GET /categories': [{ detail: 'Token expired' }, 401],
      'POST /transactions': [{ detail: 'Token expired' }, 401],
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})

    renderApp(<TransactionsDisplay />)

    await waitFor(() => expect(document.querySelector('.chakra-spinner')).not.toBeInTheDocument())
    expect(rowsOnPage()).toHaveLength(0)
    expect(getToken()).toBeNull()
    expect(window.location.hash).toBe('#/login-google')
    expect(screen.queryByText(/Não foi possível carregar/)).not.toBeInTheDocument()
  })

  describe('changing the category from the list', () => {
    const quickRoutes = (put) => {
      let rows = TRANSACTIONS.data
      return mockApi({
        'GET /families/me': FAMILY, 'GET /categories': CATEGORIES,
        'POST /transactions': () => jsonResponse({ data: rows }),
        'PUT /transactions/1': (_url, options) => {
          const response = put(options)
          if (response.status < 400) rows = rows.map((row) => (row.id === '1' ? { ...row, category_id: JSON.parse(options.body).category_id } : row))
          return Promise.resolve(response)
        },
      })
    }
    const ok = () => new Response(JSON.stringify({ data: {} }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    const refused = () => new Response(JSON.stringify({ detail: 'no' }), { status: 500, headers: { 'Content-Type': 'application/json' } })
    const boxOf = (label) => within(rowOf(label)).getByRole('combobox', { name: `Categoria de ${label}` })

    it('saves the new category right away, sending the transaction as it is, and shows it in the row', async () => {
      const api = quickRoutes(ok)
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      await chooseCategory(boxOf('Almoço'), 'Transporte')

      await waitFor(() => expect(boxOf('Almoço')).toHaveValue('Transporte'))
      const put = api.mock.calls.find(([url, options]) => String(options?.method).toUpperCase() === 'PUT' && url.endsWith('/transactions/1'))
      expect(JSON.parse(put[1].body)).toEqual({ label: 'Almoço', value: 2550, category_id: '2' }) // nothing else is touched
      expect(await screen.findByText('A categoria foi atualizada!')).toBeInTheDocument()
      expect(screen.queryByText('Editar transação')).not.toBeInTheDocument() // the row's editor did not open
    })

    it('tells the person when it could not be saved, and the row keeps its category', async () => {
      quickRoutes(refused)
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      await chooseCategory(boxOf('Almoço'), 'Transporte')

      expect(await screen.findByText('Não foi possível trocar a categoria. Tente novamente.')).toBeInTheDocument()
      await waitFor(() => expect(boxOf('Almoço')).toHaveValue('Alimentação'))
    })

    it('does not save when the same category is chosen again', async () => {
      const api = quickRoutes(ok)
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      await chooseCategory(boxOf('Almoço'), 'Alimentação')

      expect(requestsMade(api).filter((request) => request.startsWith('PUT'))).toEqual([])
    })

    it('narrows the list by what is typed in the row', async () => {
      quickRoutes(ok)
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      await userEvent.clear(boxOf('Almoço'))
      await userEvent.type(boxOf('Almoço'), 'trans')

      await waitFor(() => expect(screen.queryAllByRole('option').map((option) => option.textContent)).toEqual(['Transporte']))
    })

    it('is plain text in selection mode, where a click ticks the row', async () => {
      quickRoutes(ok)
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      await userEvent.click(screen.getByRole('button', { name: /Selecionar/ }))

      expect(screen.queryByRole('combobox', { name: 'Categoria de Almoço' })).not.toBeInTheDocument()
      expect(within(rowOf('Almoço')).getByText('Alimentação')).toBeInTheDocument()
    })
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
        'GET /families/me': FAMILY, 'GET /categories': CATEGORIES,
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
      await chooseCategory(form.getByRole('combobox', { name: 'Categoria' }), 'Transporte')
      await userEvent.click(form.getByRole('button', { name: 'Salvar' }))

      expect(await screen.findByText('Cinema')).toBeInTheDocument()
      expect(rowOf('Cinema').children[4].textContent).toBe('- R$ 12.345,67')
      expect(within(rowOf('Cinema')).getByRole('combobox')).toHaveValue('Transporte')
      expect(JSON.parse(api.mock.calls.find(([url]) => url.endsWith('/create'))[1].body).value).toBe(1234567)
      await waitFor(() => expect(screen.queryByLabelText('Valor')).not.toBeInTheDocument()) // sidebar closed
    })
  })

  describe('editing a transaction', () => {
    const editRoutes = () => {
      let rows = TRANSACTIONS.data
      const api = mockApi({
        'GET /families/me': FAMILY, 'GET /categories': CATEGORIES,
        'POST /transactions': () => jsonResponse({ data: rows }),
        'PUT /transactions/1': (_url, options) => {
          const body = JSON.parse(options.body)
          rows = rows.map((row) => (row.id === '1' ? { ...row, ...body } : row))
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
      expect(form.getByRole('combobox', { name: 'Categoria' })).toHaveValue('Alimentação')
    })

    it('shows the date and the type of the transaction in the edit form', async () => {
      mockApi(routes({ data: [{ ...t(1, 'Salário', 150000, '2026-03-02T09:15:00'), type: 'credit' }] }))
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Salário')

      await userEvent.click(screen.getByText('Salário'))

      const form = await drawer()
      expect(form.getByLabelText('Data')).toHaveValue('2026-03-02')
      expect(form.getByRole('radio', { name: 'Crédito' })).toBeChecked()
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

    it('marks a transaction that is left out of the totals, and only that one', async () => {
      mockApi({
        'GET /families/me': FAMILY,
        'GET /categories': CATEGORIES,
        'POST /transactions': { data: [{ ...t(1, 'Almoço', 2550, '2026-03-15T09:00:00'), excluded: true }, t(2, 'Uber', 1800, '2026-03-10T18:00:00')] },
      })
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      expect(within(rowOf('Almoço')).getByTitle('Não conta nos totais')).toHaveStyle({ opacity: '0.45' })
      expect(within(rowOf('Uber')).queryByTitle('Não conta nos totais')).not.toBeInTheDocument()
    })

    it('opens the same sidebar when the row is clicked', async () => {
      editRoutes()
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Uber')

      await userEvent.click(screen.getByText('Uber'))

      const form = await dialog()
      expect(form.getByLabelText('Descrição')).toHaveValue('Uber')
      expect(form.getByLabelText('Valor')).toHaveValue('18,00')
      expect(form.getByRole('combobox', { name: 'Categoria' })).toHaveValue('Transporte')
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
      await chooseCategory(form.getByRole('combobox', { name: 'Categoria' }), 'Transporte')
      await userEvent.click(form.getByRole('button', { name: 'Salvar' }))

      expect(await screen.findByText('Jantar')).toBeInTheDocument()
      const put = api.mock.calls.find(([, o]) => o.method === 'put')
      expect(JSON.parse(put[1].body)).toEqual({
        label: 'Jantar', value: 3099, category_id: '2', type: 'debit', transactioned_at: '2026-03-15T09:00:00', excluded: false,
      })
      expect(put[1].headers.Authorization).toBe('Bearer tok')
      expect(screen.queryByText('Almoço')).not.toBeInTheDocument()
      expect(rowOf('Jantar').children[4].textContent).toBe('- R$ 30,99')
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

  it('marks credits with a plus and debits with a minus', async () => {
    mockApi(routes({ data: [
      { ...t(1, 'Salário', 150000, '2026-03-15T09:00:00'), type: 'credit' },
      { ...t(2, 'Mercado', 3000, '2026-03-15T08:00:00'), type: 'debit' },
      t(3, 'Antigo sem tipo', 1000, '2026-03-14T08:00:00'), // rows without a type are expenses
    ] }))

    renderApp(<TransactionsDisplay />)
    await screen.findByText('Salário')

    expect(['Salário', 'Mercado', 'Antigo sem tipo'].map((l) => rowOf(l).children[4].textContent)).toEqual(
      ['+ R$ 1.500,00', '- R$ 30,00', '- R$ 10,00'],
    )
  })

  describe('categories', () => {
    it('are listed alphabetically in the filter and in the form', async () => {
      mockApi({
        'GET /families/me': FAMILY, 'GET /categories': { data: [{ id: 2, name: 'Transporte' }, { id: 3, name: 'Água' }, { id: 1, name: 'Alimentação' }, { id: 4, name: 'zebra' }] },
        'POST /transactions': TRANSACTIONS,
      })
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')
      const names = async (box) => {
        await userEvent.click(box)
        return within(await screen.findByRole('listbox')).getAllByRole('option').map((o) => o.textContent)
      }

      await openFilters()
      expect(await names(screen.getByRole('combobox', { name: 'Categoria' }))).toEqual(['Todas', 'Água', 'Alimentação', 'Transporte', 'zebra'])
      await userEvent.keyboard('{Escape}{Escape}')
      await userEvent.click(screen.getByRole('button', { name: /adicionar/i }))
      const form = await drawer()
      expect(await names(form.getByRole('combobox', { name: 'Categoria' }))).toEqual(['Água', 'Alimentação', 'Transporte', 'zebra'])
    })
  })

  it('has no filter fields on the page until the filter menu is opened', async () => {
    mockApi(routes())
    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    expect(screen.queryByLabelText('Buscar')).not.toBeInTheDocument()
    await openFilters()
    expect(screen.getByLabelText('Buscar')).toBeInTheDocument()
  })

  describe('filters', () => {
    const FILTERED = {
      data: [
        t(1, 'Almoço', 2550, '2026-03-15T09:00:00', 1),
        t(2, 'Uber', 1800, '2026-03-10T18:00:00', 2),
        t(3, 'Mercado', 12000, '2026-03-02T10:00:00', 1),
        t(4, 'Presente', 5000, '2026-02-20T10:00:00', 2),
      ],
    }
    const labelsShown = () => rowsOnPage().map((row) => row.children[1].textContent)
    const setup = async () => {
      mockApi(routes(FILTERED))
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')
      await openFilters()
    }

    it('narrows by description, ignoring case', async () => {
      await setup()

      await userEvent.type(screen.getByLabelText('Buscar'), 'MERC')

      expect(labelsShown()).toEqual(['Mercado'])
    })

    it('narrows by category', async () => {
      await setup()

      await chooseCategory(screen.getByRole('combobox', { name: 'Categoria' }), 'Transporte')

      expect(labelsShown()).toEqual(['Uber', 'Presente'])
    })

    it('narrows by date range, including both end days', async () => {
      await setup()

      fireEvent.change(screen.getByLabelText('De'), { target: { value: '2026-03-02' } })
      fireEvent.change(screen.getByLabelText('Até'), { target: { value: '2026-03-10' } })

      expect(labelsShown()).toEqual(['Uber', 'Mercado'])
    })

    it('narrows by amount range, typed with the amount mask', async () => {
      await setup()

      await userEvent.type(screen.getByLabelText('Valor mínimo'), '2000')
      expect(screen.getByLabelText('Valor mínimo')).toHaveValue('20,00')
      await userEvent.type(screen.getByLabelText('Valor máximo'), '6000')

      expect(labelsShown()).toEqual(['Almoço', 'Presente'])
    })

    it('narrows by credit or debit', async () => {
      mockApi(routes({ data: [
        { ...t(1, 'Salário', 150000, '2026-03-15T09:00:00'), type: 'credit' },
        t(2, 'Mercado', 3000, '2026-03-15T08:00:00'),
      ] }))
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Salário')
      await openFilters()

      await userEvent.selectOptions(screen.getByLabelText('Tipo'), 'Crédito')
      expect(labelsShown()).toEqual(['Salário'])
      await userEvent.selectOptions(screen.getByLabelText('Tipo'), 'Débito')
      expect(labelsShown()).toEqual(['Mercado'])
    })

    it('hides the filters in a menu and counts how many are set', async () => {
      await setup()
      expect(screen.getByRole('button', { name: 'Filtros' })).toBeInTheDocument()

      await userEvent.type(screen.getByLabelText('Buscar'), 'a')
      await chooseCategory(screen.getByRole('combobox', { name: 'Categoria' }), 'Transporte')

      expect(screen.getByRole('button', { name: 'Filtros (2)' })).toBeInTheDocument()
    })

    it('writes the filters into the address, replacing the entry (not one step back per change)', async () => {
      mockApi(routes(FILTERED))
      renderApp(<><TransactionsDisplay /><BackButton /></>, { route: '/transactions?from=2026-03-01' })
      await screen.findByText('Almoço')
      await openFilters()

      await chooseCategory(screen.getByRole('combobox', { name: 'Categoria' }), 'Transporte')
      await userEvent.type(screen.getByLabelText('Buscar'), 'ub')

      const shown = screen.getByTestId('location').textContent
      expect(shown).toContain('search=ub')
      expect(shown).toContain('from=2026-03-01')
    })

    it('closes the filter panel when the person goes back, and stays on the page', async () => {
      mockApi(routes(FILTERED))
      renderApp(<><TransactionsDisplay /><BackButton /></>, { route: '/transactions' })
      await screen.findByText('Almoço')
      await openFilters()
      expect(screen.getByLabelText('Buscar')).toBeInTheDocument()

      await userEvent.click(screen.getByText('voltar'))

      await waitFor(() => expect(screen.queryByLabelText('Buscar')).not.toBeInTheDocument())
      expect(screen.getByTestId('location')).toHaveTextContent('/transactions')
    })

    it('keeps a filter changed while the panel is open in the address after the panel is closed', async () => {
      mockApi(routes(FILTERED))
      renderApp(<><TransactionsDisplay /><BackButton /></>, { route: '/transactions?from=2026-03-01' })
      await screen.findByText('Almoço')
      await openFilters()

      await userEvent.type(screen.getByLabelText('Buscar'), 'ub')
      await userEvent.click(screen.getByText('voltar')) // closes the panel: one step back

      await waitFor(() => expect(screen.queryByLabelText('Buscar')).not.toBeInTheDocument())
      await waitFor(() => {
        const address = screen.getByTestId('location').textContent // the step back and the rewrite settle together
        expect(address).toContain('search=ub')
        expect(address).toContain('from=2026-03-01')
      })
    })

    it('combines filters', async () => {
      await setup()

      await chooseCategory(screen.getByRole('combobox', { name: 'Categoria' }), 'Alimentação')
      await userEvent.type(screen.getByLabelText('Valor mínimo'), '5000')

      expect(labelsShown()).toEqual(['Mercado'])
    })

    it('says so when nothing matches, and clearing the filters brings everything back', async () => {
      await setup()

      await userEvent.type(screen.getByLabelText('Buscar'), 'nada disso')

      expect(screen.getByText('Nenhuma transação encontrada com esses filtros.')).toBeInTheDocument()
      expect(labelsShown()).toEqual([])
      await userEvent.click(screen.getByRole('button', { name: /limpar filtros/i }))
      expect(labelsShown()).toHaveLength(4)
      expect(screen.getByLabelText('Buscar')).toHaveValue('')
      expect(screen.queryByRole('button', { name: /limpar filtros/i })).not.toBeInTheDocument()
    })

    it('does not change the totals at the top', async () => {
      await setup()
      const summary = () => screen.getByText('Hoje', { selector: 'p' }).nextSibling.textContent

      const before = summary()
      await userEvent.type(screen.getByLabelText('Buscar'), 'Mercado')

      expect(summary()).toBe(before)
    })
  })

  describe('infinite scroll', () => {
    // 100 transactions, "compra 001" (newest) ... "compra 100"
    const MANY = {
      data: Array.from({ length: 100 }, (_, i) =>
        t(1000 + i, `compra ${String(i + 1).padStart(3, '0')}`, 1000, new Date(2026, 1, 28 - Math.floor(i / 4), 12, 59 - (i % 4)).toISOString().slice(0, 19), 1)),
    }
    const labels = () => rowsOnPage().map((row) => row.children[1].textContent)

    // The browser's way of saying "the end of the list is in view" is played by the test
    let watchers
    beforeEach(() => {
      watchers = []
      vi.stubGlobal('IntersectionObserver', class {
        constructor(callback) { this.callback = callback; this.live = true; watchers.push(this) }
        observe() {}
        disconnect() { this.live = false }
      })
    })
    afterEach(() => vi.unstubAllGlobals())
    const scrollToTheEnd = async () => {
      await waitFor(() => expect(watchers.some((w) => w.live)).toBe(true)) // the page has started watching the end of the list
      act(() => watchers.filter((w) => w.live).forEach((w) => w.callback([{ isIntersecting: true }])))
    }

    it('puts the first rows on the page and the next ones when the end of the list comes into view', async () => {
      mockApi(routes(MANY))
      renderApp(<TransactionsDisplay />)
      await screen.findByText('compra 001')

      expect(labels()).toHaveLength(40)
      expect(labels()[0]).toBe('compra 001')
      expect(screen.queryByText('compra 041')).not.toBeInTheDocument()

      await scrollToTheEnd()
      expect(await screen.findByText('compra 041')).toBeInTheDocument()
      expect(labels()).toHaveLength(80)
      await scrollToTheEnd()
      await waitFor(() => expect(labels()).toHaveLength(100))
      expect(labels().at(-1)).toBe('compra 100')
    })

    it('does not leave the page, and has no page buttons or numbers', async () => {
      mockApi(routes(MANY))
      renderApp(<TransactionsDisplay />)
      await screen.findByText('compra 001')

      expect(screen.queryByText(/Página \d/)).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Próxima' })).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Anterior' })).not.toBeInTheDocument()
    })

    it('watches nothing once every row is on the page', async () => {
      mockApi(routes({ data: MANY.data.slice(0, 40) }))
      renderApp(<TransactionsDisplay />)
      await screen.findByText('compra 001')

      expect(labels()).toHaveLength(40)
      expect(watchers.filter((w) => w.live)).toHaveLength(0)
    })

    it('starts from the top again when a filter changes', async () => {
      mockApi(routes(MANY))
      renderApp(<TransactionsDisplay />)
      await screen.findByText('compra 001')
      await scrollToTheEnd()
      await screen.findByText('compra 041')

      await openFilters()
      await userEvent.type(screen.getByLabelText('Buscar'), 'compra 0')

      expect(labels()).toHaveLength(40) // 99 match, the first batch again
      expect(labels()[0]).toBe('compra 001')
    })

    it('shows the day above its rows on a phone, once per day', async () => {
      mockApi(routes(MANY))
      renderApp(<TransactionsDisplay />)
      await screen.findByText('compra 001')

      const days = [...document.querySelectorAll('tbody tr[data-day]')]
      expect(days).toHaveLength(10) // 40 rows, 4 a day
      expect(new Set(days.map((day) => day.textContent)).size).toBe(10)
    })
  })

  describe('infinite scroll without the browser support', () => {
    const MANY = { data: Array.from({ length: 90 }, (_, i) => t(2000 + i, `item ${String(i + 1).padStart(2, '0')}`, 100, new Date(2026, 1, 28, 12, 59 - (i % 60), 59 - Math.floor(i / 60)).toISOString().slice(0, 19), 1)) }

    it('offers a "Mostrar mais" button that adds the next rows, and removes it at the end', async () => {
      vi.stubGlobal('IntersectionObserver', undefined)
      mockApi(routes(MANY))
      renderApp(<TransactionsDisplay />)
      await screen.findByText('item 01')
      expect(rowsOnPage()).toHaveLength(40)

      await userEvent.click(screen.getByRole('button', { name: 'Mostrar mais' }))
      expect(rowsOnPage()).toHaveLength(80)
      await userEvent.click(screen.getByRole('button', { name: 'Mostrar mais' }))

      expect(rowsOnPage()).toHaveLength(90)
      expect(screen.queryByRole('button', { name: 'Mostrar mais' })).not.toBeInTheDocument()
      vi.unstubAllGlobals()
    })
  })

  describe('who a transaction belongs to', () => {
    const OWNED = {
      data: [
        { ...t(1, 'Almoço', 2550, '2026-03-15T09:00:00', 1), user_id: '1' },
        { ...t(2, 'Uber', 1800, '2026-03-10T18:00:00', 2), user_id: '2' },
        { ...t(3, 'Mercado', 12000, '2026-03-02T10:00:00', 1), user_id: '2' },
      ],
    }
    const setup = async () => {
      const api = mockApi({
        'GET /families/me': FAMILY,
        'GET /categories': CATEGORIES,
        'POST /transactions': OWNED,
        'POST /transactions/create': [{ data: {} }, 201],
        'PUT /transactions/2': [{ data: {} }, 200],
      })
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')
      return api
    }
    const bodyOf = (api, suffix) => JSON.parse(api.mock.calls.find(([url]) => url.endsWith(suffix))[1].body)

    it('shows the person of each row, with the name for screen readers and on hover', async () => {
      await setup()

      const bia = within(rowOf('Uber')).getByRole('img', { name: 'Bia Souza' })
      expect(bia).toHaveAttribute('title', 'Bia Souza')
      expect(within(rowOf('Almoço')).getByRole('img', { name: 'Clara Battesini' })).toBeInTheDocument()
    })

    it('shows the first name next to the category, and no separator when the person is unknown', async () => {
      mockApi({
        'GET /families/me': FAMILY,
        'GET /categories': CATEGORIES,
        'POST /transactions': { data: [
          { ...t(1, 'Almoço', 2550, '2026-03-15T09:00:00', 1), user_id: '1' },
          { ...t(2, 'Uber', 1800, '2026-03-10T18:00:00', 2), user_id: '99' }, // a person who is no longer in the family
        ] },
      })
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      expect(rowOf('Almoço').textContent).toContain('· Clara')
      expect(rowOf('Uber').textContent).not.toContain('·')
    })

    it('splits the category name from its emoji, flags and joined emoji included', async () => {
      mockApi({
        'GET /families/me': FAMILY,
        'GET /categories': { data: [{ id: '1', name: '🎁 Presentes' }, { id: '2', name: '🇨🇦 Canadá' }, { id: '3', name: '👨‍👩‍👧 Família' }] },
        'POST /transactions': { data: [t(1, 'A', 100, '2026-03-15T09:00:00', 1), t(2, 'B', 100, '2026-03-15T08:00:00', 2), t(3, 'C', 100, '2026-03-15T07:00:00', 3)] },
      })
      renderApp(<TransactionsDisplay />)
      await screen.findByText('A')

      // the last cell of a row is the phone-only icon; the category cell keeps the name (the emoji is only for wider screens)
      expect(['A', 'B', 'C'].map((l) => rowOf(l).lastElementChild.textContent)).toEqual(['🎁', '🇨🇦', '👨‍👩‍👧'])
      expect(['A', 'B', 'C'].map((l) => within(rowOf(l)).getByRole('combobox').value)).toEqual(['🎁 Presentes', '🇨🇦 Canadá', '👨‍👩‍👧 Família'])
    })

    it('has the logged-in person chosen in a new transaction, and sends it', async () => {
      const api = await setup()

      await userEvent.click(screen.getByRole('button', { name: /adicionar/i }))
      const form = await drawer()
      expect(form.getByLabelText('Quem')).toHaveValue('1')
      expect(within(form.getByLabelText('Quem')).getAllByRole('option').map((o) => o.textContent)).toEqual([
        'Clara Battesini',
        'Bia Souza',
      ])
      await userEvent.type(form.getByLabelText('Valor'), '500')
      await userEvent.type(form.getByLabelText('Descrição'), 'Pão')
      await chooseCategory(form.getByRole('combobox', { name: 'Categoria' }), 'Transporte')
      await userEvent.selectOptions(form.getByLabelText('Quem'), 'Bia Souza')
      await userEvent.click(form.getByRole('button', { name: 'Salvar' }))

      await waitFor(() => expect(bodyOf(api, '/create').user_id).toBe('2'))
    })

    it('opens an edit with the transaction\'s person, and lets it be changed', async () => {
      const api = await setup()

      await userEvent.click(rowOf('Uber'))
      const form = await drawer()
      expect(form.getByLabelText('Quem')).toHaveValue('2')
      await userEvent.selectOptions(form.getByLabelText('Quem'), 'Clara Battesini')
      await userEvent.click(form.getByRole('button', { name: 'Salvar' }))

      await waitFor(() => expect(bodyOf(api, '/transactions/2').user_id).toBe('1'))
    })

    it('does not make up a person for one who is no longer in the family', async () => {
      const api = mockApi({
        'GET /families/me': FAMILY,
        'GET /categories': CATEGORIES,
        'POST /transactions': { data: [{ ...t(1, 'Almoço', 2550, '2026-03-15T09:00:00', 1), user_id: '77' }] },
        'PUT /transactions/1': [{ data: {} }, 200],
      })
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      expect(within(rowOf('Almoço')).queryByRole('img')).not.toBeInTheDocument()
      await userEvent.click(rowOf('Almoço'))
      const form = await drawer()
      expect(form.getByLabelText('Quem')).toHaveValue('')
      await userEvent.click(form.getByRole('button', { name: 'Salvar' }))
      // Nothing is sent for the person, so the server keeps the one it has
      await waitFor(() => expect(api.mock.calls.some(([url]) => url.endsWith('/transactions/1'))).toBe(true))
      expect(JSON.parse(api.mock.calls.find(([url]) => url.endsWith('/transactions/1'))[1].body)).not.toHaveProperty('user_id')
    })

    it('offers the Quem filter even when the family has only one person', async () => {
      mockApi({
        'GET /families/me': { data: { me: 1, members: [FAMILY.data.members[0]] } },
        'GET /categories': CATEGORIES,
        'POST /transactions': OWNED,
      })
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')
      await openFilters()

      expect(screen.getByLabelText('Quem')).toBeInTheDocument()
    })

    it('narrows to one person in the filters', async () => {
      await setup()
      await openFilters()

      await userEvent.selectOptions(screen.getByLabelText('Quem'), 'Bia Souza')

      expect(rowsOnPage().map((row) => row.children[1].textContent)).toEqual(['Uber', 'Mercado'])
    })
  })

  describe('merchants (an optional setting of the family)', () => {
    const MERCHANTS = { data: [{ id: 5, name: 'Uber', transactions: 2 }, { id: 6, name: 'iFood', transactions: 1 }] }
    const FAMILY_ON = { data: { ...FAMILY.data, merchants_enabled: true } }
    const WITH = {
      data: [
        { ...t(1, 'Almoço', 2550, '2026-03-15T09:00:00', 1), merchant_id: 6 },
        { ...t(2, 'Corrida', 1800, '2026-03-10T18:00:00', 2), merchant_id: 5 },
        { ...t(3, 'Volta', 700, '2026-03-11T18:00:00', 2), merchant_id: 5 },
        { ...t(4, 'Salário', 99900, '2026-03-02T10:00:00', 1, ), merchant_id: 5, type: 'credit' },
        t(5, 'Sem lugar', 1000, '2026-03-03T10:00:00'),
      ],
    }
    const setup = async (extra = {}) => {
      const api = mockApi({
        'GET /families/me': FAMILY_ON,
        'GET /categories': CATEGORIES,
        'GET /merchants': MERCHANTS,
        'POST /transactions': WITH,
        'POST /transactions/create': [{ data: {} }, 201],
        'PUT /transactions/2': [{ data: {} }, 200],
        ...extra,
      })
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')
      await screen.findByText('iFood') // the merchants arrived
      return api
    }
    const bodyOf = (api, suffix) => JSON.parse(api.mock.calls.find(([url]) => url.endsWith(suffix))[1].body)

    it('changes nothing while they are off: no request, no field', async () => {
      const api = mockApi(routes())
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      expect(requestsMade(api)).not.toContain('GET /merchants')
      await userEvent.click(screen.getByRole('button', { name: /adicionar/i }))
      expect((await drawer()).queryByLabelText('Estabelecimento')).not.toBeInTheDocument()
    })

    it('shows the merchant under the description of each row', async () => {
      await setup()

      expect(within(rowOf('Corrida')).getByText('Uber')).toBeInTheDocument()
      expect(within(rowOf('Almoço')).getByText('iFood')).toBeInTheDocument()
      expect(within(rowOf('Sem lugar')).queryByText(/Uber|iFood/)).not.toBeInTheDocument()
    })

    it('lets the user pick an existing merchant or type a new name, and sends the name', async () => {
      const api = await setup()

      await userEvent.click(screen.getByRole('button', { name: /adicionar/i }))
      const form = await drawer()
      const field = form.getByLabelText('Estabelecimento')
      expect([...document.querySelectorAll('#merchant-options option')].map((o) => o.value)).toEqual(['Uber', 'iFood'])
      await userEvent.type(form.getByLabelText('Valor'), '500')
      await userEvent.type(form.getByLabelText('Descrição'), 'Série')
      await chooseCategory(form.getByRole('combobox', { name: 'Categoria' }), 'Transporte')
      await userEvent.type(field, '  Netflix ')
      await userEvent.click(form.getByRole('button', { name: 'Salvar' }))

      await waitFor(() => expect(bodyOf(api, '/create').merchant).toBe('Netflix'))
    })

    it('opens an edit with its merchant, and an empty field takes it off', async () => {
      const api = await setup()

      await userEvent.click(rowOf('Corrida'))
      const form = await drawer()
      expect(form.getByLabelText('Estabelecimento')).toHaveValue('Uber')
      await userEvent.clear(form.getByLabelText('Estabelecimento'))
      await userEvent.click(form.getByRole('button', { name: 'Salvar' }))

      await waitFor(() => expect(bodyOf(api, '/transactions/2').merchant).toBe(''))
    })

    it('narrows to one merchant in the filters', async () => {
      await setup()
      await openFilters()

      await userEvent.selectOptions(screen.getByLabelText('Estabelecimento'), 'Uber')

      expect(rowsOnPage().map((row) => row.children[1].textContent)).toEqual(['VoltaUber', 'CorridaUber', 'SalárioUber']) // newest first: 11, 10 and 2 March
    })

    it('does not touch the merchant of an edited transaction when the merchants could not be loaded', async () => {
      vi.spyOn(console, 'error').mockImplementation(() => {})
      const api = mockApi({
        'GET /families/me': FAMILY_ON,
        'GET /categories': CATEGORIES,
        'GET /merchants': [{ detail: 'boom' }, 500],
        'POST /transactions': WITH,
        'PUT /transactions/2': [{ data: {} }, 200],
      })
      renderApp(<TransactionsDisplay />)
      await screen.findByText('Almoço')

      await userEvent.click(rowOf('Corrida'))
      const form = await drawer()
      expect(form.queryByLabelText('Estabelecimento')).not.toBeInTheDocument()
      await userEvent.click(form.getByRole('button', { name: 'Salvar' }))

      await waitFor(() => expect(bodyOf(api, '/transactions/2')).not.toHaveProperty('merchant')) // the server keeps it
    })

    it('still lists the transactions when the merchants cannot be loaded', async () => {
      vi.spyOn(console, 'error').mockImplementation(() => {})

      mockApi({
        'GET /families/me': FAMILY_ON,
        'GET /categories': CATEGORIES,
        'GET /merchants': [{ detail: 'boom' }, 500],
        'POST /transactions': WITH,
      })
      renderApp(<TransactionsDisplay />)

      expect(await screen.findByText('Almoço')).toBeInTheDocument()
    })
  })

  it('tells the user when the transactions could not be loaded', async () => {
    mockApi({ 'GET /families/me': FAMILY, 'GET /categories': [{ detail: 'boom' }, 500], 'POST /transactions': [{ detail: 'boom' }, 500] })
    vi.spyOn(console, 'error').mockImplementation(() => {})

    renderApp(<TransactionsDisplay />)

    expect(await screen.findByText(/Não foi possível carregar suas transações/)).toBeInTheDocument()
    expect(await screen.findByText('Nenhuma transação ainda.')).toBeInTheDocument()
  })
})
