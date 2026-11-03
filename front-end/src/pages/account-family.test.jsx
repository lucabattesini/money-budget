import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { toaster } from '../components/ui/toaster'
import { saveToken } from '../lib/auth'
import { jsonResponse, mockApi, renderApp, requestsMade } from '../test/helpers'
import AccountFamily from './account-family'

const OWNER_ALONE = {
  id: 1,
  role: 'owner',
  members: [{ id: 10, name: 'Ana', picture: null, role: 'owner' }],
}
const OWNER_WITH_BIA = {
  id: 1,
  role: 'owner',
  members: [
    { id: 10, name: 'Ana', picture: null, role: 'owner' },
    { id: 11, name: 'Bia', picture: null, role: 'member' },
  ],
}
const MEMBER_VIEW = { id: 1, role: 'member', members: OWNER_WITH_BIA.members }
const INVITE = { id: 5, code_hint: 'WXYZ', created_at: '2026-11-01T10:00:00', expires_at: '2026-11-08T10:00:00' }

beforeEach(() => {
  saveToken('tok')
  toaster.remove() // toasts live in a global store: an earlier test's toast would crowd out the one we look for
})

const members = () => within(screen.getByRole('list', { name: 'Pessoas da família' })).getAllByRole('listitem').map((li) => li.textContent)

describe('family page: people', () => {
  it('lists the people of the family with their role', async () => {
    mockApi({ 'GET /families/me': { data: OWNER_WITH_BIA }, 'GET /families/invites': { data: [] } })

    renderApp(<AccountFamily />)

    await screen.findByRole('list', { name: 'Pessoas da família' })
    expect(members()).toEqual(['AAnaDono', 'BBiaMembro'])
  })

  it('says so when the family cannot be loaded', async () => {
    mockApi({ 'GET /families/me': [{ detail: 'boom' }, 500] })

    renderApp(<AccountFamily />)

    expect(await screen.findByText(/não foi possível carregar a sua família/i)).toBeInTheDocument()
  })
})

