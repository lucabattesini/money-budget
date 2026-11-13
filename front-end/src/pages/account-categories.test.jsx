import { fireEvent, screen, waitFor, within } from '@testing-library/react'
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
    { id: 3, name: 'Investimentos' }, // nothing in it yet
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
  it('shows the categories under their groups, A-Z inside each', async () => {
    await renderPage()

    expect(names('Casa')).toEqual(['Água da casa', 'AluguelPadrão'])
    expect(names('Lazer')).toEqual(['Cinema do bairro', 'ViagemPadrão'])
  })

  it('shows every group, with an add button in each, and says when a group has no category yet', async () => {
    await renderPage()

    expect(screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent).slice(1)).toEqual([
      'Casa',
      'Lazer',
      'Investimentos',
      'Outros',
    ])
    for (const group of ['Casa', 'Lazer', 'Investimentos', 'Outros']) {
      expect(screen.getByRole('button', { name: `Adicionar em ${group}` })).toBeInTheDocument()
    }
    const empty = within(screen.getByRole('region', { name: 'Investimentos' }))
    expect(empty.getByText('Nenhuma categoria neste grupo ainda.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /^nova categoria/i })).not.toBeInTheDocument() // none at the top
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
  const open = async (group = 'Outros') =>
    userEvent.click(await screen.findByRole('button', { name: `Adicionar em ${group}` }))

  it('starts in the group of the button that was clicked and sends it with the name', async () => {
    const lists = [LIST, { data: [...LIST.data, category(20, 'Jogos', 2, 7)] }]
    const api = await renderPage({
      'GET /categories': () => jsonResponse(lists.shift() ?? LIST),
      'POST /categories': [{ data: category(20, 'Jogos', 2, 7) }, 201],
    })
    await open('Lazer')
    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByLabelText(/grupo/i)).toHaveValue('2') // Lazer, where the button was

    await userEvent.type(dialog.getByLabelText(/nome/i), '  Jogos ')
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(requestsMade(api)).toContain('POST /categories'))
    expect(bodyOf(api, 'POST')).toEqual({ name: 'Jogos', group_id: '2' })
    expect(await screen.findByText('A categoria foi criada!')).toBeInTheDocument()
    await waitFor(() => expect(names('Lazer')).toContain('Jogos'))
  })

  it('can add to a group that has no category yet', async () => {
    const api = await renderPage({ 'POST /categories': [{ data: category(21, 'Renda fixa', 3, 7) }, 201] })
    await open('Investimentos')
    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByLabelText(/grupo/i)).toHaveValue('3')

    await userEvent.type(dialog.getByLabelText(/nome/i), 'Renda fixa')
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(bodyOf(api, 'POST')).toEqual({ name: 'Renda fixa', group_id: '3' }))
  })

  it('still lets the person pick another group in the panel', async () => {
    const api = await renderPage({ 'POST /categories': [{ data: category(20, 'Jogos', 2, 7) }, 201] })
    await open('Casa')
    const dialog = within(await screen.findByRole('dialog'))

    await userEvent.type(dialog.getByLabelText(/nome/i), 'Jogos')
    await userEvent.selectOptions(dialog.getByLabelText(/grupo/i), 'Lazer')
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(bodyOf(api, 'POST')).toEqual({ name: 'Jogos', group_id: '2' }))
  })

  it('starts empty and in the new group every time the panel is opened again', async () => {
    await renderPage()
    await open('Casa')
    await userEvent.type(within(await screen.findByRole('dialog')).getByLabelText(/nome/i), 'rascunho')
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())

    await open('Lazer')

    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByLabelText(/nome/i)).toHaveValue('')
    expect(dialog.getByLabelText(/grupo/i)).toHaveValue('2')
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

