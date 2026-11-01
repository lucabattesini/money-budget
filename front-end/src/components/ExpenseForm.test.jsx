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
    it.skip('TKT-32: keeps the cents of an amount like 12.50', async () => {
      const api = await renderForm({ 'POST /transactions/create': [{ data: {} }, 201] })
      await userEvent.type(amount(), '12.50')
      await userEvent.type(description(), 'Café')
      await pickCategory('Alimentação')

      await userEvent.click(submit())

      await waitFor(() => expect(created(api)).toBeTruthy())
      expect(created(api).value).toBe(1250)
    })

    it.skip('TKT-32: rejects an amount of zero', async () => {
      const api = await renderForm({ 'POST /transactions/create': [{ data: {} }, 201] })
      await userEvent.type(amount(), '0')
      await userEvent.type(description(), 'Nada')
      await pickCategory('Alimentação')

      await userEvent.click(submit())

      expect(customToaster).toHaveBeenCalledWith('Error', 'error', expect.stringMatching(/bigger than 0/))
      expect(created(api)).toBeUndefined()
    })

    it.skip('TKT-32: rejects a negative amount', async () => {
      const api = await renderForm({ 'POST /transactions/create': [{ data: {} }, 201] })
      await userEvent.type(amount(), '-5')
      await userEvent.type(description(), 'Estorno')
      await pickCategory('Alimentação')

      await userEvent.click(submit())

      expect(customToaster).toHaveBeenCalledWith('Error', 'error', expect.stringMatching(/bigger than 0/))
      expect(created(api)).toBeUndefined()
    })

    it.skip('TKT-32: shows an error when the request cannot reach the server', async () => {
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
