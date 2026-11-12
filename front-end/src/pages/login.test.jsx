import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderApp } from '../test/helpers'
import Login from './login'

describe('old login page', () => {
  it('links to the create-account page of the app, not to a plain address that does not exist', async () => {
    renderApp(<Login />, { route: '/login' })

    const link = screen.getByRole('link', { name: /Crie uma agora/ })
    expect(link.getAttribute('href')).toBe('/create-account') // the router writes the "#" in front on the real app (HashRouter)

    await userEvent.click(link)

    expect(screen.getByTestId('location')).toHaveTextContent('/create-account')
  })
})
