import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { renderApp } from '../test/helpers'
import AccountLayout from './account-layout'
import AccountData from './account-data'

function renderAccount(route = '/account') {
  return renderApp(
    <Routes>
      <Route path="/account" element={<AccountLayout />}>
        <Route index element={<div>conteúdo do perfil</div>} />
        <Route path="data" element={<AccountData />} />
      </Route>
    </Routes>,
    { route },
  )
}

const menu = () => within(screen.getByRole('navigation', { name: 'Menu da conta' }))
const currentEntry = () =>
  menu().getAllByRole('link').filter((link) => link.getAttribute('aria-current') === 'page').map((l) => l.textContent)

describe('account area', () => {
  it('has a menu with Perfil, Família, Categorias, Preferências and Importar e exportar', () => {
    renderAccount()

    expect(menu().getAllByRole('link').map((link) => link.textContent)).toEqual([
      'Perfil',
      'Família',
      'Categorias',
      'Preferências',
      'Importar e exportar',
    ])
  })

  it('opens on the profile, which is the highlighted entry', () => {
    renderAccount()

    expect(screen.getByText('conteúdo do perfil')).toBeInTheDocument()
    expect(currentEntry()).toEqual(['Perfil'])
  })

  it('switches section from the menu and highlights where the user is', async () => {
    renderAccount()

    await userEvent.click(menu().getByRole('link', { name: 'Importar e exportar' }))
    expect(screen.getByRole('heading', { name: 'Importar' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Exportar' })).toBeInTheDocument() // both on the same page
    expect(screen.queryByText('conteúdo do perfil')).not.toBeInTheDocument()
    expect(currentEntry()).toEqual(['Importar e exportar'])

    await userEvent.click(menu().getByRole('link', { name: 'Perfil' }))
    expect(screen.getByText('conteúdo do perfil')).toBeInTheDocument()
    expect(currentEntry()).toEqual(['Perfil'])
  })

  it('opens a section straight from its address and keeps the menu', () => {
    renderAccount('/account/data')

    expect(screen.getByRole('heading', { name: 'Importar e exportar' })).toBeInTheDocument()
    expect(currentEntry()).toEqual(['Importar e exportar']) // Perfil is not highlighted just because the path starts with /account
  })
})
