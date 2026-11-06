import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { mockApi, renderApp, requestsMade } from '../test/helpers'
import AccountMerchants from './account-merchants'

const MERCHANTS = {
  data: [
    { id: 1, name: 'iFood', transactions: 1 },
    { id: 2, name: 'Uber', transactions: 3 },
    { id: 3, name: 'Netflix', transactions: 0 },
  ],
}

beforeEach(() => saveToken('tok'))

describe('merchants page', () => {
  it('lists the merchants with how many transactions use each', async () => {
    mockApi({ 'GET /merchants': MERCHANTS })

    renderApp(<AccountMerchants />)

    const items = within(await screen.findByRole('list', { name: 'Estabelecimentos' })).getAllByRole('listitem')
    expect(items.map((item) => item.textContent)).toEqual(['iFood1 transação', 'Uber3 transações', 'Netflix0 transações'])
  })

  it('says so when there are none, and when they could not be loaded', async () => {
    mockApi({ 'GET /merchants': { data: [] } })
    const { unmount } = renderApp(<AccountMerchants />)
    expect(await screen.findByText('Nenhum estabelecimento ainda.')).toBeInTheDocument()
    unmount()

    vi.spyOn(console, 'error').mockImplementation(() => {})
    mockApi({ 'GET /merchants': [{ detail: 'boom' }, 500] })
    renderApp(<AccountMerchants />)
    expect(await screen.findByText(/Não foi possível carregar os estabelecimentos/)).toBeInTheDocument()
  })

  it('renames one and shows the new name', async () => {
    let name = 'Uber'
    const api = mockApi({
      'GET /merchants': () => Promise.resolve(new Response(JSON.stringify({ data: [{ id: 2, name, transactions: 3 }] }))),
      'PATCH /merchants/2': (_url, options) => {
        name = JSON.parse(options.body).name
        return Promise.resolve(new Response(JSON.stringify({ data: { id: 2, name, transactions: 3 } })))
      },
    })
    renderApp(<AccountMerchants />)

    await userEvent.click(await screen.findByRole('button', { name: 'Renomear Uber' }))
    const input = screen.getByLabelText('Novo nome')
    await userEvent.clear(input)
    await userEvent.type(input, 'Uber Brasil')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('Uber Brasil')).toBeInTheDocument()
    expect(requestsMade(api)).toContain('PATCH /merchants/2')
  })

  it('shows the message of the server when the new name is taken, and keeps the name typed', async () => {
    mockApi({
      'GET /merchants': MERCHANTS,
      'PATCH /merchants/2': [{ detail: 'Já existe um estabelecimento com esse nome.' }, 409],
    })
    renderApp(<AccountMerchants />)

    await userEvent.click(await screen.findByRole('button', { name: 'Renomear Uber' }))
    await userEvent.type(screen.getByLabelText('Novo nome'), ' 2')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('Já existe um estabelecimento com esse nome.')).toBeInTheDocument()
  })

  it('asks before deleting, and shows the message of the server when transactions still use it', async () => {
    const api = mockApi({
      'GET /merchants': MERCHANTS,
      'DELETE /merchants/2': [{ detail: 'Este estabelecimento é usado por 3 transações. Mude o estabelecimento delas ou apague-as antes.' }, 409],
    })
    renderApp(<AccountMerchants />)

    await userEvent.click(await screen.findByRole('button', { name: 'Apagar Uber' }))
    expect(requestsMade(api)).not.toContain('DELETE /merchants/2') // not yet: it asked first
    await userEvent.click(screen.getByRole('button', { name: 'Apagar' }))

    expect(await screen.findByText(/é usado por 3 transações/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('Uber')).toBeInTheDocument()) // still there
  })

  it('deletes one nobody uses', async () => {
    const api = mockApi({ 'GET /merchants': MERCHANTS, 'DELETE /merchants/3': { data: { message: 'ok' } } })
    renderApp(<AccountMerchants />)

    await userEvent.click(await screen.findByRole('button', { name: 'Apagar Netflix' }))
    await userEvent.click(screen.getByRole('button', { name: 'Apagar' }))

    await waitFor(() => expect(requestsMade(api)).toContain('DELETE /merchants/3'))
  })
})
