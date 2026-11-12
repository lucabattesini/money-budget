import { useState } from 'react'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { setLocale } from '../lib/locale'
import { jsonResponse, mockApi, renderApp, chooseCategory } from '../test/helpers'
import TransactionDrawer from './TransactionDrawer'
import customToaster from '../utils/customToaster'

vi.mock('../utils/customToaster', () => ({ default: vi.fn() }))

const CATEGORIES = [{ id: 1, name: 'Alimentação' }, { id: 2, name: 'Transporte' }]

const amount = () => screen.getByLabelText('Valor')
const description = () => screen.getByLabelText('Descrição')
const category = () => screen.getByRole('combobox', { name: 'Categoria' })
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

  it('marks the fields that must be filled in as required', async () => {
    renderDrawer()

    expect(amount()).toBeRequired()
    expect(screen.getByLabelText('Data')).toBeRequired()
    expect(description()).toBeRequired()
    expect(category()).toBeRequired()
    expect(screen.getByRole('radio', { name: 'Débito' })).not.toBeRequired() // always has a value
    expect(screen.queryByText('campo obrigatório')).not.toBeInTheDocument()
  })

  it('offers the categories to choose from', async () => {
    renderDrawer()

    await userEvent.click(await screen.findByRole('combobox', { name: 'Categoria' }))

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

  it('sends the ids of the category and the person exactly as it got them (they are UUIDs, not numbers)', async () => {
    const CAT = '7c1f5f0e-52a4-4d8c-9b7e-0a6c1d2f3e44'
    const PERSON = '0b9d6a1c-3f58-4e2a-8c47-91d5e6f7a802'
    saveToken('tok')
    const api = mockApi({ 'POST /transactions/create': () => jsonResponse({ data: {} }, 201) })
    renderApp(
      <TransactionDrawer
        open onClose={vi.fn()} onSaved={vi.fn()}
        categories={[{ id: CAT, name: 'Alimentação' }]}
        members={[{ id: PERSON, name: 'Bia Souza', picture: null }, { id: 'other', name: 'Clara', picture: null }]}
        me={PERSON}
      />,
    )
    await userEvent.type(amount(), '1000')
    await userEvent.type(description(), 'Pão')
    await chooseCategory(category(), 'Alimentação')

    await userEvent.click(save())

    await waitFor(() => expect(created(api)).toBeTruthy())
    expect(created(api).category_id).toBe(CAT)
    expect(created(api).user_id).toBe(PERSON)
  })

  it('saves the amount in cents, without losing the decimals, and closes', async () => {
    const { api, onSaved, onClose } = renderDrawer()
    await userEvent.type(amount(), '2550')
    await userEvent.type(description(), '  Almoço ')
    await chooseCategory(category(), 'Transporte')

    await userEvent.click(save())

    await waitFor(() => expect(onSaved).toHaveBeenCalledTimes(1))
    expect(created(api)).toEqual({
      label: 'Almoço', value: 2550, category_id: '2', type: 'debit', transactioned_at: '2026-03-15T12:00:00', excluded: false,
    })
    expect(api.mock.calls.find(([url]) => url.endsWith('/transactions/create'))[1].headers.Authorization).toBe('Bearer tok')
    expect(onClose).toHaveBeenCalled()
    expect(customToaster).toHaveBeenCalledWith('Salvo', 'success', expect.any(String))
  })

  describe('leaving a transaction out of the totals', () => {
    const WITH_GROUPS = [
      { id: 1, name: '🛒 Supermercado', group_name: 'Alimentação' },
      { id: 2, name: '🔄 Transferência', group_name: 'Transferências' },
      { id: 3, name: '🧮 Ajustes de saldo', group_name: 'Transferências' },
    ]
    const checkbox = () => screen.getByRole('checkbox', { name: 'Não contar nos totais' })
    const open = (props = {}) => {
      saveToken('tok')
      const api = mockApi({
        'POST /transactions/create': () => jsonResponse({ data: {} }, 201),
        'PUT /transactions/9': () => jsonResponse({ data: {} }, 200),
      })
      renderApp(<TransactionDrawer open onClose={vi.fn()} onSaved={vi.fn()} categories={WITH_GROUPS} {...props} />)
      return api
    }
    const fill = async () => {
      await userEvent.type(amount(), '1000')
      await userEvent.type(description(), 'Algo')
    }

    it('is unchecked for an ordinary category and sent as counted', async () => {
      const api = open()
      await fill()

      await chooseCategory(category(), '🛒 Supermercado')
      expect(checkbox()).not.toBeChecked()
      await userEvent.click(save())

      await waitFor(() => expect(created(api)).toBeTruthy())
      expect(created(api).excluded).toBe(false)
    })

    it('starts checked for a transfer or a card payment, and the person can uncheck it', async () => {
      const api = open()
      await fill()

      await chooseCategory(category(), '🔄 Transferência')
      expect(checkbox()).toBeChecked()
      await userEvent.click(checkbox())
      await userEvent.click(save())

      await waitFor(() => expect(created(api)).toBeTruthy())
      expect(created(api).excluded).toBe(false)
    })

    it('does not change a choice the person made when they pick another category', async () => {
      open()
      await userEvent.click(checkbox()) // they leave it out themselves
      await chooseCategory(category(), '🛒 Supermercado')
      expect(checkbox()).toBeChecked()

      await chooseCategory(category(), '🔄 Transferência')
      expect(checkbox()).toBeChecked()
    })

    it('follows the category until the person decides, then goes back when the category is not a transfer', async () => {
      open()

      await chooseCategory(category(), '🔄 Transferência')
      expect(checkbox()).toBeChecked()
      await chooseCategory(category(), '🧮 Ajustes de saldo') // a correction: it counts
      expect(checkbox()).not.toBeChecked()
    })

    it('shows an edited transaction as it is, and sends the change', async () => {
      const row = { id: 9, label: 'Mercado', value: 5000, type: 'debit', category_id: 1, transactioned_at: '2026-03-10T10:00:00', excluded: true }
      const api = open({ transaction: row })
      expect(await screen.findByRole('checkbox', { name: 'Não contar nos totais' })).toBeChecked()

      await userEvent.click(checkbox())
      await userEvent.click(save())

      await waitFor(() => expect(api.mock.calls.some(([url, o]) => url.endsWith('/transactions/9') && o.method === 'put')).toBe(true))
      const put = api.mock.calls.find(([url]) => url.endsWith('/transactions/9'))
      expect(JSON.parse(put[1].body).excluded).toBe(false)
    })
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
    if (input.pick) await chooseCategory(category(), input.pick)

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
    await chooseCategory(category(), 'Alimentação')

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
    await chooseCategory(category(), 'Alimentação')

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
    await chooseCategory(category(), 'Alimentação')

    await userEvent.click(save())

    await waitFor(() => expect(created(api)).toMatchObject({ type: 'credit', value: 150000 }))
  })

  it('starts on today and saves the chosen day with the current time', async () => {
    const { api } = renderDrawer()
    expect(screen.getByLabelText('Data')).toHaveValue('2026-03-15')
    fireEvent.change(screen.getByLabelText('Data'), { target: { value: '2026-03-01' } })
    await userEvent.type(amount(), '100')
    await userEvent.type(description(), 'x')
    await chooseCategory(category(), 'Alimentação')

    await userEvent.click(save())

    await waitFor(() => expect(created(api).transactioned_at).toBe('2026-03-01T12:00:00'))
  })

  it('starts on the family\'s today, not the device\'s: 22:30 on 31 March in Brasília is already April in UTC', async () => {
    vi.setSystemTime(new Date('2026-04-01T01:30:00Z'))
    const { api } = renderDrawer()
    expect(screen.getByLabelText('Data')).toHaveValue('2026-03-31')
    await userEvent.type(amount(), '100')
    await userEvent.type(description(), 'x')
    await chooseCategory(category(), 'Alimentação')

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
    await chooseCategory(category(), 'Alimentação')

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