describe('categories page: emoji', () => {
  const emoji = (dialog, label) => dialog.getByRole('radio', { name: label })
  const open = async (group = 'Outros') =>
    userEvent.click(await screen.findByRole('button', { name: `Adicionar em ${group}` }))

  it('asks for the name first, then the group, then the emoji', async () => {
    await renderPage()
    await open()
    const dialog = (await screen.findByRole('dialog')).closest('[role="dialog"]')

    const fields = [...dialog.querySelectorAll('label')]
      .map((element) => element.textContent.replace(/\s*\*$/, '').trim())
      .filter((text) => ['Nome', 'Grupo', 'Emoji'].includes(text))

    expect(fields).toEqual(['Nome', 'Grupo', 'Emoji'])
  })

  it('puts the chosen emoji in front of the name', async () => {
    const api = await renderPage({ 'POST /categories': [{ data: category(20, '🌱 Plantas', 4, 7) }, 201] })
    await open()
    const dialog = within(await screen.findByRole('dialog'))

    await userEvent.type(dialog.getByLabelText(/nome/i), 'Plantas')
    await userEvent.click(emoji(dialog, '🌱'))
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(requestsMade(api)).toContain('POST /categories'))
    expect(bodyOf(api, 'POST')).toEqual({ name: '🌱 Plantas', group_id: '4' })
  })

  it('has an emoji only when one is chosen, and none selected at first', async () => {
    await renderPage()
    await open()
    const dialog = within(await screen.findByRole('dialog'))

    expect(dialog.getByRole('radio', { name: 'Sem emoji' })).toBeChecked()
    expect(emoji(dialog, '🌱')).not.toBeChecked()
  })

  it('takes an emoji typed into the name box as well, without doubling it', async () => {
    const api = await renderPage({ 'POST /categories': [{ data: category(20, '🪴 Vasos', 4, 7) }, 201] })
    await open()
    const dialog = within(await screen.findByRole('dialog'))

    await userEvent.type(dialog.getByLabelText(/nome/i), '🪴 Vasos')
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(requestsMade(api)).toContain('POST /categories'))
    expect(bodyOf(api, 'POST').name).toBe('🪴 Vasos')
  })

  it('refuses a name that is only an emoji', async () => {
    const api = await renderPage()
    await open()
    const dialog = within(await screen.findByRole('dialog'))

    await userEvent.click(emoji(dialog, '🌱'))
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    expect(await dialog.findByText('O nome da categoria não pode ficar vazio.')).toBeInTheDocument()
    expect(requestsMade(api)).not.toContain('POST /categories')
  })

  it('splits the name of a category being edited into its emoji and its words', async () => {
    const api = await renderPage({
      'GET /categories': { data: [category(12, '🌱 Plantas', 1, 7)] },
      'PATCH /categories/12': { data: category(12, 'Plantas da casa', 1, 7) },
    })
    await userEvent.click(screen.getByRole('button', { name: 'Editar 🌱 Plantas' }))
    const dialog = within(await screen.findByRole('dialog'))
    expect(dialog.getByLabelText(/nome/i)).toHaveValue('Plantas')
    expect(emoji(dialog, '🌱')).toBeChecked()

    await userEvent.type(dialog.getByLabelText(/nome/i), ' da casa')
    await userEvent.click(dialog.getByRole('radio', { name: 'Sem emoji' }))
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    await waitFor(() => expect(requestsMade(api)).toContain('PATCH /categories/12'))
    expect(bodyOf(api, 'PATCH').name).toBe('Plantas da casa') // the emoji was taken off
  })

  it('keeps an emoji of the category that is not in the list selectable', async () => {
    await renderPage({ 'GET /categories': { data: [category(12, '🦄 Mágicas', 1, 7)] } })

    await userEvent.click(screen.getByRole('button', { name: 'Editar 🦄 Mágicas' }))
    const dialog = within(await screen.findByRole('dialog'))

    expect(emoji(dialog, '🦄')).toBeChecked()
  })

  it('lists the categories by their words, not by the emoji in front', async () => {
    await renderPage({
      'GET /categories': {
        data: [category(10, '🏠 Zebra', 1, 7), category(11, '🔧 Abacate', 1, 7), category(12, 'Mala', 1, 7)],
      },
    })

    expect(names('Casa')).toEqual(['🔧 Abacate', 'Mala', '🏠 Zebra'])
  })
})

