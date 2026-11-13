import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { mockApi, renderApp, requestsMade, chooseCategory } from '../test/helpers'
import TransactionsDisplay from './transactions-display'

const FAMILY = {
  data: { me: '1', members: [{ id: '1', name: 'Clara Battesini', picture: null }, { id: '2', name: 'Bia Souza', picture: null }] },
}
const CATEGORIES = { data: [{ id: '1', name: 'Alimentação' }, { id: '2', name: 'Transporte' }] }
const t = (id, label, cents) => ({ id: String(id), label, value: cents, transactioned_at: '2025-01-10T10:00:00', category_id: '1' })
const TRANSACTIONS = { data: [t(1, 'Almoço', 2500), t(2, 'Mercado', 12000), t(3, 'Uber', 1800)] }

const bodies = (mock, request) =>
  mock.mock.calls.filter(([url, o = {}]) => `${(o.method || 'GET').toUpperCase()} ${String(url).replace('http://api.test', '')}` === request)
    .map(([, o]) => JSON.parse(o.body))
const startSelecting = () => userEvent.click(screen.getByRole('button', { name: 'Selecionar' }))
const tick = async (label) => {
  if (!screen.queryByRole('checkbox', { name: `Selecionar ${label}` })) await startSelecting()
  await userEvent.click(screen.getByRole('checkbox', { name: `Selecionar ${label}` }))
}
const dialog = async (title) => within((await screen.findByText(title)).closest('[role="dialog"], [role="alertdialog"]'))

const api = (extra = {}) =>
  mockApi({ 'GET /families/me': FAMILY, 'GET /categories': CATEGORIES, 'POST /transactions': TRANSACTIONS, ...extra })

