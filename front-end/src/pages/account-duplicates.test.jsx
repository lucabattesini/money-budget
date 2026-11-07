import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { mockApi, renderApp } from '../test/helpers'
import AccountDuplicates from './account-duplicates'

const tx = (id, label) => ({
  id, label, value: 2500, type: 'debit', transactioned_at: '2026-03-10T10:00:00', category_name: 'Alimentação', user_name: 'Clara Battesini',
})
const GROUPS = [
  [tx('a1', 'Padaria'), tx('a2', 'PADARIA SP')],
  [tx('b1', 'Cinema'), tx('b2', 'Cinema 2'), tx('b3', 'Cinema 3')],
]
const bodyOf = (mock, request) => {
  const call = mock.mock.calls.find(([url, o = {}]) => `${(o.method || 'GET').toUpperCase()} ${String(url).replace('http://api.test', '')}` === request)
  return call && JSON.parse(call[1].body)
}

describe('duplicates page', () => {
  beforeEach(() => {
    saveToken('tok')
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 2, 15, 12, 0, 0))
  })

  it('searches the last three months by default, and the range can be changed', async () => {
    const mock = mockApi({ 'POST /transactions/duplicates': { data: [] } })
    renderApp(<AccountDuplicates />)
    expect(screen.getByLabelText('De')).toHaveValue('2025-12-15')
    expect(screen.getByLabelText('Até')).toHaveValue('2026-03-15')

    await userEvent.clear(screen.getByLabelText('De'))
    await userEvent.type(screen.getByLabelText('De'), '2026-01-05')
    await userEvent.click(screen.getByRole('button', { name: 'Procurar' }))

    expect(await screen.findByText('Nenhuma duplicata encontrada nesse período.')).toBeInTheDocument()
    expect(bodyOf(mock, 'POST /transactions/duplicates')).toEqual({ start_date: '2026-01-05', end_date: '2026-03-15', ignore_excluded: false })
  })

  it('can leave out the transactions that do not count in the totals', async () => {
    const mock = mockApi({ 'POST /transactions/duplicates': { data: [] } })
    renderApp(<AccountDuplicates />)

    await userEvent.click(screen.getByRole('checkbox', { name: 'Ignorar as que não contam nos totais' }))
    await userEvent.click(screen.getByRole('button', { name: 'Procurar' }))

    await screen.findByText('Nenhuma duplicata encontrada nesse período.')
    expect(bodyOf(mock, 'POST /transactions/duplicates')).toMatchObject({ ignore_excluded: true })
  })

  it('does not search when the first day is after the last', async () => {
    const mock = mockApi({})
    renderApp(<AccountDuplicates />)

    await userEvent.clear(screen.getByLabelText('Até'))
    await userEvent.type(screen.getByLabelText('Até'), '2026-02-01')

    expect(screen.getByText('A data inicial não pode ser depois da final')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Procurar' })).toBeDisabled()
    expect(mock).not.toHaveBeenCalled()
  })

  it('keeps the first of each group by default and deletes the rest only after a confirmation', async () => {
    const mock = mockApi({
      'POST /transactions/duplicates': { data: GROUPS },
      'POST /transactions/bulk-delete': { data: { deleted: 3 } },
    })
    renderApp(<AccountDuplicates />)
    await userEvent.click(screen.getByRole('button', { name: 'Procurar' }))

    await screen.findByText('2 grupos encontrados')
    const [padaria, cinema] = screen.getAllByRole('radiogroup').map((box) => within(box).getAllByRole('radio'))
    expect(padaria[0]).toBeChecked()
    expect(cinema[0]).toBeChecked()
    await userEvent.click(cinema[2]) // change my mind in one group: keep the third

    await userEvent.click(screen.getByRole('button', { name: 'Excluir 3 duplicadas' }))
    const confirm = within((await screen.findByText('Excluir 3 transações?')).closest('[role="alertdialog"]'))
    expect(bodyOf(mock, 'POST /transactions/bulk-delete')).toBeUndefined() // not yet
    await userEvent.click(confirm.getByRole('button', { name: 'Excluir' }))

    await waitFor(() => expect(bodyOf(mock, 'POST /transactions/bulk-delete')).toEqual({ ids: ['a2', 'b1', 'b2'] }))
  })

  it('leaves alone a group marked "manter todas", and never lists every member of a group for deletion', async () => {
    mockApi({ 'POST /transactions/duplicates': { data: GROUPS } })
    renderApp(<AccountDuplicates />)
    await userEvent.click(screen.getByRole('button', { name: 'Procurar' }))
    await screen.findByText('2 grupos encontrados')

    const groupBoxes = screen.getAllByRole('radiogroup')
    const keepAll = (box) => within(box).getByRole('radio', { name: /Manter todas/ })
    await userEvent.click(keepAll(groupBoxes[1]))

    expect(screen.getByRole('button', { name: 'Excluir 1 duplicada' })).toBeEnabled()
    await userEvent.click(keepAll(groupBoxes[0]))
    expect(screen.getByRole('button', { name: 'Excluir 0 duplicadas' })).toBeDisabled()
  })

  it('tells the user when the search fails', async () => {
    mockApi({ 'POST /transactions/duplicates': [{ detail: 'boom' }, 500] })
    renderApp(<AccountDuplicates />)

    await userEvent.click(screen.getByRole('button', { name: 'Procurar' }))

    expect(await screen.findByText(/Não foi possível procurar duplicatas/)).toBeInTheDocument()
  })

  it('does not offer to delete more than the server accepts at once', async () => {
    const big = Array.from({ length: 501 }, (_, n) => [tx(`k${n}`, 'Café'), tx(`d${n}`, 'CAFE')])
    mockApi({ 'POST /transactions/duplicates': { data: big } })
    renderApp(<AccountDuplicates />)

    await userEvent.click(screen.getByRole('button', { name: 'Procurar' }))

    await screen.findByText('501 grupos encontrados')
    expect(screen.getByRole('button', { name: 'Excluir 501 duplicadas' })).toBeDisabled()
    expect(screen.getByText(/mais de 500 de uma vez/)).toBeInTheDocument()
  })
})
