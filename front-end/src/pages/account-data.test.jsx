import { screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { saveToken } from '../lib/auth'
import { mockApi, renderApp, requestsMade } from '../test/helpers'
import AccountData from './account-data'

const CATEGORIES = { data: [{ id: 2, name: 'Transporte' }, { id: 3, name: 'Água' }, { id: 1, name: 'Alimentação' }] }

describe('import and export page', () => {
  it('tells the user which columns the import file needs, and which are required', async () => {
    saveToken('tok')
    mockApi({ 'GET /categories': CATEGORIES })

    renderApp(<AccountData />)

    const table = within(screen.getByRole('table', { name: 'Colunas da planilha de importação' }))
    const rows = table.getAllByRole('row').slice(1).map((row) => [...row.children].map((cell) => cell.textContent))
    expect(rows.map((row) => row.slice(0, 2))).toEqual([
      ['Data', 'Sim'],
      ['Descrição', 'Sim'],
      ['Categoria', 'Sim'],
      ['Valor', 'Sim'],
      ['Tipo', 'Não'],
    ])
    expect(rows[0][3]).toBe('15/03/2026') // an example for each column
    expect(rows[3][3]).toBe('1.234,56')
    expect(await screen.findByText('Água')).toBeInTheDocument() // wait for the page to settle
  })

  it('explains the file type and the header row', async () => {
    saveToken('tok')
    mockApi({ 'GET /categories': CATEGORIES })

    renderApp(<AccountData />)

    expect(screen.getByText(/primeira linha tem os nomes das colunas/i)).toBeInTheDocument()
    expect(screen.getByText('.xlsx')).toBeInTheDocument()
    expect(screen.getByText('.csv')).toBeInTheDocument()
    await screen.findByText('Água')
  })

  it('lists the real categories, alphabetically, as the accepted ones', async () => {
    saveToken('tok')
    const api = mockApi({ 'GET /categories': CATEGORIES })

    renderApp(<AccountData />)

    const list = within(await screen.findByLabelText('Categorias aceitas'))
    expect(list.getAllByText(/./).map((tag) => tag.textContent)).toEqual(['Água', 'Alimentação', 'Transporte'])
    expect(api.mock.calls[0][1].headers.Authorization).toBe('Bearer tok')
  })

  it('still shows the format when the categories cannot be loaded', async () => {
    saveToken('tok')
    const api = mockApi({ 'GET /categories': [{ detail: 'boom' }, 500] })

    renderApp(<AccountData />)

    expect(screen.getByRole('table', { name: 'Colunas da planilha de importação' })).toBeInTheDocument()
    await Promise.resolve()
    expect(requestsMade(api)).toEqual(['GET /categories'])
    expect(screen.queryByLabelText('Categorias aceitas')).not.toBeInTheDocument()
  })

  it('does not ask for categories without a login', () => {
    const api = mockApi({})

    renderApp(<AccountData />)

    expect(requestsMade(api)).toEqual([])
    expect(screen.getByRole('table', { name: 'Colunas da planilha de importação' })).toBeInTheDocument()
  })
})