describe('transactions page: many at once', () => {
  beforeEach(() => saveToken('tok'))

  it('shows no tick boxes until selection mode is on, and hides them again when it is left', async () => {
    api()
    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()

    await startSelecting()
    expect(screen.getByRole('checkbox', { name: 'Selecionar Almoço' })).toBeInTheDocument()
    await tick('Almoço')
    await userEvent.click(screen.getByRole('button', { name: /Cancelar$/ }))

    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.queryByText('1 selecionada')).not.toBeInTheDocument()
  })

  it('shows how many are selected, and nothing to act on while none is', async () => {
    api()
    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')
    expect(screen.queryByRole('button', { name: /editar selecionadas/i })).not.toBeInTheDocument()

    await tick('Almoço')
    await tick('Uber')

    expect(screen.getByText('2 selecionadas')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /limpar seleção/i }))
    expect(screen.queryByText('2 selecionadas')).not.toBeInTheDocument()
  })

  it('in selection mode clicking a row ticks it and does not open the editor', async () => {
    api()
    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    await startSelecting()
    await userEvent.click(screen.getByText('Almoço'))
    expect(screen.getByText('1 selecionada')).toBeInTheDocument()
    await tick('Mercado')

    expect(screen.queryByText('Editar transação')).not.toBeInTheDocument()
  })

  it('changes only what was chosen, on the selected ones, then reads the list again and clears the selection', async () => {
    const mock = api({ 'POST /transactions/bulk-update': { data: { updated: 2 } } })
    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')
    await tick('Almoço')
    await tick('Mercado')

    await userEvent.click(screen.getByRole('button', { name: /editar selecionadas/i }))
    const form = await dialog('Editar 2 transações')
    expect(form.getByRole('button', { name: 'Salvar' })).toBeDisabled() // nothing chosen yet
    await chooseCategory(form.getByRole('combobox', { name: 'Categoria' }), 'Transporte')
    await userEvent.selectOptions(form.getByLabelText('Totais'), 'Não contar nos totais')
    await userEvent.click(form.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(bodies(mock, 'POST /transactions/bulk-update')).toEqual([{ ids: ['1', '2'], category_id: '2', excluded: true }]))
    await waitFor(() => expect(requestsMade(mock).filter((r) => r === 'POST /transactions')).toHaveLength(2))
    await waitFor(() => expect(screen.queryByText('2 selecionadas')).not.toBeInTheDocument())
  })

  it('does not offer merchants while the family does not use them', async () => {
    api()
    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')
    await tick('Almoço')
    await userEvent.click(screen.getByRole('button', { name: /editar selecionadas/i }))

    const form = await dialog('Editar 1 transação')
    expect(form.queryByLabelText('Estabelecimento')).not.toBeInTheDocument()
  })

  it('keeps the selection and says so when the server refuses the change', async () => {
    const mock = api({ 'POST /transactions/bulk-update': [{ detail: 'Transaction not found' }, 404] })
    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')
    await tick('Almoço')
    await userEvent.click(screen.getByRole('button', { name: /editar selecionadas/i }))
    const form = await dialog('Editar 1 transação')
    await userEvent.selectOptions(form.getByLabelText('Quem'), 'Bia Souza')
    await userEvent.click(form.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText(/nada foi alterado|Transaction not found/i)).toBeInTheDocument()
    expect(screen.getByText('1 selecionada')).toBeInTheDocument()
    expect(requestsMade(mock).filter((r) => r === 'POST /transactions')).toHaveLength(1)
  })

  it('"select all" ticks every row shown, and deleting asks first', async () => {
    const mock = api({ 'POST /transactions/bulk-delete': { data: { deleted: 3 } } })
    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')

    await startSelecting()
    await userEvent.click(screen.getByRole('checkbox', { name: /selecionar todas as exibidas/i }))
    expect(screen.getByText('3 selecionadas')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /excluir selecionadas/i }))
    const confirm = await dialog('Excluir 3 transações?')
    expect(bodies(mock, 'POST /transactions/bulk-delete')).toEqual([]) // nothing yet
    await userEvent.click(confirm.getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(screen.queryByText('Excluir 3 transações?')).not.toBeInTheDocument())
    expect(bodies(mock, 'POST /transactions/bulk-delete')).toEqual([])

    await userEvent.click(screen.getByRole('button', { name: /excluir selecionadas/i }))
    await userEvent.click((await dialog('Excluir 3 transações?')).getByRole('button', { name: 'Excluir' }))

    await waitFor(() => expect(bodies(mock, 'POST /transactions/bulk-delete')).toEqual([{ ids: ['1', '2', '3'] }]))
  })

  it('does not act on a selected row that the filters now hide', async () => {
    const mock = api({ 'POST /transactions/bulk-delete': { data: { deleted: 1 } } })
    renderApp(<TransactionsDisplay />, { route: '/transactions?from=2025-01-01&to=2025-01-31' })
    await screen.findByText('Almoço')
    await tick('Uber')

    // the same page, opened with a range that hides everything, has nothing selected
    expect(screen.getByText('1 selecionada')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /excluir selecionadas/i }))
    await userEvent.click((await dialog('Excluir 1 transação?')).getByRole('button', { name: 'Excluir' }))
    await waitFor(() => expect(bodies(mock, 'POST /transactions/bulk-delete')).toEqual([{ ids: ['3'] }]))
  })

  it('opens the editor on "Não alterar" every time, not on what was chosen last time', async () => {
    api({ 'POST /transactions/bulk-update': { data: { updated: 1 } } })
    renderApp(<TransactionsDisplay />)
    await screen.findByText('Almoço')
    await tick('Almoço')
    await userEvent.click(screen.getByRole('button', { name: /editar selecionadas/i }))
    const first = await dialog('Editar 1 transação')
    await chooseCategory(first.getByRole('combobox', { name: 'Categoria' }), 'Transporte')
    await userEvent.click(first.getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(screen.queryByText('Editar 1 transação')).not.toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /editar selecionadas/i }))
    const second = await dialog('Editar 1 transação')
    expect(second.getByRole('combobox', { name: 'Categoria' })).toHaveValue('Não alterar')
    expect(second.getByRole('button', { name: 'Salvar' })).toBeDisabled()
  })

  it('does not offer to act on more than the server accepts at once, and says why', async () => {
    vi.stubGlobal('IntersectionObserver', undefined) // no scrolling in a test: the "Mostrar mais" button puts the rows on the page
    const many = { data: Array.from({ length: 501 }, (_, n) => ({ ...t(n + 1, `Compra ${n + 1}`, 100), transactioned_at: new Date(2026, 2, 15, 12, 0, 0, 0).toISOString().slice(0, 19) })) }
    api({ 'POST /transactions': many })
    renderApp(<TransactionsDisplay />)
    await screen.findByText('Compra 1')
    while (screen.queryByRole('button', { name: 'Mostrar mais' })) await userEvent.click(screen.getByRole('button', { name: 'Mostrar mais' }))

    await startSelecting()
    await userEvent.click(screen.getByRole('checkbox', { name: /selecionar todas as exibidas/i }))

    expect(screen.getByText(/mais de 500 de uma vez/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /excluir selecionadas/i })).toBeDisabled()
    expect(screen.getByRole('button', { name: /editar selecionadas/i })).toBeDisabled()
    vi.unstubAllGlobals()
  }, 30000)
})
