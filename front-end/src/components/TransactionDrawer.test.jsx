import { useState } from 'react'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { setLocale } from '../lib/locale'
import { jsonResponse, mockApi, renderApp } from '../test/helpers'
import TransactionDrawer from './TransactionDrawer'
import customToaster from '../utils/customToaster'

vi.mock('../utils/customToaster', () => ({ default: vi.fn() }))

const CATEGORIES = [{ id: 1, name: 'Alimentação' }, { id: 2, name: 'Transporte' }]

const amount = () => screen.getByLabelText('Valor')
const description = () => screen.getByLabelText('Descrição')
const category = () => screen.getByLabelText('Categoria')
const save = () => screen.getByRole('button', { name: 'Salvar' })
const created = (api) => {
  const call = api.mock.calls.find(([url]) => url.endsWith('/transactions/create'))
  return call && JSON.parse(call[1].body)
}

function renderDrawer(routes = {}, { open = true } = {}) {
  saveToken('tok')
  const api = mockApi({ 'POST /transactions/create': () => jsonResponse({ data: {} }, 201), ...routes })
  const onClose = vi.fn()
  const onSaved = vi.fn()
  renderApp(<TransactionDrawer open={open} onClose={onClose} onSaved={onSaved} categories={CATEGORIES} />)
  return { api, onClose, onSaved }
}