describe('family page: inviting', () => {
  it('shows the invite area and the active codes to the owner', async () => {
    mockApi({ 'GET /families/me': { data: OWNER_ALONE }, 'GET /families/invites': { data: [INVITE] } })

    renderApp(<AccountFamily />)

    const codes = within(await screen.findByRole('list', { name: 'Códigos ativos' }))
    expect(codes.getByText('WXYZ')).toBeInTheDocument()
    expect(codes.getByText(/vence em 08\/11\/2026/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Gerar código' })).toBeInTheDocument()
  })

  it('hides the invite area from a member, and does not even ask for the codes', async () => {
    const api = mockApi({ 'GET /families/me': { data: MEMBER_VIEW } })

    renderApp(<AccountFamily />)

    await screen.findByRole('list', { name: 'Pessoas da família' })
    expect(screen.queryByRole('button', { name: 'Gerar código' })).not.toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Códigos ativos' })).not.toBeInTheDocument()
    expect(requestsMade(api)).toEqual(['GET /families/me'])
    expect(screen.getByRole('button', { name: 'Entrar na família' })).toBeInTheDocument() // joining is open to everyone
  })

  it('shows a new code once, with the warning that it will not appear again', async () => {
    const invites = [[], [{ ...INVITE, code_hint: 'ABCD' }]]
    const api = mockApi({
      'GET /families/me': { data: OWNER_ALONE },
      'GET /families/invites': () => jsonResponse({ data: invites.shift() ?? [] }),
      'POST /families/invites': () => jsonResponse({ data: { ...INVITE, code_hint: 'ABCD', code: 'AAAA-BBBB-CCCC-ABCD' } }, 201),
    })
    renderApp(<AccountFamily />)

    await userEvent.click(await screen.findByRole('button', { name: 'Gerar código' }))

    expect(await screen.findByTestId('new-code')).toHaveTextContent('AAAA-BBBB-CCCC-ABCD')
    expect(screen.getByText(/não aparece de novo/i)).toBeInTheDocument()
    expect(await screen.findByRole('list', { name: 'Códigos ativos' })).toHaveTextContent('ABCD') // the list is refreshed
    expect(api.mock.calls.find(([, o]) => o?.method === 'post')[1].headers.Authorization).toBe('Bearer tok')
  })

  it('cancels a code and refreshes the list', async () => {
    const lists = [[INVITE], []]
    const api = mockApi({
      'GET /families/me': { data: OWNER_ALONE },
      'GET /families/invites': () => jsonResponse({ data: lists.shift() ?? [] }),
      'DELETE /families/invites/5': { data: { message: 'Código cancelado' } },
    })
    renderApp(<AccountFamily />)

    await userEvent.click(await screen.findByRole('button', { name: 'Cancelar código terminado em WXYZ' }))

    await waitFor(() => expect(screen.queryByRole('list', { name: 'Códigos ativos' })).not.toBeInTheDocument())
    expect(requestsMade(api)).toContain('DELETE /families/invites/5')
  })

  it('tells the user when a code could not be created', async () => {
    mockApi({
      'GET /families/me': { data: OWNER_ALONE },
      'GET /families/invites': { data: [] },
      'POST /families/invites': [{ detail: 'Você já tem 3 códigos ativos. Cancele algum antes.' }, 409],
    })
    renderApp(<AccountFamily />)

    await userEvent.click(await screen.findByRole('button', { name: 'Gerar código' }))

    expect(await screen.findByText('Você já tem 3 códigos ativos. Cancele algum antes.')).toBeInTheDocument()
    expect(screen.queryByTestId('new-code')).not.toBeInTheDocument()
  })
})

describe('family page: joining', () => {
  const renderOwner = (extra = {}) => {
    const api = mockApi({ 'GET /families/me': { data: OWNER_ALONE }, 'GET /families/invites': { data: [] }, ...extra })
    renderApp(<AccountFamily />)
    return api
  }
  const joinButton = () => screen.getByRole('button', { name: 'Entrar na família' })
  const joinRequest = (api) => JSON.parse(api.mock.calls.find(([, o]) => o?.method === 'post')[1].body)

  it('needs both a code and an explicit choice before it can be sent', async () => {
    renderOwner()
    await screen.findByLabelText('Código de convite')
    expect(joinButton()).toBeDisabled()

    await userEvent.type(screen.getByLabelText('Código de convite'), 'AAAA-BBBB-CCCC-DDDD')
    expect(joinButton()).toBeDisabled() // no choice yet: nothing is picked for the user

    await userEvent.click(screen.getByRole('radio', { name: /Começar vazio/ }))
    expect(joinButton()).toBeEnabled()
  })

  it.each([
    ['Trazer meus dados', true],
    ['Começar vazio', false],
  ])('sends the code and the choice "%s"', async (label, bringData) => {
    const api = renderOwner({ 'POST /families/join': { data: MEMBER_VIEW } })
    await userEvent.type(await screen.findByLabelText('Código de convite'), '  aaaa-bbbb-cccc-dddd ')

    await userEvent.click(screen.getByRole('radio', { name: new RegExp(label) }))
    await userEvent.click(joinButton())

    await waitFor(() => expect(requestsMade(api)).toContain('POST /families/join'))
    expect(joinRequest(api)).toEqual({ code: 'aaaa-bbbb-cccc-dddd', bring_data: bringData })
  })

  it('shows the new family after joining and clears the form', async () => {
    const answers = [OWNER_ALONE, MEMBER_VIEW]
    mockApi({
      'GET /families/me': () => jsonResponse({ data: answers.shift() ?? MEMBER_VIEW }),
      'GET /families/invites': { data: [] },
      'POST /families/join': { data: MEMBER_VIEW },
    })
    renderApp(<AccountFamily />)
    await userEvent.type(await screen.findByLabelText('Código de convite'), 'AAAA-BBBB-CCCC-DDDD')
    await userEvent.click(screen.getByRole('radio', { name: /Trazer meus dados/ }))

    await userEvent.click(joinButton())

    expect(await screen.findByText('Você entrou na família.')).toBeInTheDocument()
    await waitFor(() => expect(members()).toEqual(['AAnaDono', 'BBiaMembro']))
    expect(screen.getByLabelText('Código de convite')).toHaveValue('')
    expect(screen.queryByRole('button', { name: 'Gerar código' })).not.toBeInTheDocument() // now a member
  })

  it.each([
    [404, 'Código inválido, expirado ou já usado.'],
    [409, 'Você já faz parte de uma família com outras pessoas. Saia dela ou passe a posse antes de entrar em outra.'],
  ])('shows the server message when joining is refused (%s) and keeps what was typed', async (status, detail) => {
    renderOwner({ 'POST /families/join': [{ detail }, status] })
    await userEvent.type(await screen.findByLabelText('Código de convite'), 'AAAA-BBBB-CCCC-DDDD')
    await userEvent.click(screen.getByRole('radio', { name: /Começar vazio/ }))

    await userEvent.click(joinButton())

    expect(await screen.findByText(detail)).toBeInTheDocument()
    expect(screen.getByLabelText('Código de convite')).toHaveValue('AAAA-BBBB-CCCC-DDDD')
    expect(members()).toEqual(['AAnaDono']) // still in the old family
  })
})
