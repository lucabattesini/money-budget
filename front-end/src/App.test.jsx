import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { Provider } from './components/ui/provider'
import { saveToken } from './lib/auth'
import { mockApi } from './test/helpers'

vi.mock('@react-oauth/google', () => ({
  GoogleOAuthProvider: ({ children }) => children,
  GoogleLogin: () => <button>Sign in with Google</button>,
}))

function renderAt(hash) {
  window.location.hash = hash
  return render(
    <Provider>
      <App />
    </Provider>,
  )
}

describe('routing', () => {
  beforeEach(() => {
    mockApi({
      'GET /user/me': { data: { name: 'Clara', email: 'c@example.com' } },
      'GET /categories': { data: [] }, // asked by the import page
      'GET /families/me': { data: { currency: 'BRL', language: 'pt', role: 'owner', members: [] } }, // asked by the layout
    })
  })

  afterEach(() => {
    window.location.hash = '' // the router reads the real URL, so do not leak it into the next test
  })

  it.each(['#/', '#/transactions', '#/budgets', '#/report-expense', '#/investments', '#/account'])(
    'sends a logged-out visitor from %s to the login page',
    async (hash) => {
      renderAt(hash)

      // the Google login page, not the legacy /login page that has the same heading
      expect(await screen.findByRole('button', { name: 'Sign in with Google' })).toBeInTheDocument() // pages are loaded when first opened
      expect(window.location.hash).toBe('#/login-google')
    },
  )

  it.each([
    ['#/login', () => screen.findByPlaceholderText(/e-?mail/i)],
    ['#/login-google', () => screen.findByRole('button', { name: 'Sign in with Google' })],
    ['#/create-account', () => screen.findByText('Criar conta')],
  ])('keeps %s public and shows its own page', async (hash, pageMarker) => {
    renderAt(hash)

    expect(await pageMarker()).toBeInTheDocument()
    expect(window.location.hash).toBe(hash)
  })

  it.each([
    ['#/account', 'Minha Conta'],
    ['#/account/data', 'Importar e exportar'],
  ])('shows %s inside the app layout and the account menu', async (hash, marker) => {
    saveToken('tok')
    renderAt(hash)

    expect((await screen.findAllByText(marker)).length).toBeGreaterThan(0) // the page title (the menu entry has the same name)
    expect(screen.getByRole('navigation', { name: 'Menu da conta' })).toBeInTheDocument()
    expect(screen.getByText('Money Budget')).toBeInTheDocument() // header
  })

  it('shows a logged-in user the page they asked for, inside the layout', async () => {
    saveToken('tok')

    renderAt('#/investments')

    expect(await screen.findByText('Painel de Investimentos')).toBeInTheDocument()
    expect(screen.getByText('Money Budget')).toBeInTheDocument() // header
    expect(window.location.hash).toBe('#/investments')
  })

  it('offers the main pages in the navigation', () => {
    saveToken('tok')

    renderAt('#/investments')

    for (const name of ['Dashboard', 'Transações', 'Conta']) {
      expect(screen.getByRole('link', { name })).toBeInTheDocument()
    }
    expect(screen.queryByRole('link', { name: 'Registrar Despesa' })).not.toBeInTheDocument() // hidden, the page itself still exists
  })
})
