import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { leaveTo, takePendingConnect } from '../lib/connect'
import { mockApi, renderApp, requestsMade } from '../test/helpers'
import Connect from './connect'

vi.mock('../lib/connect', async (importOriginal) => ({ ...(await importOriginal()), leaveTo: vi.fn() }))

const QUERY =
  '?client_id=abc&app=Claude&redirect_uri=https%3A%2F%2Fclaude.ai%2Fcb&response_type=code&code_challenge=chal&code_challenge_method=S256&state=xyz'

const renderConnect = (search = QUERY) =>
  renderApp(
    <Routes>
      <Route path="/connect" element={<Connect />} />
      <Route path="/login-google" element={<p>Login page</p>} />
    </Routes>,
    { route: `/connect${search}` },
  )

describe('connecting an AI app', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.mocked(leaveTo).mockClear()
  })

  it('says what the app can and cannot do, and asks', () => {
    saveToken('tok')
    renderConnect()

    expect(screen.getByRole('heading', { name: 'Conectar Claude?' })).toBeInTheDocument()
    expect(screen.getByText(/adicioná-las depois que você confirmar/)).toBeInTheDocument()
    expect(screen.getByText(/Ele não consegue apagar nem alterar nada/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Permitir' })).toBeInTheDocument()
  })

  it('sends the answer as the signed-in person and goes where the server says', async () => {
    saveToken('tok')
    const api = mockApi({ 'POST /oauth/authorize': { data: { redirect_to: 'https://claude.ai/cb?code=c&state=xyz' } } })
    renderConnect()

    await userEvent.click(screen.getByRole('button', { name: 'Permitir' }))

    await waitFor(() => expect(leaveTo).toHaveBeenCalledWith('https://claude.ai/cb?code=c&state=xyz'))
    const [, options] = api.mock.calls[0]
    expect(options.headers.Authorization).toBe('Bearer tok')
    expect(JSON.parse(options.body)).toEqual({
      client_id: 'abc',
      redirect_uri: 'https://claude.ai/cb',
      response_type: 'code',
      code_challenge: 'chal',
      code_challenge_method: 'S256',
      state: 'xyz',
      allow: true,
    })
  })

  it('sends "no" when the person refuses', async () => {
    saveToken('tok')
    const api = mockApi({ 'POST /oauth/authorize': { data: { redirect_to: 'https://claude.ai/cb?error=access_denied' } } })
    renderConnect()

    await userEvent.click(screen.getByRole('button', { name: 'Negar' }))

    await waitFor(() => expect(leaveTo).toHaveBeenCalledWith('https://claude.ai/cb?error=access_denied'))
    expect(JSON.parse(api.mock.calls[0][1].body).allow).toBe(false)
  })

  it('stays put and says so when the server refuses', async () => {
    saveToken('tok')
    mockApi({ 'POST /oauth/authorize': [{ detail: 'This app is not registered.' }, 400] })
    vi.spyOn(console, 'error').mockImplementation(() => {})
    renderConnect()

    await userEvent.click(screen.getByRole('button', { name: 'Permitir' }))

    expect(await screen.findByText(/Não foi possível concluir/)).toBeInTheDocument()
    expect(leaveTo).not.toHaveBeenCalled()
  })

  it('sends a person who is not signed in to the login and remembers the question', async () => {
    const api = mockApi({})
    renderConnect()

    expect(await screen.findByText('Login page')).toBeInTheDocument()
    expect(requestsMade(api)).toEqual([]) // nothing is decided before the person signs in
    expect(takePendingConnect()).toBe(QUERY)
    expect(takePendingConnect()).toBeNull() // and it is given back only once
  })

  it('does not ask anything when it was not opened by an app', () => {
    saveToken('tok')
    renderConnect('?client_id=abc')

    expect(screen.getByText(/Abra-a pelo aplicativo/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Permitir' })).not.toBeInTheDocument()
  })
})
