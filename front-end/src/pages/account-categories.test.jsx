import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { toaster } from '../components/ui/toaster'
import { saveToken } from '../lib/auth'
import { jsonResponse, mockApi, renderApp, requestsMade } from '../test/helpers'
import AccountCategories from './account-categories'

const GROUPS = {
  data: [
    { id: 1, name: 'Casa' },
    { id: 2, name: 'Lazer' },
    { id: 3, name: 'Investimentos' }, // nothing in it: it must not be shown
    { id: 4, name: 'Outros' },
  ],
}
const category = (id, name, group_id, family_id = null) => ({
  id,
  name,
  group_id,
  group_name: GROUPS.data.find((g) => g.id === group_id).name,
  family_id,
  is_default: family_id === null,
})
const LIST = {
  data: [
    category(10, 'Viagem', 2),
    category(11, 'Aluguel', 1),
    category(12, 'Água da casa', 1, 7), // the family's own
    category(13, 'Outros', 4),
    category(14, 'Cinema do bairro', 2, 7), // the family's own
  ],
}

beforeEach(() => {
  saveToken('tok')
  toaster.remove() // toasts live in a global store: an earlier test's toast would crowd out the one we look for
})

const names = (groupName) =>
  within(screen.getByRole('list', { name: `Categorias de ${groupName}` }))
    .getAllByRole('listitem')
    .map((li) => li.textContent)

async function renderPage(extra = {}) {
  const api = mockApi({ 'GET /categories': LIST, 'GET /categories/groups': GROUPS, ...extra })
  renderApp(<AccountCategories />)
  await screen.findByRole('heading', { name: 'Casa' })
  return api
}

const bodyOf = (api, method) => {
  const call = api.mock.calls.find(([, o]) => (o?.method || 'GET').toUpperCase() === method)
  return call && JSON.parse(call[1].body)
}

describe('categories page: the list', () => {
  it('shows the categories under their groups, A-Z inside each, and hides the empty groups', async () => {
    await renderPage()

    expect(names('Casa')).toEqual(['Água da casa', 'AluguelPadrão'])
    expect(names('Lazer')).toEqual(['Cinema do bairro', 'ViagemPadrão'])
    expect(screen.queryByRole('heading', { name: 'Investimentos' })).not.toBeInTheDocument()
  })

  it('marks the default categories and lets the family change only its own', async () => {
    await renderPage()

    expect(screen.getAllByText('Padrão')).toHaveLength(3)
    expect(screen.getByRole('button', { name: 'Editar Água da casa' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Apagar Água da casa' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Editar Aluguel' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Apagar Aluguel' })).not.toBeInTheDocument()
  })

  it('says so when the categories cannot be loaded', async () => {
    mockApi({ 'GET /categories': [{ detail: 'boom' }, 500], 'GET /categories/groups': GROUPS })

    renderApp(<AccountCategories />)

    expect(await screen.findByText(/não foi possível carregar as categorias/i)).toBeInTheDocument()
  })
})

describe('categories page: adding', () => {
  const open = async () => userEvent.click(await screen.findByRole('button', { name: /nova categoria/i }))

  it('starts in the group Outros and sends the name and the chosen group', async () => {
    const lists = [LIST, { data: [...LIST.data, category(20, 'Jogos', 2, 7)] }]
    const api = await renderPage({
      'GET /categories': () => jsonResponse(lists.shift() ?? LIST),
      'POST /categories': [{ data: category(20, 'Jogos', 2, 7) }, 201],
    })
    await open()
    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByLabelText(/grupo/i)).toHaveValue('4') // Outros

    await userEvent.type(dialog.getByLabelText(/nome/i), '  Jogos ')
    await userEvent.selectOptions(dialog.getByLabelText(/grupo/i), 'Lazer')
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(requestsMade(api)).toContain('POST /categories'))
    expect(bodyOf(api, 'POST')).toEqual({ name: 'Jogos', group_id: 2 })
    expect(await screen.findByText('A categoria foi criada!')).toBeInTheDocument()
    await waitFor(() => expect(names('Lazer')).toContain('Jogos'))
  })

  it('does not send an empty name and says why', async () => {
    const api = await renderPage()
    await open()
    const dialog = within(await screen.findByRole('dialog'))

    await userEvent.type(dialog.getByLabelText(/nome/i), '   ')
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    expect(await dialog.findByText('O nome da categoria não pode ficar vazio.')).toBeInTheDocument()
    expect(requestsMade(api)).not.toContain('POST /categories')
  })

  it('shows the message of the server when the name already exists and keeps the panel open', async () => {
    await renderPage({ 'POST /categories': [{ detail: 'Já existe uma categoria com esse nome.' }, 409] })
    await open()
    const dialog = within(await screen.findByRole('dialog'))

    await userEvent.type(dialog.getByLabelText(/nome/i), 'aluguel')
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    expect(await dialog.findByText('Já existe uma categoria com esse nome.')).toBeInTheDocument()
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })
})

describe('categories page: editing', () => {
  it('opens with the current name and group and sends the changes', async () => {
    const api = await renderPage({
      'PATCH /categories/12': { data: category(12, 'Jardim', 2, 7) },
    })
    await userEvent.click(screen.getByRole('button', { name: 'Editar Água da casa' }))
    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByLabelText(/nome/i)).toHaveValue('Água da casa')
    expect(dialog.getByLabelText(/grupo/i)).toHaveValue('1')

    await userEvent.clear(dialog.getByLabelText(/nome/i))
    await userEvent.type(dialog.getByLabelText(/nome/i), 'Jardim')
    await userEvent.selectOptions(dialog.getByLabelText(/grupo/i), 'Lazer')
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(requestsMade(api)).toContain('PATCH /categories/12'))
    expect(bodyOf(api, 'PATCH')).toEqual({ name: 'Jardim', group_id: 2 })
    expect(await screen.findByText('A categoria foi atualizada!')).toBeInTheDocument()
  })

  it('shows the message of the server when the new name is taken', async () => {
    await renderPage({ 'PATCH /categories/12': [{ detail: 'Já existe uma categoria com esse nome.' }, 409] })
    await userEvent.click(screen.getByRole('button', { name: 'Editar Água da casa' }))
    const dialog = within(await screen.findByRole('dialog'))

    await userEvent.clear(dialog.getByLabelText(/nome/i))
    await userEvent.type(dialog.getByLabelText(/nome/i), 'Aluguel')
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    expect(await dialog.findByText('Já existe uma categoria com esse nome.')).toBeInTheDocument()
  })
})