describe('categories page: the emoji grid with the keyboard', () => {
  const open = async (group = 'Outros') =>
    userEvent.click(await screen.findByRole('button', { name: `Adicionar em ${group}` }))
  const radios = (dialog) => dialog.getAllByRole('radio')

  it('has a single tab stop: the selected option', async () => {
    await renderPage()
    await open()
    const dialog = within(await screen.findByRole('dialog'))

    const stops = radios(dialog).filter((radio) => radio.tabIndex === 0)

    expect(stops.map((radio) => radio.textContent)).toEqual(['Sem emoji'])
  })

  it('moves and selects with the arrow keys, and wraps around', async () => {
    await renderPage()
    await open()
    const dialog = within(await screen.findByRole('dialog'))
    const first = dialog.getByRole('radio', { name: 'Sem emoji' })
    first.focus()

    await userEvent.keyboard('{ArrowRight}')
    const second = radios(dialog)[1]
    expect(second).toBeChecked()
    expect(second).toHaveFocus()
    expect(second.tabIndex).toBe(0) // the tab stop follows the selection
    expect(first.tabIndex).toBe(-1)

    await userEvent.keyboard('{ArrowLeft}{ArrowLeft}')
    expect(radios(dialog).at(-1)).toBeChecked() // before the first comes the last

    await userEvent.keyboard('{Home}')
    expect(first).toBeChecked()
    await userEvent.keyboard('{End}')
    expect(radios(dialog).at(-1)).toBeChecked()
  })
})

describe('categories page: the length of a name', () => {
  const open = async (group = 'Outros') =>
    userEvent.click(await screen.findByRole('button', { name: `Adicionar em ${group}` }))

  it('cuts the words at 100 characters when there is no emoji', async () => {
    await renderPage()
    await open()
    const dialog = within(await screen.findByRole('dialog'))

    fireEvent.change(dialog.getByLabelText(/nome/i), { target: { value: 'a'.repeat(120) } })

    expect(dialog.getByLabelText(/nome/i)).toHaveValue('a'.repeat(100))
  })

  it('leaves room for the emoji and the space in front, counted by characters like the server', async () => {
    await renderPage()
    await open()
    const dialog = within(await screen.findByRole('dialog'))

    await userEvent.click(dialog.getByRole('radio', { name: '🏋️' })) // two characters (a symbol and a selector)
    fireEvent.change(dialog.getByLabelText(/nome/i), { target: { value: 'a'.repeat(120) } })

    expect(dialog.getByLabelText(/nome/i)).toHaveValue('a'.repeat(97)) // 100 - 2 - the space
  })

  it('does not send a name that became too long when the emoji was chosen after typing', async () => {
    const api = await renderPage()
    await open()
    const dialog = within(await screen.findByRole('dialog'))
    fireEvent.change(dialog.getByLabelText(/nome/i), { target: { value: 'a'.repeat(100) } })

    await userEvent.click(dialog.getByRole('radio', { name: '🌱' }))
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    expect(await dialog.findByText(/com o emoji, pode ter no máximo 100 caracteres/)).toBeInTheDocument()
    expect(requestsMade(api)).not.toContain('POST /categories')
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
    expect(bodyOf(api, 'PATCH')).toEqual({ name: 'Jardim', group_id: '2' })
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

describe('categories page: when the category changed meanwhile', () => {
  it('says so, closes the panel and shows the real list when saving finds the category gone', async () => {
    const lists = [LIST, { data: LIST.data.filter((c) => c.id !== 12) }]
    const api = await renderPage({
      'GET /categories': () => jsonResponse(lists.shift() ?? LIST),
      'PATCH /categories/12': [{ detail: 'Categoria não encontrada.' }, 404],
    })
    await userEvent.click(screen.getByRole('button', { name: 'Editar Água da casa' }))
    const dialog = within(await screen.findByRole('dialog'))

    await userEvent.type(dialog.getByLabelText(/nome/i), ' 2')
    await userEvent.click(dialog.getByRole('button', { name: 'Salvar' }))

    expect(await screen.findByText('Categoria não encontrada.')).toBeInTheDocument()
    await waitFor(() => expect(names('Casa')).toEqual(['AluguelPadrão'])) // the list was reloaded
    expect(requestsMade(api).filter((r) => r === 'GET /categories')).toHaveLength(2)
  })

  it('sends only one delete request when the confirm button is clicked twice quickly', async () => {
    let finish
    const api = await renderPage({
      'DELETE /categories/12': () => new Promise((resolve) => (finish = () => resolve(new Response('{"data":{}}')))),
    })
    await userEvent.click(screen.getByRole('button', { name: 'Apagar Água da casa' }))
    const confirm = screen.getByRole('button', { name: 'Apagar' })

    await userEvent.dblClick(confirm)
    finish()

    await waitFor(() => expect(requestsMade(api)).toContain('DELETE /categories/12'))
    expect(requestsMade(api).filter((r) => r.startsWith('DELETE'))).toHaveLength(1)
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