describe('transaction sidebar', () => {
  beforeEach(() => {
    vi.mocked(customToaster).mockClear()
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date('2026-03-15T15:00:00Z')) // noon in Brasília, the family's clock
  })

  it('shows nothing until it is opened', () => {
    renderDrawer({}, { open: false })

    expect(screen.queryByText('Nova transação')).not.toBeInTheDocument()
  })

  it('marks the fields that must be filled in as required, and says so', async () => {
    renderDrawer()

    expect(amount()).toBeRequired()
    expect(screen.getByLabelText('Data')).toBeRequired()
    expect(description()).toBeRequired()
    expect(category()).toBeRequired()
    expect(screen.getByRole('radio', { name: 'Débito' })).not.toBeRequired() // always has a value
    expect(screen.getByText('campo obrigatório')).toBeInTheDocument()
  })

  it('offers the categories to choose from', async () => {
    renderDrawer()

    expect(await screen.findByRole('option', { name: 'Alimentação' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Transporte' })).toBeInTheDocument()
  })

  it('shows the currency of the family before the amount', async () => {
    setLocale({ currency: 'CAD', language: 'en' })
    renderDrawer()

    await userEvent.type(amount(), '2550')

    expect(screen.getByText('CA$')).toBeInTheDocument()
    expect(amount()).toHaveValue('25.50')
    expect(screen.getByRole('textbox', { name: 'Valor em dólares canadenses (CA$)' })).toBe(amount())
  })

  it('masks the amount while typing: always two decimals, comma, dot between thousands', async () => {
    renderDrawer()

    await userEvent.type(amount(), '5')
    expect(amount()).toHaveValue('0,05')
    await userEvent.type(amount(), '5')
    expect(amount()).toHaveValue('0,55')
    await userEvent.type(amount(), '0')
    expect(amount()).toHaveValue('5,50')
    await userEvent.type(amount(), '1234')
    expect(amount()).toHaveValue('55.012,34')
  })

  it('ignores letters in the amount', async () => {
    renderDrawer()

    await userEvent.type(amount(), 'ab')

    expect(amount()).toHaveValue('')
  })

  it('saves the amount in cents, without losing the decimals, and closes', async () => {
    const { api, onSaved, onClose } = renderDrawer()
    await userEvent.type(amount(), '2550')
    await userEvent.type(description(), '  Almoço ')
    await userEvent.selectOptions(category(), 'Transporte')

    await userEvent.click(save())

    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1))
    expect(created(api)).toEqual({
      label: 'Almoço', value: 2550, category_id: 2, type: 'debit', transactioned_at: '2026-03-15T12:00:00',
    })
    expect(api.mock.calls.find(([url]) => url.endsWith('/transactions/create'))[1].headers.Authorization).toBe('Bearer tok')
    expect(onClose).toHaveBeenCalled()
    expect(customToaster).toHaveBeenCalledWith('Salvo', 'success', expect.any(String))
  })

  it.each([
    ['no amount', { amount: '', text: 'x', pick: 'Alimentação' }, 'Informe um valor maior que zero'],
    ['a zero amount', { amount: '0', text: 'x', pick: 'Alimentação' }, 'Informe um valor maior que zero'],
    ['no description', { amount: '100', text: '   ', pick: 'Alimentação' }, 'Informe uma descrição'],
    ['no category', { amount: '100', text: 'x', pick: null }, 'Escolha uma categoria'],
  ])('does not save with %s and says what is wrong', async (_name, input, message) => {
    const { api, onSaved } = renderDrawer()
    if (input.amount) await userEvent.type(amount(), input.amount)
    await userEvent.type(description(), input.text)
    if (input.pick) await userEvent.selectOptions(category(), input.pick)

    await userEvent.click(save())

    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(created(api)).toBeUndefined()
    expect(onSaved).not.toHaveBeenCalled()
  })

  it('keeps the form open and tells the user when the server refuses', async () => {
    const { onSaved, onClose } = renderDrawer({
      'POST /transactions/create': () => jsonResponse({ detail: 'Category not found' }, 404),
    })
    await userEvent.type(amount(), '100')
    await userEvent.type(description(), 'x')
    await userEvent.selectOptions(category(), 'Alimentação')

    await userEvent.click(save())

    await waitFor(() => expect(customToaster).toHaveBeenCalledWith('Erro', 'error', expect.any(String)))
    expect(onSaved).not.toHaveBeenCalled()
    expect(onClose).not.toHaveBeenCalled()
    expect(description()).toHaveValue('x') // what the user typed is still there
  })

  it('keeps the form open and tells the user when the server cannot be reached', async () => {
    const { onSaved } = renderDrawer({
      'POST /transactions/create': () => Promise.reject(new TypeError('Failed to fetch')),
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})
    await userEvent.type(amount(), '100')
    await userEvent.type(description(), 'x')
    await userEvent.selectOptions(category(), 'Alimentação')

    await userEvent.click(save())

    await waitFor(() => expect(customToaster).toHaveBeenCalledWith('Erro', 'error', expect.any(String)))
    expect(onSaved).not.toHaveBeenCalled()
  })

  it('is a debit by default and can be saved as a credit', async () => {
    const { api } = renderDrawer()
    expect(screen.getByRole('radio', { name: 'Débito' })).toBeChecked()
    await userEvent.click(screen.getByRole('radio', { name: 'Crédito' }))
    await userEvent.type(amount(), '150000')
    await userEvent.type(description(), 'Salário')
    await userEvent.selectOptions(category(), 'Alimentação')

    await userEvent.click(save())

    await waitFor(() => expect(created(api)).toMatchObject({ type: 'credit', value: 150000 }))
  })

  it('starts on today and saves the chosen day with the current time', async () => {
    const { api } = renderDrawer()
    expect(screen.getByLabelText('Data')).toHaveValue('2026-03-15')
    fireEvent.change(screen.getByLabelText('Data'), { target: { value: '2026-03-01' } })
    await userEvent.type(amount(), '100')
    await userEvent.type(description(), 'x')
    await userEvent.selectOptions(category(), 'Alimentação')

    await userEvent.click(save())

    await waitFor(() => expect(created(api).transactioned_at).toBe('2026-03-01T12:00:00'))
  })

  it('starts on the family\'s today, not the device\'s: 22:30 on 31 March in Brasília is already April in UTC', async () => {
    vi.setSystemTime(new Date('2026-04-01T01:30:00Z'))
    const { api } = renderDrawer()
    expect(screen.getByLabelText('Data')).toHaveValue('2026-03-31')
    await userEvent.type(amount(), '100')
    await userEvent.type(description(), 'x')
    await userEvent.selectOptions(category(), 'Alimentação')

    await userEvent.click(save())

    await waitFor(() => expect(created(api).transactioned_at).toBe('2026-03-31T22:30:00'))
  })

  it.each([
    ['no date', '', 'Informe a data'],
    ['a date in the future', '2026-03-16', 'A data não pode ser no futuro'],
  ])('does not save with %s', async (_name, value, message) => {
    const { api } = renderDrawer()
    fireEvent.change(screen.getByLabelText('Data'), { target: { value } })
    await userEvent.type(amount(), '100')
    await userEvent.type(description(), 'x')
    await userEvent.selectOptions(category(), 'Alimentação')

    await userEvent.click(save())

    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(created(api)).toBeUndefined()
  })

  it('closes without saving when cancelled', async () => {
    const { api, onClose } = renderDrawer()

    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

    expect(onClose).toHaveBeenCalled()
    expect(created(api)).toBeUndefined()
  })

  it('starts empty each time it is opened', async () => {
    saveToken('tok')
    mockApi({})
    function Harness() {
      const [open, setOpen] = useState(true)
      return (
        <>
          <button onClick={() => setOpen(true)}>reabrir</button>
          <TransactionDrawer open={open} onClose={() => setOpen(false)} onSaved={() => {}} categories={CATEGORIES} />
        </>
      )
    }
    renderApp(<Harness />)
    await userEvent.type(await screen.findByLabelText('Valor'), '100')
    await userEvent.type(description(), 'sobrou')

    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(screen.queryByLabelText('Valor')).not.toBeInTheDocument())
    await userEvent.click(screen.getByRole('button', { name: 'reabrir' }))

    expect(await screen.findByLabelText('Valor')).toHaveValue('')
    expect(description()).toHaveValue('')
  })
})
