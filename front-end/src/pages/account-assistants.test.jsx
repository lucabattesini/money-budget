import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { jsonResponse, mockApi, renderApp, requestsMade } from '../test/helpers'
import AccountAssistants from './account-assistants'

const CONNECTION = { id: 'g1', app: 'Claude', connected_at: '2026-03-10T12:00:00', last_used_at: null }

describe('AI assistants page', () => {
  it('shows the address to give the app and the apps already connected', async () => {
    saveToken('tok')
    mockApi({ 'GET /connections': { data: [CONNECTION] } })

    renderApp(<AccountAssistants />)

    expect(screen.getByText(/\/mcp$/)).toBeInTheDocument()
    const row = within(await screen.findByRole('table', { name: 'Aplicativos conectados' })).getAllByRole('row')[1]
    expect(within(row).getByText('Claude')).toBeInTheDocument()
    expect(within(row).getByText('—')).toBeInTheDocument() // never used yet
  })

  it('says when nothing is connected', async () => {
    saveToken('tok')
    mockApi({ 'GET /connections': { data: [] } })

    renderApp(<AccountAssistants />)

    expect(await screen.findByText('Nenhum aplicativo conectado.')).toBeInTheDocument()
  })

  it('disconnects an app and shows the list again', async () => {
    saveToken('tok')
    let connections = [CONNECTION]
    const api = mockApi({
      'GET /connections': () => jsonResponse({ data: connections }),
      'DELETE /connections/g1': () => {
        connections = []
        return Promise.resolve(new Response(null, { status: 204 }))
      },
    })
    renderApp(<AccountAssistants />)

    await userEvent.click(await screen.findByRole('button', { name: 'Desconectar Claude' }))

    expect(await screen.findByText('Nenhum aplicativo conectado.')).toBeInTheDocument()
    expect(requestsMade(api)).toEqual(['GET /connections', 'DELETE /connections/g1', 'GET /connections'])
  })

  it('says so when the list cannot be loaded', async () => {
    saveToken('tok')
    mockApi({ 'GET /connections': [{}, 500] })
    vi.spyOn(console, 'error').mockImplementation(() => {})

    renderApp(<AccountAssistants />)

    await waitFor(() => expect(screen.getByText(/Não foi possível carregar as conexões/)).toBeInTheDocument())
  })
})
