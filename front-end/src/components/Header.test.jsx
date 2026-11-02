import { screen } from '@testing-library/react'
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
})
