import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { mockApi, renderApp } from '../test/helpers'
import ExpenseForm from './ExpenseForm'
import customToaster from '../utils/customToaster'

vi.mock('../utils/customToaster', () => ({ default: vi.fn() }))

const CATEGORIES = { data: [{ id: 1, name: 'Alimentação' }, { id: 2, name: 'Transporte' }] }

const amount = () => screen.getByPlaceholderText('Amount')
const description = () => screen.getByPlaceholderText('Description')
const submit = () => screen.getByRole('button', { name: 'Submit' })

async function renderForm(routes = {}) {
  saveToken('tok')
  const api = mockApi({ 'GET /categories': CATEGORIES, ...routes })
  renderApp(<ExpenseForm />)
  await screen.findByPlaceholderText('Amount')
  return api
}

async function openCategories() {
  await userEvent.click(screen.getByRole('button', { name: 'Toggle suggestions' }))
}

async function pickCategory(name) {
  await openCategories()
  await userEvent.click(await screen.findByRole('option', { name }))
}

const created = (api) => {
  const call = api.mock.calls.find(([url]) => url.endsWith('/transactions/create'))
  return call && JSON.parse(call[1].body)
}

describe('expense form', () => {
  beforeEach(() => {
    vi.mocked(customToaster).mockClear()
  })

  it('loads the categories with the user token', async () => {
    const api = await renderForm()

    expect(api.mock.calls[0][0]).toBe('http://api.test/categories')
    expect(api.mock.calls[0][1].headers.Authorization).toBe('Bearer tok')
  })

  it('offers the loaded categories to choose from', async () => {
    await renderForm()

    await openCategories()

    expect(await screen.findByRole('option', { name: 'Alimentação' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'Transporte' })).toBeInTheDocument()
  })

  it('lists the categories A-Z, whatever order the server sent them in', async () => {
    await renderForm({
      'GET /categories': { data: [{ id: 3, name: 'Viagem' }, { id: 1, name: 'Água' }, { id: 2, name: 'Aluguel' }] },
    })

    await openCategories()

    const options = await screen.findAllByRole('option')
    expect(options.map((option) => option.textContent)).toEqual(['Água', 'Aluguel', 'Viagem'])
  })

  it('sorts by the words, not by the emoji the name starts with', async () => {
    await renderForm({
      'GET /categories': { data: [{ id: 1, name: '🏠 Zebra' }, { id: 2, name: '🔧 Abacate' }] },
    })

    await openCategories()

    const options = await screen.findAllByRole('option')
    expect(options.map((option) => option.textContent)).toEqual(['🔧 Abacate', '🏠 Zebra'])
  })

  it('narrows the categories as the user types', async () => {
    await renderForm()

    await openCategories()
    // Typed at human speed: the category box re-renders on every key and loses
    // characters when they arrive with no delay at all (see the front-end bugs ticket).
    const typist = userEvent.setup({ delay: 20 })
    await typist.type(screen.getByPlaceholderText('Select category'), 'trans')

    expect(await screen.findByRole('option', { name: 'Transporte' })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: 'Alimentação' })).not.toBeInTheDocument()
  })

  it('saves a transaction in cents and confirms', async () => {
    const api = await renderForm({ 'POST /transactions/create': [{ data: {} }, 201] })

    await userEvent.type(amount(), '25')
    await userEvent.type(description(), 'Almoço')
    await pickCategory('Alimentação')
    await userEvent.click(submit())

    await waitFor(() => expect(customToaster).toHaveBeenCalledWith('Accepted', 'success', 'Your transaction is saved!'))
    expect(created(api)).toEqual({ label: 'Almoço', value: 2500, category_id: 1 })
  })

  it('clears the form after saving', async () => {
    await renderForm({ 'POST /transactions/create': [{ data: {} }, 201] })
    await userEvent.type(amount(), '25')
    await userEvent.type(description(), 'Almoço')
    await pickCategory('Alimentação')

    await userEvent.click(submit())

    await waitFor(() => expect(amount()).toHaveValue(null))
    expect(description()).toHaveValue('')
  })

  it('reports a server error without clearing what the user typed', async () => {
    await renderForm({ 'POST /transactions/create': [{ detail: 'boom' }, 500] })
    await userEvent.type(amount(), '25')
    await userEvent.type(description(), 'Almoço')
    await pickCategory('Alimentação')

    await userEvent.click(submit())

    await waitFor(() => expect(customToaster).toHaveBeenCalledWith(
      'Error', 'error', 'Some error ocurred to report your transaction, please try again later'))
    expect(amount()).toHaveValue(25)
    expect(description()).toHaveValue('Almoço')
  })

  describe('validation (nothing is sent)', () => {
    it('needs an amount', async () => {
      const api = await renderForm()
      await userEvent.type(description(), 'Almoço')
      await pickCategory('Alimentação')

      await userEvent.click(submit())

      expect(customToaster).toHaveBeenCalledWith('Error', 'error', 'The amount value need to be bigger than 0')
      expect(created(api)).toBeUndefined()
    })

    it('needs a description', async () => {
      const api = await renderForm()
      await userEvent.type(amount(), '25')
      await pickCategory('Alimentação')

      await userEvent.click(submit())

      expect(customToaster).toHaveBeenCalledWith('Error', 'error', 'You need to give a description to your transaction')
      expect(created(api)).toBeUndefined()
    })

    it('needs a category', async () => {
      const api = await renderForm()
      await userEvent.type(amount(), '25')
      await userEvent.type(description(), 'Almoço')

      await userEvent.click(submit())

      expect(customToaster).toHaveBeenCalledWith('Error', 'error', 'You need to select a category to your transaction')
      expect(created(api)).toBeUndefined()
    })
  })

  describe('known bugs', () => {
    // Binary floating point: 19.99 * 100 is 1998.9999999999998 and 0.29 * 100 is 28.999999999999996,
    // so a fix that truncates instead of rounding still loses a cent.
    it.each([
      ['12.50', 1250],
      ['19.99', 1999],
      ['0.29', 29],
    ])('keeps the cents of %s', async (typed, cents) => {
      const api = await renderForm({ 'POST /transactions/create': [{ data: {} }, 201] })
      await userEvent.type(amount(), typed)
      await userEvent.type(description(), 'Café')
      await pickCategory('Alimentação')

      await userEvent.click(submit())

      await waitFor(() => expect(created(api)).toBeTruthy())
      expect(created(api).value).toBe(cents)
    })

    it('after saving, a second transaction without a category is rejected', async () => {
      const api = await renderForm({ 'POST /transactions/create': [{ data: {} }, 201] })
      await userEvent.type(amount(), '25')
      await userEvent.type(description(), 'Almoço')
      await pickCategory('Alimentação')
      await userEvent.click(submit())
      await waitFor(() => expect(customToaster).toHaveBeenCalledWith('Accepted', 'success', expect.any(String)))
      customToaster.mockClear()
      api.mockClear()

      await userEvent.type(amount(), '10')
      await userEvent.type(description(), 'Café')
      await userEvent.click(submit()) // no category chosen this time

      expect(customToaster).toHaveBeenCalledWith('Error', 'error', 'You need to select a category to your transaction')
      expect(created(api)).toBeUndefined()
    })

    it('rejects an amount of zero', async () => {
      const api = await renderForm({ 'POST /transactions/create': [{ data: {} }, 201] })
      await userEvent.type(amount(), '0')
      await userEvent.type(description(), 'Nada')
      await pickCategory('Alimentação')

      await userEvent.click(submit())

      expect(customToaster).toHaveBeenCalledWith('Error', 'error', expect.stringMatching(/bigger than 0/))
      expect(created(api)).toBeUndefined()
    })

    it('rejects a negative amount', async () => {
      const api = await renderForm({ 'POST /transactions/create': [{ data: {} }, 201] })
      await userEvent.type(amount(), '-5')
      await userEvent.type(description(), 'Estorno')
      await pickCategory('Alimentação')

      await userEvent.click(submit())

      expect(customToaster).toHaveBeenCalledWith('Error', 'error', expect.stringMatching(/bigger than 0/))
      expect(created(api)).toBeUndefined()
    })

    it('rejects an amount that rounds to zero cents', async () => {
      const api = await renderForm({ 'POST /transactions/create': [{ data: {} }, 201] })
      await userEvent.type(amount(), '0.001')
      await userEvent.type(description(), 'Nada')
      await pickCategory('Alimentação')

      await userEvent.click(submit())

      expect(customToaster).toHaveBeenCalledWith('Error', 'error', expect.stringMatching(/bigger than 0/))
      expect(created(api)).toBeUndefined()
    })

    it('rejects an amount bigger than the database can hold', async () => {
      const api = await renderForm({ 'POST /transactions/create': [{ data: {} }, 201] })
      await userEvent.type(amount(), '99999999999')
      await userEvent.type(description(), 'Muito')
      await pickCategory('Alimentação')

      await userEvent.click(submit())

      expect(customToaster).toHaveBeenCalledWith('Error', 'error', expect.stringMatching(/too big/))
      expect(created(api)).toBeUndefined()
    })

    it('shows an error when the request cannot reach the server', async () => {
      vi.spyOn(console, 'error').mockImplementation(() => {})
      await renderForm({ 'POST /transactions/create': () => Promise.reject(new TypeError('Failed to fetch')) })
      await userEvent.type(amount(), '25')
      await userEvent.type(description(), 'Almoço')
      await pickCategory('Alimentação')

      await userEvent.click(submit())

      await waitFor(() => expect(customToaster).toHaveBeenCalledWith('Error', 'error', expect.any(String)))
    })
  })
})
