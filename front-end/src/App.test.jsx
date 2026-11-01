import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
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
    mockApi({ 'GET /user/me': { data: { name: 'Clara', email: 'c@example.com' } } })
  })

  it.each(['#/', '#/transactions', '#/report-expense', '#/investments', '#/account'])(
    'sends a logged-out visitor from %s to the login page',
    (hash) => {
      renderAt(hash)

      expect(screen.getByText('Bem-vindo de volta!')).toBeInTheDocument()
      expect(window.location.hash).toBe('#/login-google')
    },
  )

  it.each(['#/login', '#/login-google', '#/create-account'])('keeps %s public', (hash) => {
    renderAt(hash)

    expect(window.location.hash).toBe(hash)
  })

  it('shows a logged-in user the page they asked for, inside the layout', () => {
    saveToken('tok')

    renderAt('#/investments')

    expect(screen.getByText('Painel de Investimentos')).toBeInTheDocument()
    expect(screen.getByText('Money Budget')).toBeInTheDocument() // header
    expect(window.location.hash).toBe('#/investments')
  })

  it('offers the main pages in the navigation', () => {
    saveToken('tok')

    renderAt('#/investments')

    for (const name of ['Dashboard', 'Transações', 'Registrar Despesa', 'Conta']) {
      expect(screen.getByRole('link', { name })).toBeInTheDocument()
    }
  })
})
