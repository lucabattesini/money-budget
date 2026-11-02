import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { getToken } from '../lib/auth'
import customToaster from '../utils/customToaster'
import { mockApi, renderApp, requestsMade } from '../test/helpers'

vi.mock('../utils/customToaster', () => ({ default: vi.fn() }))

// The real button loads Google's script; stand in for it with one that "signs in" on click.
vi.mock('@react-oauth/google', () => ({
  GoogleLogin: ({ onSuccess, onError }) => (
    <>
      <button onClick={() => onSuccess({ credential: 'google-id-token' })}>Sign in with Google</button>
      <button onClick={() => onError()}>Google fails</button>
    </>
  ),
}))

async function renderLogin(route = '/login-google') {
  const { default: LoginGoogle } = await import('./login-google')
  return renderApp(
    <Routes>
      <Route path="/login-google" element={<LoginGoogle />} />
      <Route path="/" element={<p>Dashboard page</p>} />
    </Routes>,
    { route },
  )
}

describe('login with Google', () => {
  beforeEach(() => {
    vi.resetModules() // the page reads VITE_GOOGLE_CLIENT_ID once, when it is loaded
    vi.mocked(customToaster).mockClear()
  })

  it('welcomes the user and offers the Google button', async () => {
    await renderLogin()

    expect(screen.getByText('Bem-vindo de volta!')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in with Google' })).toBeInTheDocument()
  })

  it('warns the developer, and shows no Google button, when the client id is missing', async () => {
    vi.stubEnv('VITE_GOOGLE_CLIENT_ID', '')

    await renderLogin()

    expect(screen.getByText(/Google Client ID não configurado/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Sign in with Google' })).not.toBeInTheDocument()
  })

  it('saves the token and goes to the dashboard after a successful login', async () => {
    const api = mockApi({ 'POST /auth/google': { data: { token: 'app-token', user: { id: 1 } } } })
    await renderLogin()

    await userEvent.click(screen.getByRole('button', { name: 'Sign in with Google' }))

    await waitFor(() => expect(screen.getByText('Dashboard page')).toBeInTheDocument())
    expect(getToken()).toBe('app-token')
    expect(JSON.parse(api.mock.calls[0][1].body)).toEqual({ id_token: 'google-id-token', whatsapp_phone: null })
  })

  it('passes the phone from the sign-up link to the back-end', async () => {
    const api = mockApi({ 'POST /auth/google': { data: { token: 'app-token' } } })
    await renderLogin('/login-google?phone=5511999990000')

    await userEvent.click(screen.getByRole('button', { name: 'Sign in with Google' }))

    await waitFor(() => expect(api).toHaveBeenCalled())
    expect(JSON.parse(api.mock.calls[0][1].body).whatsapp_phone).toBe('5511999990000')
  })

  it('stays on the login page and saves nothing when the back-end refuses the login', async () => {
    const api = mockApi({ 'POST /auth/google': [{ detail: 'Invalid Google token' }, 401] })
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})
    await renderLogin()

    await userEvent.click(screen.getByRole('button', { name: 'Sign in with Google' }))

    // wait until the failure has been handled (the API client logs it), then let the page react
    await waitFor(() => expect(log).toHaveBeenCalled())
    await act(async () => {})
    expect(requestsMade(api)).toEqual(['POST /auth/google'])
    expect(getToken()).toBeNull()
    expect(screen.queryByText('Dashboard page')).not.toBeInTheDocument()
  })

  it('tells the user when the login fails', async () => {
    mockApi({ 'POST /auth/google': [{ detail: 'Invalid Google token' }, 401] })
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})
    await renderLogin()

    await userEvent.click(screen.getByRole('button', { name: 'Sign in with Google' }))

    await waitFor(() => expect(log).toHaveBeenCalled())
    await act(async () => {})
    expect(customToaster).toHaveBeenCalledWith('Error', 'error', expect.any(String))
  })

  it('does not break when Google itself reports an error', async () => {
    const log = vi.spyOn(console, 'error').mockImplementation(() => {})
    await renderLogin()

    await userEvent.click(screen.getByRole('button', { name: 'Google fails' }))

    expect(log).toHaveBeenCalledWith('Google login failed')
  })
})
