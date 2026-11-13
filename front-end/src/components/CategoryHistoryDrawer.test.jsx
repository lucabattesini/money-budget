import { useState } from 'react'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { jsonResponse, mockApi, renderApp, requestsMade } from '../test/helpers'
import CategoryHistoryDrawer from './CategoryHistoryDrawer'

const ID = '7c1f5f0e-52a4-4d8c-9b7e-0a6c1d2f3e44'
const CATEGORY = { id: ID, name: '🍽️ Restaurantes e Bares' }

const history = (overrides = {}) => ({
  category: { id: ID, name: CATEGORY.name, group_name: 'Alimentação' },
  month: '2026-11',
  transactions_month: '2026-11',
  history: [
    { month: '2026-06', budgeted: null, spent: 0 },
    { month: '2026-07', budgeted: 50000, spent: 30000 },
    { month: '2026-08', budgeted: 50000, spent: 52000 },
    { month: '2026-09', budgeted: 50000, spent: 40000 },
    { month: '2026-10', budgeted: 50000, spent: 20000 },
    { month: '2026-11', budgeted: 50000, spent: 12000 },
  ],
  transactions: [
    { id: 't2', label: 'Padaria', value: 3000, transactioned_at: '2026-11-20T09:00:00', excluded: false, user_name: 'Clara Battesini' },
    { id: 't1', label: 'Pizza', value: 9000, transactioned_at: '2026-11-03T20:00:00', excluded: false, user_name: 'Bia Souza' },
    { id: 't0', label: 'Transferência', value: 700, transactioned_at: '2026-11-10T08:00:00', excluded: true, user_name: 'Clara Battesini' },
  ],
  ...overrides,
})

const URL_NOV = `GET /budgets/categories/${ID}?month=2026-11&months=6&show=2026-11`

function Harness({ month = '2026-11', onUseBudget }) {
  const [open, setOpen] = useState(true)
  return <CategoryHistoryDrawer category={CATEGORY} month={month} open={open} onClose={() => setOpen(false)} onUseBudget={onUseBudget} />
}

