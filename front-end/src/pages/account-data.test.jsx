import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { mockApi, renderApp, requestsMade } from '../test/helpers'
import AccountData from './account-data'
import { enqueueExport, followExport } from '../lib/exportJobs'

vi.mock('../lib/exportJobs', () => ({ enqueueExport: vi.fn(), followExport: vi.fn() }))

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

  it('lists the real categories, alphabetically, as the ones the family already has', async () => {
    saveToken('tok')
    const api = mockApi({ 'GET /categories': CATEGORIES })

    renderApp(<AccountData />)

    const list = within(await screen.findByLabelText('Categorias que você já tem'))
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
    expect(screen.queryByLabelText('Categorias que você já tem')).not.toBeInTheDocument()
  })

  it('does not ask for categories without a login', () => {
    const api = mockApi({})

    renderApp(<AccountData />)

    expect(requestsMade(api)).toEqual([])
    expect(screen.getByRole('table', { name: 'Colunas da planilha de importação' })).toBeInTheDocument()
  })
})

describe('importing', () => {
  beforeEach(() => saveToken('tok'))

  it('opens the import dialog from a button and closes it again', async () => {
    mockApi({ 'GET /categories': CATEGORIES })
    renderApp(<AccountData />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /importar planilha/i }))

    const dialog = await screen.findByRole('dialog', { name: 'Importar transações' })
    expect(within(dialog).getByRole('listitem', { current: 'step' })).toHaveTextContent('Arquivo')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('no longer says the import is coming soon, and explains that rows are checked together and duplicates skipped', async () => {
    mockApi({ 'GET /categories': CATEGORIES })
    renderApp(<AccountData />)

    expect(screen.queryByText(/em breve/i)).not.toBeInTheDocument()
    expect(screen.getByText(/nada é importado/i)).toBeInTheDocument()
    expect(screen.getByText(/não duplica nada/i)).toBeInTheDocument()
    await screen.findByText('Água')
  })
})

describe('exporting', () => {
  beforeEach(() => {
    vi.mocked(enqueueExport).mockReset()
    vi.mocked(followExport).mockReset()
    saveToken('tok')
  })

  const render = () => {
    mockApi({ 'GET /categories': CATEGORIES })
    return renderApp(<AccountData />)
  }

  it('queues an Excel export by default and then follows the job', async () => {
    const job = { id: 7, status: 'queued' }
    vi.mocked(enqueueExport).mockResolvedValue(job)
    render()
    expect(screen.getByRole('radio', { name: 'Excel (.xlsx)' })).toBeChecked()

    await userEvent.click(screen.getByRole('button', { name: /baixar/i }))

    await waitFor(() => expect(followExport).toHaveBeenCalledWith(job))
    expect(enqueueExport).toHaveBeenCalledWith('xlsx')
  })

  it('queues a CSV when that format is chosen', async () => {
    vi.mocked(enqueueExport).mockResolvedValue({ id: 8 })
    render()

    await userEvent.click(screen.getByRole('radio', { name: 'CSV (.csv)' }))
    await userEvent.click(screen.getByRole('button', { name: /baixar/i }))

    await waitFor(() => expect(enqueueExport).toHaveBeenCalledWith('csv'))
  })

  it('does not follow anything when the export could not be queued', async () => {
    vi.mocked(enqueueExport).mockResolvedValue(null)
    render()

    await userEvent.click(screen.getByRole('button', { name: /baixar/i }))

    await waitFor(() => expect(enqueueExport).toHaveBeenCalled())
    expect(followExport).not.toHaveBeenCalled()
  })

  it('does not wait for the file: the button is free again as soon as the export is queued', async () => {
    vi.mocked(enqueueExport).mockResolvedValue({ id: 9 })
    vi.mocked(followExport).mockReturnValue(new Promise(() => {})) // a job that takes forever
    render()

    await userEvent.click(screen.getByRole('button', { name: /baixar/i }))

    await waitFor(() => expect(followExport).toHaveBeenCalled())
    expect(screen.getByRole('button', { name: /baixar/i })).toBeEnabled()
    await userEvent.click(screen.getByRole('button', { name: /baixar/i })) // a second export can be queued
    await waitFor(() => expect(enqueueExport).toHaveBeenCalledTimes(2))
  })

  it('says the file is built in the background', () => {
    render()

    expect(screen.getByText(/gerado em segundo plano/i)).toBeInTheDocument()
  })
})