describe('categories page: deleting', () => {
  it('asks to confirm, then deletes and refreshes the list', async () => {
    const lists = [LIST, { data: LIST.data.filter((c) => c.id !== 12) }]
    const api = await renderPage({
      'GET /categories': () => jsonResponse(lists.shift() ?? LIST),
      'DELETE /categories/12': { data: { message: 'Categoria apagada' } },
    })

    await userEvent.click(screen.getByRole('button', { name: 'Apagar Água da casa' }))
    expect(requestsMade(api)).not.toContain('DELETE /categories/12') // not yet: it asked first
    await userEvent.click(screen.getByRole('button', { name: 'Apagar' }))

    await waitFor(() => expect(names('Casa')).toEqual(['AluguelPadrão']))
    expect(requestsMade(api)).toContain('DELETE /categories/12')
  })

  it('does nothing when the user changes their mind', async () => {
    const api = await renderPage()

    await userEvent.click(screen.getByRole('button', { name: 'Apagar Água da casa' }))
    await userEvent.click(screen.getByRole('button', { name: 'Não apagar' }))

    expect(requestsMade(api).filter((r) => r.startsWith('DELETE'))).toEqual([])
    expect(screen.getByRole('button', { name: 'Apagar Água da casa' })).toBeInTheDocument()
  })

  it('keeps a category that is in use and tells how many transactions use it', async () => {
    const message = 'Esta categoria é usada por 3 transações. Mude a categoria delas ou apague-as antes.'
    await renderPage({ 'DELETE /categories/12': [{ detail: message }, 409] })

    await userEvent.click(screen.getByRole('button', { name: 'Apagar Água da casa' }))
    await userEvent.click(screen.getByRole('button', { name: 'Apagar' }))

    expect(await screen.findByText(message)).toBeInTheDocument()
    expect(names('Casa')).toContain('Água da casa') // still there
  })
})
