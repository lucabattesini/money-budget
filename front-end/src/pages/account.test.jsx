import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { getToken, saveToken } from '../lib/auth'
import customToaster from '../utils/customToaster'
import { mockApi, renderApp, requestsMade } from '../test/helpers'
import Account from './account'

vi.mock('../utils/customToaster', () => ({ default: vi.fn() }))

const ME = { data: { name: 'Clara Batt', email: 'clara@example.com', picture: null, whatsapp_phone: '5511999990000' } }

describe('account page', () => {
  it('shows the profile and the saved WhatsApp number', async () => {
    saveToken('tok')
    mockApi({ 'GET /user/me': ME })

    renderApp(<Account />)

    expect(await screen.findByText('Clara Batt')).toBeInTheDocument()
    expect(screen.getByText('clara@example.com')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('+55 51 99999-9999')).toHaveValue('5511999990000')
  })

  it('asks for the profile with the stored token', async () => {
    saveToken('tok')
    const api = mockApi({ 'GET /user/me': ME })

    renderApp(<Account />)
    await screen.findByText('Clara Batt')

    expect(api.mock.calls[0][1].headers.Authorization).toBe('Bearer tok')
  })

  it('does not ask for a profile without a token', async () => {
    const api = mockApi({})

    renderApp(<Account />)

    expect(await screen.findByText('Minha Conta')).toBeInTheDocument()
    expect(api).not.toHaveBeenCalled()
  })

  it('saves a new number and confirms with "Salvo!"', async () => {
    saveToken('tok')
    const api = mockApi({
      'GET /user/me': ME,
      'PATCH /user/me/phone': { data: { whatsapp_phone: '5551888880000' } },
    })
    renderApp(<Account />)
    const input = await screen.findByPlaceholderText('+55 51 99999-9999')

    await userEvent.clear(input)
    await userEvent.type(input, '5551888880000')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar número' }))

    expect(await screen.findByRole('button', { name: 'Salvo!' })).toBeInTheDocument()
    const patch = api.mock.calls.find(([, o]) => o?.method === 'PATCH')
    expect(JSON.parse(patch[1].body)).toEqual({ whatsapp_phone: '5551888880000' })
  })

  it('does not say "Salvo!" when the number was not saved', async () => {
    saveToken('tok')
    mockApi({ 'GET /user/me': ME, 'PATCH /user/me/phone': [{ detail: 'taken' }, 409] })
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderApp(<Account />)
    await screen.findByText('Clara Batt')

    await userEvent.click(screen.getByRole('button', { name: 'Salvar número' }))

    // wait until the failure has been handled (the API client logs it), then let the page react
    await waitFor(() => expect(log).toHaveBeenCalled())
    await act(async () => {})
    expect(screen.getByRole('button', { name: 'Salvar número' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Salvo!' })).not.toBeInTheDocument()
  })

  it.skip('TKT-32: tells the user why the number was not saved', async () => {
    saveToken('tok')
    mockApi({ 'GET /user/me': ME, 'PATCH /user/me/phone': [{ detail: 'taken' }, 409] })
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})
    renderApp(<Account />)
    await screen.findByText('Clara Batt')

    await userEvent.click(screen.getByRole('button', { name: 'Salvar número' }))

    await waitFor(() => expect(log).toHaveBeenCalled())
    await act(async () => {})
    expect(customToaster).toHaveBeenCalledWith('Error', 'error', expect.any(String))
  })

  it('logs out: forgets the token and goes back to the start', async () => {
    saveToken('tok')
    mockApi({ 'GET /user/me': ME })
    const location = { href: 'http://localhost/#/account' }
    vi.stubGlobal('location', location)
    renderApp(<Account />)
    await screen.findByText('Clara Batt')

    await userEvent.click(screen.getByRole('button', { name: 'Sair' }))

    expect(getToken()).toBeNull()
    expect(location.href).toBe('/')
  })

  it('only requests the profile once', async () => {
    saveToken('tok')
    const api = mockApi({ 'GET /user/me': ME })

    renderApp(<Account />)
    await screen.findByText('Clara Batt')

    expect(requestsMade(api)).toEqual(['GET /user/me'])
  })
})