describe('category history panel', () => {
  beforeEach(() => saveToken('tok'))

  it('shows the months against the plan, the average, and the transactions of the month', async () => {
    mockApi({ [URL_NOV]: { data: history() } })

    renderApp(<Harness />)

    const months = await screen.findByRole('group', { name: 'Gasto de Restaurantes e Bares por mês' })
    expect(within(months).getAllByRole('button')).toHaveLength(6)
    expect(within(months).getByRole('button', { name: /agosto de 2026: gasto R\$ 520 de R\$ 500/ })).toBeInTheDocument()
    expect(within(months).getByRole('button', { name: /junho de 2026: gasto R\$ 0$/ })).toBeInTheDocument() // no plan then
    expect(screen.getByText('Média por mês')).toBeInTheDocument()
    expect(screen.getByText(/^R\$\s*355$/)).toBeInTheDocument() // the average of the months that are over, from the first with spending: (300+520+400+200)/4
    const list = screen.getByRole('list', { name: 'Transações de Restaurantes e Bares' })
    expect(within(list).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      expect.stringContaining('Padaria'),
      expect.stringContaining('Pizza'),
      expect.stringContaining('Transferência'),
    ])
    expect(within(list).getByText(/fora dos totais/)).toBeInTheDocument()
    expect(within(list).getAllByText(/Clara/)).toHaveLength(2) // the first name of the person it belongs to
    expect(screen.getByRole('link', { name: 'Ver na lista de transações' }).getAttribute('href')).toBe(
      `/transactions?category=${ID}&from=2026-11-01&to=2026-11-30&type=debit`,
    )
  })

  it('shows the transactions of another month when it is tapped, without moving the months', async () => {
    const api = mockApi({
      [URL_NOV]: { data: history() },
      [`GET /budgets/categories/${ID}?month=2026-11&months=6&show=2026-09`]: {
        data: history({ transactions_month: '2026-09', transactions: [{ id: 's1', label: 'Jantar de setembro', value: 4000, transactioned_at: '2026-09-12T20:00:00', excluded: false, user_name: 'Bia Souza' }] }),
      },
    })
    renderApp(<Harness />)
    await screen.findByText('Padaria')

    await userEvent.click(screen.getByRole('button', { name: /setembro de 2026/ }))

    expect(await screen.findByText('Jantar de setembro')).toBeInTheDocument()
    expect(screen.queryByText('Padaria')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /setembro de 2026/ })).toHaveAttribute('aria-pressed', 'true')
    expect(within(screen.getByRole('group', { name: /por mês/ })).getAllByRole('button')).toHaveLength(6)
    expect(requestsMade(api)).toContain(`GET /budgets/categories/${ID}?month=2026-11&months=6&show=2026-09`)
  })

  it('can look at twelve months instead of six', async () => {
    const api = mockApi({
      [URL_NOV]: { data: history() },
      [`GET /budgets/categories/${ID}?month=2026-11&months=12&show=2026-11`]: { data: history() },
    })
    renderApp(<Harness />)
    await screen.findByText('Padaria')

    await userEvent.click(screen.getByRole('button', { name: 'Ver 12 meses' }))

    await waitFor(() => expect(requestsMade(api)).toContain(`GET /budgets/categories/${ID}?month=2026-11&months=12&show=2026-11`))
    expect(await screen.findByRole('button', { name: 'Ver 6 meses' })).toBeInTheDocument()
  })

  it('goes back to the month of the page when the window changes, so the figures and the list agree', async () => {
    const api = mockApi({
      [URL_NOV]: { data: history() },
      [`GET /budgets/categories/${ID}?month=2026-11&months=12&show=2026-11`]: { data: history() },
      [`GET /budgets/categories/${ID}?month=2026-11&months=12&show=2026-07`]: { data: history({ transactions_month: '2026-07' }) },
    })
    renderApp(<Harness />)
    await screen.findByText('Padaria')
    await userEvent.click(screen.getByRole('button', { name: 'Ver 12 meses' }))
    await userEvent.click(await screen.findByRole('button', { name: /julho de 2026/ }))
    await waitFor(() => expect(requestsMade(api)).toContain(`GET /budgets/categories/${ID}?month=2026-11&months=12&show=2026-07`))

    await userEvent.click(await screen.findByRole('button', { name: 'Ver 6 meses' }))

    await waitFor(() => expect(requestsMade(api).filter((request) => request === URL_NOV)).toHaveLength(2))
    expect(screen.getByRole('button', { name: /novembro de 2026/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('says so when there is no spending in the month', async () => {
    mockApi({ [URL_NOV]: { data: history({ transactions: [] }) } })

    renderApp(<Harness />)

    expect(await screen.findByText('Nenhum gasto nesta categoria neste mês.')).toBeInTheDocument()
  })

  it('shows only the error, not the figures of the last answer, when asking again fails', async () => {
    mockApi({
      [URL_NOV]: { data: history() },
      [`GET /budgets/categories/${ID}?month=2026-11&months=6&show=2026-09`]: () => jsonResponse({ detail: 'boom' }, 500),
    })
    renderApp(<Harness />)
    await screen.findByText('Padaria')

    await userEvent.click(screen.getByRole('button', { name: /setembro de 2026/ }))

    expect(await screen.findByText(/Não foi possível carregar o histórico/)).toBeInTheDocument()
    expect(screen.queryByText('Padaria')).not.toBeInTheDocument()
    expect(screen.queryByRole('group', { name: /por mês/ })).not.toBeInTheDocument()
  })

  it('says so when the history cannot be loaded', async () => {
    mockApi({ [URL_NOV]: () => jsonResponse({ detail: 'boom' }, 500) })

    renderApp(<Harness />)

    expect(await screen.findByText(/Não foi possível carregar o histórico/)).toBeInTheDocument()
  })

  describe('suggestions for the budget', () => {
    const suggestion = (name) => screen.getByRole('button', { name: new RegExp(`^${name}:`) })

    it('offers the average, the maximum, the minimum and last month, from the months that are over', async () => {
      mockApi({ [URL_NOV]: { data: history() } })

      renderApp(<Harness onUseBudget={vi.fn()} />)

      await screen.findByText('Padaria')
      // July to October (June had nothing yet, and November is not over): 300, 520, 400, 200
      expect(suggestion('Média')).toHaveAccessibleName(/R\$\s*355 como orçamento/)
      expect(suggestion('Máximo')).toHaveAccessibleName(/R\$\s*520 como orçamento/)
      expect(suggestion('Mínimo')).toHaveAccessibleName(/R\$\s*200 como orçamento/)
      expect(suggestion('Mês passado')).toHaveAccessibleName(/R\$\s*200 como orçamento/)
    })

    it('rounds to whole units, because budgets are meant to be round', async () => {
      const odd = history()
      odd.history[1].spent = 30049
      odd.history[2].spent = 52051
      mockApi({ [URL_NOV]: { data: odd } })
      const onUseBudget = vi.fn().mockResolvedValue(true)
      renderApp(<Harness onUseBudget={onUseBudget} />)
      await screen.findByText('Padaria')

      await userEvent.click(suggestion('Máximo'))

      expect(onUseBudget).toHaveBeenCalledWith(52100)
    })

    it('sets the budget to the chosen amount and asks for the history again', async () => {
      const api = mockApi({ [URL_NOV]: { data: history() } })
      const onUseBudget = vi.fn().mockResolvedValue(true)
      renderApp(<Harness onUseBudget={onUseBudget} />)
      await screen.findByText('Padaria')

      await userEvent.click(suggestion('Média'))

      expect(onUseBudget).toHaveBeenCalledWith(35500)
      await waitFor(() => expect(requestsMade(api).filter((request) => request === URL_NOV)).toHaveLength(2))
    })

    it('does not ask for the history again when the budget could not be saved', async () => {
      const api = mockApi({ [URL_NOV]: { data: history() } })
      const onUseBudget = vi.fn().mockResolvedValue(false)
      renderApp(<Harness onUseBudget={onUseBudget} />)
      await screen.findByText('Padaria')

      await userEvent.click(suggestion('Mínimo'))

      expect(onUseBudget).toHaveBeenCalledWith(20000)
      await waitFor(() => expect(suggestion('Mínimo')).toBeEnabled())
      expect(requestsMade(api).filter((request) => request === URL_NOV)).toHaveLength(1)
    })

    it('does not offer a chip of R$ 0, which would plan "spend nothing"', async () => {
      mockApi({
        [URL_NOV]: {
          data: history({
            history: [
              { month: '2026-09', budgeted: null, spent: 4000 },
              { month: '2026-10', budgeted: null, spent: 0 },
              { month: '2026-11', budgeted: null, spent: 100 },
            ],
          }),
        },
      })

      renderApp(<Harness onUseBudget={vi.fn()} />)

      await screen.findByText('Padaria')
      expect(screen.getByRole('button', { name: /^Máximo:/ })).toBeInTheDocument() // R$ 40
      expect(screen.queryByRole('button', { name: /^Mínimo:/ })).not.toBeInTheDocument() // October had nothing: R$ 0
    })

    it('offers nothing while there is no month that is over with any spending', async () => {
      mockApi({ [URL_NOV]: { data: history({ history: [{ month: '2026-10', budgeted: null, spent: 0 }, { month: '2026-11', budgeted: null, spent: 5000 }] }) } })

      renderApp(<Harness onUseBudget={vi.fn()} />)

      await screen.findByText('Padaria')
      expect(screen.queryByRole('group', { name: 'Sugestões de orçamento' })).not.toBeInTheDocument()
    })
  })
})
