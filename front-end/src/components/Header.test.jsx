import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderApp } from '../test/helpers'
import Header from './Header'

describe('header', () => {
  it('has a Money Budget logo that links to the home page', () => {
    renderApp(<Header />, { route: '/transactions' })

    const logo = screen.getByRole('link', { name: /money budget/i })
    expect(logo).toHaveAttribute('href', '/')
  })

  it('goes home when the logo is clicked', async () => {
    renderApp(<Header />, { route: '/transactions' })
    expect(screen.getByTestId('location')).toHaveTextContent('/transactions')

    await userEvent.click(screen.getByRole('link', { name: /money budget/i }))

    expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/)
  })

  it.each([
    ['/', 'Dashboard'],
    ['/transactions', 'Transações'],
    ['/budgets', 'Orçamentos'],
    ['/account', 'Conta'],
    ['/account/data', 'Conta'], // a sub-page keeps its section highlighted
  ])('highlights the current section on %s: %s', (route, name) => {
    renderApp(<Header />, { route })

    const current = screen.getAllByRole('link').filter((link) => link.getAttribute('aria-current') === 'page')
    expect(current.map((link) => link.textContent)).toEqual([name])
  })

  it('has a main menu with every section, which a phone shows as a bar at the bottom', () => {
    renderApp(<Header />, { route: '/' })

    const menu = screen.getByRole('navigation', { name: 'Menu principal' })
    const links = within(menu).getAllByRole('link').map((link) => link.getAttribute('href'))
    expect(links).toEqual(['/', '/transactions', '/budgets', '/account'])
  })
})
