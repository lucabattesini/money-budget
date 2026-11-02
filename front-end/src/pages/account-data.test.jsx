import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { mockApi, renderApp, requestsMade } from '../test/helpers'
import AccountData from './account-data'
import customToaster from '../utils/customToaster'

vi.mock('../utils/customToaster', () => ({ default: vi.fn() }))

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

describe('exporting', () => {
  let downloads
  beforeEach(() => {
    vi.mocked(customToaster).mockClear()
    saveToken('tok')
    downloads = []
    URL.createObjectURL = vi.fn(() => 'blob:fake')
    URL.revokeObjectURL = vi.fn()
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function () {
      downloads.push(this.download)
    })
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 2, 15, 12, 0, 0))
  })
  afterEach(() => vi.restoreAllMocks())

  const fileResponse = () => Promise.resolve(new Response('Data;Valor\r\n', { status: 200 }))

  it('downloads an Excel file by default, asking the server for xlsx with the user token', async () => {
    const api = mockApi({ 'GET /categories': CATEGORIES, 'GET /transactions/export?format=xlsx': fileResponse })
    renderApp(<AccountData />)
    expect(screen.getByRole('radio', { name: 'Excel (.xlsx)' })).toBeChecked()

    await userEvent.click(screen.getByRole('button', { name: /baixar/i }))

    await waitFor(() => expect(downloads).toEqual(['transacoes-2026-03-15.xlsx']))
    const call = api.mock.calls.find(([url]) => url.includes('/export'))
    expect(call[1].headers.Authorization).toBe('Bearer tok')
    expect(customToaster).toHaveBeenCalledWith('Pronto', 'success', expect.any(String))
  })

  it('downloads a CSV when that format is chosen', async () => {
    const api = mockApi({ 'GET /categories': CATEGORIES, 'GET /transactions/export?format=csv': fileResponse })
    renderApp(<AccountData />)

    await userEvent.click(screen.getByRole('radio', { name: 'CSV (.csv)' }))
    await userEvent.click(screen.getByRole('button', { name: /baixar/i }))

    await waitFor(() => expect(downloads).toEqual(['transacoes-2026-03-15.csv']))
    expect(requestsMade(api)).toContain('GET /transactions/export?format=csv')
  })

  it('tells the user and downloads nothing when the server refuses', async () => {
    mockApi({ 'GET /categories': CATEGORIES, 'GET /transactions/export?format=xlsx': [{ detail: 'boom' }, 500] })
    renderApp(<AccountData />)

    await userEvent.click(screen.getByRole('button', { name: /baixar/i }))

    await waitFor(() => expect(customToaster).toHaveBeenCalledWith('Erro', 'error', expect.any(String)))
    expect(downloads).toEqual([])
  })

  it('tells the user and downloads nothing when the server cannot be reached', async () => {
    mockApi({
      'GET /categories': CATEGORIES,
      'GET /transactions/export?format=xlsx': () => Promise.reject(new TypeError('Failed to fetch')),
    })
    vi.spyOn(console, 'error').mockImplementation(() => {})
    renderApp(<AccountData />)

    await userEvent.click(screen.getByRole('button', { name: /baixar/i }))

    await waitFor(() => expect(customToaster).toHaveBeenCalledWith('Erro', 'error', expect.any(String)))
    expect(downloads).toEqual([])
  })
})
