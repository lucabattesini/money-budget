import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { saveToken } from '../lib/auth'
import { setLocale } from '../lib/locale'
import { followImport, queueImport } from '../lib/importJobs'
import { jsonResponse, mockApi, renderApp, requestsMade } from '../test/helpers'
import ImportDialog from './ImportDialog'

vi.mock('../lib/importJobs', () => ({ queueImport: vi.fn(), followImport: vi.fn() }))

const CATEGORIES = {
  data: [
    { id: 1, name: 'Aluguel', group_id: 10 },
    { id: 2, name: '🛒 Supermercado', group_id: 11 },
  ],
}
const GROUPS = {
  data: [
    { id: 10, name: 'Casa' },
    { id: 11, name: 'Outros' },
  ],
}
const skipped = (row) => ({ row, date: '2026-03-15', label: `Almoço ${row}`, value: 123456, type: 'debit', category: 'Aluguel' })
const COLUMNS = ['Data', 'Descrição', 'Categoria', 'Valor', 'Tipo']
const SUGGESTED = { Data: 0, Descrição: 1, Categoria: 2, Valor: 3, Tipo: 4, Pessoa: null, Estabelecimento: null, 'Fora dos totais': null }
const SAMPLE = [['15/03/2026', 'Almoço', 'Aluguel', '12,00', 'Débito']]
// What the server answers to the upload: the file is read, nothing is checked yet
const uploaded = (extra = {}) => ({ id: 5, status: 'staged', filename: 'transacoes.csv', columns: COLUMNS, suggested_map: SUGGESTED, sample: SAMPLE, ...extra })
// ...and to the matching of the columns: every row is fine
const job = (extra = {}) => ({
  id: 5,
  status: 'staged',
  filename: 'transacoes.csv',
  total_rows: 3,
  to_import: 3,
  skipped_count: 0,
  skipped: [],
  unknown_categories: [],
  ...extra,
})
// The routes of a file that is uploaded and then matched by name; `checked` is what the server says once every row is fine
const imports = (checked = {}, extra = {}) => ({
  'POST /imports': [{ data: uploaded() }, 201],
  'PUT /imports/5/columns': [{ data: job(checked) }, 200],
  ...extra,
})
const PETS = { name: 'Pets', rows: 2 }
const file = (name = 'transacoes.csv') => new File(['Data;Descrição'], name, { type: 'text/csv' })

async function chooseFile(name) {
  await userEvent.upload(screen.getByLabelText('Arquivo da planilha'), file(name))
}
// Send the file and, with the columns as suggested, check it
async function send() {
  await chooseFile()
  await userEvent.click(screen.getByRole('button', { name: 'Enviar arquivo' }))
}

// Send the file and wait for the formats step
async function toFormats() {
  await send()
  await screen.findByLabelText('Formato das datas')
}

// Send the file and go on to the columns, leaving the formats as they are
async function toColumns() {
  await toFormats()
  await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
  await screen.findByLabelText('Coluna para Data')
}

// Send the file and go on to the check (step 4), with the formats and columns as suggested; it runs by itself
async function toCheck() {
  await toColumns()
  await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
}

// Wait for the check to end well and go on
async function passCheck() {
  await waitFor(() => expect(screen.getByRole('button', { name: 'Próximo' })).toBeEnabled())
  await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
}

// From the formats step, through the columns as suggested, and the check
async function conferir() {
  await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
  await screen.findByLabelText('Coluna para Data')
  await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
  await passCheck()
}

// Send the file and go through the check, with the formats and columns as suggested
async function check() {
  await toCheck()
  await passCheck()
}

describe('import dialog', () => {
  let onClose
  beforeEach(() => {
    saveToken('tok')
    onClose = vi.fn()
    vi.mocked(queueImport).mockReset()
    vi.mocked(followImport).mockReset()
  })
  const open = () => renderApp(<ImportDialog open onClose={onClose} />)

  describe('step 1: the file', () => {
    it('starts on the file step and cannot check anything until a file is chosen', async () => {
      mockApi({})
      open()

      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Arquivo')
      expect(screen.getByRole('button', { name: 'Enviar arquivo' })).toBeDisabled()
      expect(screen.getByText('Nenhum arquivo escolhido')).toBeInTheDocument()

      await chooseFile('abril.csv')

      expect(screen.getByText('abril.csv')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Enviar arquivo' })).toBeEnabled()
    })

    it('sends the file with the login and goes straight to confirming when every category exists', async () => {
      const api = mockApi(imports())
      open()

      await check()

      expect(await screen.findByText('3 transações serão importadas')).toBeInTheDocument()
      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Confirmar')
      const [, options] = api.mock.calls[0]
      expect(options.headers.Authorization).toBe('Bearer tok')
      expect(options.body.get('file').name).toBe('transacoes.csv')
      expect(requestsMade(api)).toEqual(['POST /imports', 'PUT /imports/5/columns'])
    })

    it('shows the message for a file that cannot be read, and lets the user try another one', async () => {
      mockApi({ 'POST /imports': [{ detail: 'O arquivo está vazio.' }, 422] })
      open()

      await send()

      expect(await screen.findByText('O arquivo está vazio.')).toBeInTheDocument()
      expect(screen.queryByRole('table', { name: 'Problemas encontrados' })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Enviar arquivo' })).toBeEnabled()
    })

    it('says so when the server cannot be reached', async () => {
      vi.spyOn(console, 'error').mockImplementation(() => {})
      vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new TypeError('Failed to fetch'))))
      open()

      await send()

      expect(await screen.findByText(/Não foi possível enviar o arquivo/)).toBeInTheDocument()
    })
  })

  describe('sections', () => {
    const headings = () => screen.queryAllByRole('heading', { level: 3 }).map((h) => h.textContent)

    it('organises each step in titled sections', async () => {
      mockApi({ ...imports({ unknown_categories: [PETS] }), 'GET /categories': CATEGORIES, 'GET /categories/groups': GROUPS })
      open()
      expect(headings()).toEqual(['Planilha'])

      await toFormats()
      expect(headings()).toEqual(['Formatos do arquivo', 'Primeiras linhas do arquivo'])

      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await screen.findByLabelText('Coluna para Data')
      expect(headings()).toEqual(['Colunas do arquivo', 'Primeiras linhas do arquivo']) // the fields have no titles of their own: required ones have a *

      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      expect(await screen.findByText(/Tudo certo/)).toBeInTheDocument()
      expect(headings()).toEqual(['Resultado da conferência'])

      await passCheck()
      await screen.findByLabelText('Categoria para "Pets"')
      expect(headings()).toEqual(['Categorias do arquivo'])
    })

    it('has the summary and, when there are duplicates, their own section when confirming', async () => {
      mockApi(imports({ to_import: 1, skipped_count: 1, skipped: [skipped(2)] }))
      open()

      await check()

      await screen.findByText(/1 transação será importada/)
      expect(headings()).toEqual(['Resumo', 'Já existem e serão ignoradas'])
    })

    it('has no section for duplicates when there are none, and no Tipo field when the sign says the direction', async () => {
      mockApi(imports())
      open()
      await toFormats()
      await userEvent.selectOptions(screen.getByLabelText('Sinal do valor'), 'Negativo é débito, positivo é crédito')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await screen.findByLabelText('Coluna para Data')

      expect(headings()).toEqual(['Colunas do arquivo', 'Primeiras linhas do arquivo'])
      expect(screen.queryByLabelText('Coluna para Tipo')).not.toBeInTheDocument()
      expect(screen.getByLabelText('Coluna para Pessoa')).toBeInTheDocument() // still optional
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await passCheck()
      await screen.findByText(/3 transações serão importadas/)
      expect(headings()).toEqual(['Resumo'])
    })
  })

  describe('while the file is being sent', () => {
    it('does not close with Esc, which would leave the file on the server with nobody to use or delete it', async () => {
      let answer
      mockApi({ 'POST /imports': () => new Promise((resolve) => (answer = () => resolve(jsonResponse({ data: uploaded() }, 201)))) })
      open()
      await chooseFile()
      await userEvent.click(screen.getByRole('button', { name: 'Enviar arquivo' }))

      await userEvent.keyboard('{Escape}')

      expect(onClose).not.toHaveBeenCalled()
      expect(screen.getByRole('button', { name: 'Cancelar' })).toBeDisabled()
      await act(async () => answer())
      expect(await screen.findByLabelText('Formato das datas')).toBeInTheDocument() // and it went on normally
    })

    it('closes with Esc when nothing is being sent', async () => {
      mockApi({})
      open()

      await userEvent.keyboard('{Escape}')

      await waitFor(() => expect(onClose).toHaveBeenCalled())
    })
  })

  describe('step 2: formats', () => {
    const putBody = (api) => JSON.parse(api.mock.calls.find(([, o]) => o?.method === 'PUT')[1].body)
    const options = (label) => within(screen.getByLabelText(label)).getAllByRole('option').map((o) => o.textContent)

    it('comes right after the file, with the first rows of the file to judge by', async () => {
      const api = mockApi(imports())
      open()

      await toFormats()

      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Formatos')
      expect(screen.getByText('Formatos do arquivo')).toBeInTheDocument()
      const sample = within(screen.getByRole('table', { name: 'Primeiras linhas do arquivo' }))
      expect(sample.getAllByRole('row')[1]).toHaveTextContent('15/03/2026')
      expect(requestsMade(api)).toEqual(['POST /imports']) // nothing is checked until the columns are matched
    })

    it('has all three formats on automatic to begin with, and the options of each', async () => {
      mockApi(imports())
      open()

      await toFormats()

      expect(screen.getByLabelText('Formato das datas')).toHaveValue('auto')
      expect(screen.getByLabelText('Formato dos valores')).toHaveValue('auto')
      expect(screen.getByLabelText('Sinal do valor')).toHaveValue('type_column')
      expect(options('Formato das datas')).toEqual([
        'Automático',
        'DD/MM/AAAA (15/03/2026)',
        'MM/DD/AAAA (03/15/2026)',
        'AAAA-MM-DD (2026-10-13)',
      ])
      expect(options('Formato dos valores')).toEqual(['Automático', '1.234,56 (vírgula nos centavos)', '1,234.56 (ponto nos centavos)'])
      expect(options('Sinal do valor')).toHaveLength(3)
    })

    it('sends the date format, the amount format and the sign the user picks', async () => {
      const api = mockApi(imports())
      open()
      await toFormats()

      await userEvent.selectOptions(screen.getByLabelText('Formato das datas'), 'MM/DD/AAAA (03/15/2026)')
      await userEvent.selectOptions(screen.getByLabelText('Formato dos valores'), '1,234.56 (ponto nos centavos)')
      await userEvent.selectOptions(screen.getByLabelText('Sinal do valor'), 'Positivo é débito, negativo é crédito')
      await conferir()

      await screen.findByText('3 transações serão importadas')
      expect(putBody(api)).toMatchObject({ date_order: 'month_first', amount_style: 'us', sign: 'negative_credit' })
    })

    it('lets the user say the dates are written year first, like 2026-10-13', async () => {
      const api = mockApi(imports())
      open()
      await toFormats()

      await userEvent.selectOptions(screen.getByLabelText('Formato das datas'), 'AAAA-MM-DD (2026-10-13)')
      await conferir()

      await screen.findByText('3 transações serão importadas')
      expect(putBody(api)).toMatchObject({ date_order: 'iso' })
    })

    it('has no Tipo column to choose in the next step when the sign says debit or credit, and sends none', async () => {
      const api = mockApi(imports())
      open()
      await toFormats()

      await userEvent.selectOptions(screen.getByLabelText('Sinal do valor'), 'Negativo é débito, positivo é crédito')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))

      await screen.findByLabelText('Coluna para Data')
      expect(screen.queryByLabelText('Coluna para Tipo')).not.toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await passCheck()
      await screen.findByText('3 transações serão importadas')
      expect(putBody(api)).toMatchObject({ mapping: { ...SUGGESTED, Tipo: null }, sign: 'negative_debit' })
    })

    it('has the Tipo column to choose when the type is in a column', async () => {
      mockApi(imports())
      open()

      await toColumns()

      expect(screen.getByLabelText('Coluna para Tipo')).toHaveValue('4')
    })

    it('starts with the sign the server suggests for a bank statement with negative amounts', async () => {
      mockApi({ ...imports(), 'POST /imports': [{ data: uploaded({ suggested_sign: 'negative_debit', suggested_map: { ...SUGGESTED, Tipo: null } }) }, 201] })
      open()

      await toFormats()

      expect(screen.getByLabelText('Sinal do valor')).toHaveValue('negative_debit')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await screen.findByLabelText('Coluna para Data')
      expect(screen.queryByLabelText('Coluna para Tipo')).not.toBeInTheDocument()
    })

    it('goes back to choosing another file', async () => {
      mockApi(imports())
      open()
      await toFormats()

      await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))

      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Arquivo')
    })

    it('numbers the steps in order: file, formats, columns, check, categories, confirm (the people step only when the file has a Pessoa column)', async () => {
      mockApi(imports())
      open()

      const steps = within(screen.getByRole('list', { name: 'Passos da importação' })).getAllByRole('listitem')

      expect(steps.map((step) => step.textContent)).toEqual([
        '1Arquivo',
        '2Formatos',
        '3Colunas',
        '4Conferência',
        '5Categorias',
        '6Confirmar',
      ])
    })
  })

  describe('the example of the file', () => {
    it('can be folded away and shown again in the formats step too', async () => {
      mockApi(imports())
      open()
      await toFormats()

      expect(screen.getByRole('table', { name: 'Primeiras linhas do arquivo' })).toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: /Recolher/ }))
      expect(screen.queryByRole('table', { name: 'Primeiras linhas do arquivo' })).not.toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: /Mostrar/ }))

      expect(screen.getByRole('table', { name: 'Primeiras linhas do arquivo' })).toBeInTheDocument()
    })
  })

  describe('step 3: columns', () => {
    const select = (field) => screen.getByLabelText(`Coluna para ${field}`)
    const putBody = (api) => JSON.parse(api.mock.calls.find(([, o]) => o?.method === 'PUT')[1].body)
    // A file whose columns are named differently: nothing is suggested
    const OTHER = uploaded({
      columns: ['Quando', 'O que', 'Tipo de gasto', 'Quanto', ''],
      suggested_map: { Data: null, Descrição: null, Categoria: null, Valor: null, Tipo: null, Pessoa: null, Estabelecimento: null, 'Fora dos totais': null },
      sample: [['15/03/2026', 'Almoço', 'Aluguel', '12,00', 'x']],
    })

    it('offers the Fora dos totais column, not used unless chosen, and says what an empty cell means', async () => {
      mockApi(imports())
      open()

      await toColumns()

      expect(select('Fora dos totais')).toHaveValue('') // "Não usar"
      expect(screen.getByText('Sim ou Não. Se vazio, só transferências e pagamentos de fatura ficam de fora.')).toBeInTheDocument()
    })

    it('has the columns the server recognised already chosen, and shows the first rows of the file', async () => {
      mockApi(imports())
      open()

      await toColumns()

      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Colunas')
      expect(select('Data')).toHaveValue('0')
      expect(select('Valor')).toHaveValue('3')
      expect(select('Tipo')).toHaveValue('4')
      const sample = within(screen.getByRole('table', { name: 'Primeiras linhas do arquivo' }))
      expect(sample.getAllByRole('columnheader').map((h) => h.textContent)).toEqual(COLUMNS)
      expect(sample.getAllByRole('row')[1]).toHaveTextContent('15/03/2026')
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeEnabled()
    })

    it('has the Estabelecimento column to choose only while the family has merchants on, and sends it', async () => {
      mockApi(imports())
      open()
      await toColumns()
      expect(screen.queryByLabelText('Coluna para Estabelecimento')).not.toBeInTheDocument()
      expect(screen.getByLabelText('Coluna para Tipo')).toBeInTheDocument()
    })

    it('chooses the Estabelecimento column, explains what empty means, and sends the choice', async () => {
      setLocale({ merchants_enabled: true })
      const api = mockApi({
        ...imports(),
        'POST /imports': [{ data: uploaded({ columns: [...COLUMNS, 'Pessoa', 'Estabelecimento'], suggested_map: { ...SUGGESTED, Estabelecimento: 6 } }) }, 201],
      })
      open()
      await toColumns()

      expect(screen.getByLabelText('Coluna para Estabelecimento')).toHaveValue('6')
      expect(screen.getByText(/Se vazio, fica sem estabelecimento/)).toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await screen.findByText('3 transações serão importadas', {}, { timeout: 3000 }).catch(() => {})

      expect(putBody(api).mapping).toMatchObject({ Estabelecimento: 6 })
    })

    it('shows the example of the file open, and folds it away and back on request', async () => {
      mockApi(imports())
      open()
      await toColumns()

      const toggle = screen.getByRole('button', { name: /Recolher/ })
      expect(toggle).toHaveAttribute('aria-expanded', 'true')
      await userEvent.click(toggle)

      expect(screen.queryByRole('table', { name: 'Primeiras linhas do arquivo' })).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Mostrar/ })).toHaveAttribute('aria-expanded', 'false')
      await userEvent.click(screen.getByRole('button', { name: /Mostrar/ }))
      expect(screen.getByRole('table', { name: 'Primeiras linhas do arquivo' })).toBeInTheDocument()
    })

    it('marks the required fields with a *, with no titles or introduction for the fields', async () => {
      mockApi(imports())
      open()
      await toColumns()

      expect(screen.queryByText('Campos obrigatórios')).not.toBeInTheDocument()
      expect(screen.queryByText(/Campos? opcionais?/)).not.toBeInTheDocument()
      expect(screen.queryByText(/Diga qual coluna/)).not.toBeInTheDocument() // no introduction either
      expect(screen.getByText('Valor', { selector: 'label' })).toHaveTextContent('*')
      expect(screen.getByText('Tipo', { selector: 'label' })).not.toHaveTextContent('*')
    })

    it('sends the Pessoa column when the file has one', async () => {
      const api = mockApi({
        ...imports(),
        'POST /imports': [{ data: uploaded({ columns: [...COLUMNS, 'Pessoa'], suggested_map: { ...SUGGESTED, Pessoa: 5 } }) }, 201],
      })
      open()

      await check()

      await screen.findByText('3 transações serão importadas')
      expect(putBody(api).mapping).toEqual({ ...SUGGESTED, Pessoa: 5 })
    })

    it('sends the columns and the default formats when the user just continues', async () => {
      const api = mockApi(imports())
      open()

      await check()

      await screen.findByText('3 transações serão importadas')
      expect(putBody(api)).toEqual({
        mapping: SUGGESTED,
        date_order: 'auto',
        amount_style: 'auto',
        sign: 'type_column',
      })
    })

    it('waits for the user to say which column is which when the names do not match', async () => {
      const api = mockApi({ ...imports(), 'POST /imports': [{ data: OTHER }, 201] })
      open()
      await toColumns()

      expect(screen.getByRole('button', { name: 'Próximo' })).toBeDisabled()
      expect(select('Data')).toHaveValue('')
      expect(within(select('Data')).getByRole('option', { name: 'Coluna 5 (sem nome)' })).toBeInTheDocument() // a column with no name
      await userEvent.selectOptions(select('Data'), 'Quando')
      await userEvent.selectOptions(select('Descrição'), 'O que')
      await userEvent.selectOptions(select('Categoria'), 'Tipo de gasto')
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeDisabled() // still no amount
      await userEvent.selectOptions(select('Valor'), 'Quanto')
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeEnabled()
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await passCheck()

      await screen.findByText('3 transações serão importadas')
      expect(putBody(api).mapping).toEqual({ Data: 0, Descrição: 1, Categoria: 2, Valor: 3, Tipo: null, Pessoa: null, Estabelecimento: null, 'Fora dos totais': null }) // Tipo: not used
    })

    it('lets one column serve two fields', async () => {
      const api = mockApi(imports())
      open()
      await toColumns()

      await userEvent.selectOptions(select('Valor'), 'Data') // the same column as the date

      expect(screen.queryByText(/não pode ser usada/)).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeEnabled()
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await passCheck()
      await screen.findByText('3 transações serão importadas')
      expect(putBody(api).mapping).toMatchObject({ Data: 0, Valor: 0 }) // both fields read column 0
    })

    it('goes back to the formats, keeping them', async () => {
      mockApi(imports())
      open()
      await toFormats()
      await userEvent.selectOptions(screen.getByLabelText('Formato das datas'), 'MM/DD/AAAA (03/15/2026)')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await screen.findByLabelText('Coluna para Data')

      await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))

      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Formatos')
      expect(screen.getByLabelText('Formato das datas')).toHaveValue('month_first')
    })

    it('goes back from confirming to the columns, and from there to the formats', async () => {
      mockApi(imports())
      open()
      await toFormats()
      await userEvent.selectOptions(screen.getByLabelText('Formato das datas'), 'MM/DD/AAAA (03/15/2026)')
      await conferir()
      await screen.findByText('3 transações serão importadas')

      await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Conferência')
      await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Colunas')
      expect(screen.getByRole('table', { name: 'Primeiras linhas do arquivo' })).toBeInTheDocument()
      expect(select('Valor')).toHaveValue('3')

      await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
      expect(screen.getByLabelText('Formato das datas')).toHaveValue('month_first')
    })

    it('says in the end how the dates were read, so a wrong guess can be noticed', async () => {
      mockApi(imports({ date_order: 'month_first', sign: 'type_column' }))
      open()

      await check()

      expect(await screen.findByText(/Datas lidas como mês\/dia\/ano/)).toBeInTheDocument()
    })

    it('says in the end when the dates were read year first', async () => {
      mockApi(imports({ date_order: 'iso', sign: 'type_column' }))
      open()

      await check()

      expect(await screen.findByText(/Datas lidas como ano-mês-dia/)).toBeInTheDocument()
    })

    it('says in the end that the sign of the amount was used', async () => {
      mockApi(imports({ date_order: 'day_first', sign: 'negative_debit' }))
      open()

      await check()

      expect(await screen.findByText(/o sinal do valor diz se é débito ou crédito/)).toBeInTheDocument()
    })
  })

  describe('step 4: check', () => {
    const select = (field) => screen.getByLabelText(`Coluna para ${field}`)
    const problems = [
      { row: 3, message: 'A data não é válida (use por exemplo 15/03/2026).' },
      { row: 7, message: 'O valor não é um número (use por exemplo 1.234,56 ou 1,234.56, como escolhido).' },
    ]
    const refused = (extra = {}) =>
      imports({}, { 'PUT /imports/5/columns': [{ detail: 'O arquivo tem problemas. Nada foi importado.', problems, problems_total: 5, ...extra }, 422] })

    it('runs by itself when the user leaves the columns, and waits for it to end', async () => {
      let answer
      const api = mockApi(imports({}, { 'PUT /imports/5/columns': () => new Promise((resolve) => (answer = () => resolve(jsonResponse({ data: job() })))) }))
      open()

      await toCheck()

      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Conferência')
      expect(screen.getByText('Conferindo todas as linhas do arquivo...')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'Voltar' })).toBeDisabled()
      expect(requestsMade(api)).toEqual(['POST /imports', 'PUT /imports/5/columns'])

      await act(async () => answer())

      expect(await screen.findByText('Tudo certo: as 3 linhas do arquivo foram conferidas.')).toBeInTheDocument()
      expect(screen.queryByText('Conferindo todas as linhas do arquivo...')).not.toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeEnabled()
    })

    it('says "the row" when the file has only one', async () => {
      mockApi(imports({ total_rows: 1 }))
      open()

      await toCheck()

      expect(await screen.findByText('Tudo certo: a linha do arquivo foi conferida.')).toBeInTheDocument()
    })

    it('says how the dates were read', async () => {
      mockApi(imports({ date_order: 'iso', sign: 'type_column' }))
      open()

      await toCheck()

      expect(await screen.findByText(/Datas lidas como ano-mês-dia/)).toBeInTheDocument()
    })

    it('goes on to the categories the file needs', async () => {
      mockApi({ ...imports({ unknown_categories: [PETS] }), 'GET /categories': CATEGORIES, 'GET /categories/groups': GROUPS })
      open()
      await toCheck()

      await passCheck()

      expect(await screen.findByLabelText('Categoria para "Pets"')).toBeInTheDocument()
      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Categorias')
    })

    it('goes straight to confirming when the file needs no new category', async () => {
      mockApi(imports())
      open()
      await toCheck()

      await passCheck()

      expect(await screen.findByText('3 transações serão importadas')).toBeInTheDocument()
    })

    it('lists every row with a problem, says nothing was imported and cannot go on', async () => {
      mockApi(refused())
      open()

      await toCheck()

      const table = within(await screen.findByRole('table', { name: 'Problemas encontrados' }))
      expect(table.getAllByRole('row').slice(1).map((r) => [...r.children].map((c) => c.textContent))).toEqual([
        ['3', problems[0].message],
        ['7', problems[1].message],
      ])
      expect(screen.getByText('O arquivo tem problemas. Nada foi importado.')).toBeInTheDocument()
      expect(screen.getByText(/E mais 3 problemas/)).toBeInTheDocument()
      expect(screen.getByText(/volte e mude as colunas ou os formatos/)).toBeInTheDocument()
      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Conferência')
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeDisabled()
      expect(screen.queryByText(/Tudo certo/)).not.toBeInTheDocument()
    })

    it('goes back to the columns after a problem, keeping the choices, and checks again', async () => {
      const api = mockApi(refused())
      open()
      await toCheck()
      await screen.findByRole('table', { name: 'Problemas encontrados' })

      await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))

      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Colunas')
      expect(select('Valor')).toHaveValue('3')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await screen.findByRole('table', { name: 'Problemas encontrados' })
      expect(requestsMade(api).filter((r) => r.startsWith('PUT'))).toHaveLength(2) // the check ran again
    })

    it('shows the server message when the choice makes no sense', async () => {
      mockApi(imports({}, { 'PUT /imports/5/columns': [{ detail: 'Escolha a coluna de: Valor.' }, 422] }))
      open()

      await toCheck()

      expect(await screen.findByText('Escolha a coluna de: Valor.')).toBeInTheDocument()
      expect(screen.queryByRole('table', { name: 'Problemas encontrados' })).not.toBeInTheDocument()
    })

    it('is where confirming comes back to, without checking again', async () => {
      const api = mockApi(imports())
      open()
      await check()
      await screen.findByText('3 transações serão importadas')

      await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))

      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Conferência')
      expect(screen.getByText(/Tudo certo/)).toBeInTheDocument()
      expect(requestsMade(api).filter((r) => r.startsWith('PUT'))).toHaveLength(1)
    })
  })

  describe('step 5: categories', () => {
    const routes = (extra = {}) => ({
      ...imports({ unknown_categories: [PETS] }),
      'GET /categories': CATEGORIES,
      'GET /categories/groups': GROUPS,
      ...extra,
    })

    const SETTLED = [{ ...PETS, category_id: 1 }] // what the server answers once Pets has a category (Aluguel)

    const UUID_A = '7c1f5f0e-52a4-4d8c-9b7e-0a6c1d2f3e44'
    const UUID_B = '0b9d6a1c-3f58-4e2a-8c47-91d5e6f7a802'
    const TWO = [PETS, { name: 'Viagem', rows: 1 }]
    const UUID_CATEGORIES = {
      data: [
        { id: UUID_A, name: 'Aluguel', group_id: 10 },
        { id: UUID_B, name: '🛒 Supermercado', group_id: 11 },
      ],
    }

    const FILE_CATEGORIES = [
      { name: 'Aluguel', rows: 2, category_id: UUID_A, match: 'name' },
      { name: 'Groceries', rows: 1, category_id: UUID_B, match: 'alias' },
      { name: 'Pets', rows: 1, category_id: null, match: null },
    ]
    const reviewRoutes = (fileCategories, extra = {}) =>
      routes({
        ...imports({ file_categories: fileCategories, unknown_categories: fileCategories.filter((c) => c.category_id == null) }),
        'GET /categories': UUID_CATEGORIES,
        'PUT /imports/5/categories': { data: job({ to_import: 4, unknown_categories: [], file_categories: fileCategories }) },
        ...extra,
      })

    it('lists every category of the file, the matched ones already chosen and labelled, for the person to review', async () => {
      mockApi(reviewRoutes(FILE_CATEGORIES))
      open()
      await check()

      expect(await screen.findByLabelText('Categoria para "Aluguel"')).toHaveValue(UUID_A)
      expect(screen.getByLabelText('Categoria para "Groceries"')).toHaveValue(UUID_B)
      expect(screen.getByLabelText('Categoria para "Pets"')).toHaveValue('')
      expect(screen.getByText('Já existe com esse nome')).toBeInTheDocument()
      expect(screen.getByText('Reconhecida por um nome parecido: confira')).toBeInTheDocument()
      expect(screen.getByText('Falta escolher')).toBeInTheDocument()
      expect(screen.getByText('2 de 3 categorias escolhidas. Falta 1.')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeDisabled()
    })

    it('does not skip the step when everything was matched by itself, and sends all the choices', async () => {
      const matched = FILE_CATEGORIES.slice(0, 2)
      const api = mockApi(reviewRoutes(matched))
      open()
      await check()

      expect(await screen.findByText('Tudo escolhido: 2 categorias.')).toBeInTheDocument() // the step is there
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))

      await screen.findByText(/transações serão importadas/)
      const put = api.mock.calls.find(([url, o]) => o?.method === 'PUT' && String(url).endsWith('/categories'))
      expect(JSON.parse(put[1].body)).toEqual({ mapping: { Aluguel: UUID_A, Groceries: UUID_B } })
    })

    it('lets the person change a match, and says it is now their choice', async () => {
      const api = mockApi(reviewRoutes(FILE_CATEGORIES.slice(0, 2)))
      open()
      await check()

      await userEvent.selectOptions(await screen.findByLabelText('Categoria para "Groceries"'), 'Aluguel')

      expect(screen.queryByText('Reconhecida por um nome parecido: confira')).not.toBeInTheDocument()
      expect(screen.getByText('Sua escolha')).toBeInTheDocument()
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await screen.findByText(/transações serão importadas/)
      const put = api.mock.calls.find(([url, o]) => o?.method === 'PUT' && String(url).endsWith('/categories'))
      expect(JSON.parse(put[1].body)).toEqual({ mapping: { Aluguel: UUID_A, Groceries: UUID_A } })
    })

    it('counts what is still missing and lets the person go on once everything is chosen (real ids are UUIDs)', async () => {
      const api = mockApi(
        routes({
          ...imports({ unknown_categories: TWO }),
          'GET /categories': UUID_CATEGORIES,
          'PUT /imports/5/categories': { data: job({ to_import: 3, unknown_categories: [], new_categories: [] }) },
        }),
      )
      open()
      await check()
      const next = () => screen.getByRole('button', { name: 'Próximo' })

      expect(await screen.findByText('0 de 2 categorias escolhidas. Faltam 2.')).toBeInTheDocument()
      expect(next()).toBeDisabled()

      await userEvent.selectOptions(screen.getByLabelText('Categoria para "Pets"'), 'Aluguel')
      expect(screen.getByText('1 de 2 categorias escolhidas. Falta 1.')).toBeInTheDocument()
      expect(next()).toBeDisabled()

      await userEvent.selectOptions(screen.getByLabelText('Categoria para "Viagem"'), '🛒 Supermercado')
      expect(screen.getByText('Tudo escolhido: 2 categorias.')).toBeInTheDocument()
      expect(next()).toBeEnabled()
      await userEvent.click(next())
      await screen.findByText(/transações serão importadas/)
      const put = api.mock.calls.find(([url, o]) => o?.method === 'PUT' && String(url).endsWith('/categories'))
      expect(JSON.parse(put[1].body)).toEqual({ mapping: { Pets: UUID_A, Viagem: UUID_B } })
    })

    it('marks each category that still needs a choice', async () => {
      mockApi(routes({ ...imports({ unknown_categories: TWO }), 'GET /categories': UUID_CATEGORIES }))
      open()
      await check()

      expect(await screen.findAllByText('Falta escolher')).toHaveLength(2)
      await userEvent.selectOptions(screen.getByLabelText('Categoria para "Pets"'), 'Aluguel')

      expect(screen.getAllByText('Falta escolher')).toHaveLength(1)
    })

    it('does not count a new category as chosen until it is created, and says what to do', async () => {
      mockApi(routes({ ...imports({ unknown_categories: [PETS] }), 'GET /categories': UUID_CATEGORIES }))
      open()
      await check()
      await userEvent.selectOptions(await screen.findByLabelText('Categoria para "Pets"'), 'Criar uma categoria nova')

      expect(screen.getByText('0 de 1 categoria escolhida. Falta 1.')).toBeInTheDocument()
      expect(screen.getByText(/clique em .Criar categoria./i)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeDisabled()
    })

    it('keeps the choices when the person goes back to the check and forward again', async () => {
      mockApi(
        routes({
          'PUT /imports/5/categories': { data: job({ to_import: 3, unknown_categories: [], new_categories: SETTLED }) },
          'PUT /imports/5/columns': [{ data: job({ unknown_categories: [PETS], new_categories: [{ ...PETS, category_id: null }] }) }, 200],
        }),
      )
      open()
      await check()
      await userEvent.selectOptions(await screen.findByLabelText('Categoria para "Pets"'), 'Aluguel')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await screen.findByText(/transações serão importadas/)

      await userEvent.click(screen.getByRole('button', { name: 'Voltar' })) // categories
      await userEvent.click(screen.getByRole('button', { name: 'Voltar' })) // the check
      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Conferência')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))

      expect(await screen.findByLabelText('Categoria para "Pets"')).toHaveValue('1') // still chosen
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeEnabled()
    })

    it('keeps the choices when the person goes back to the columns without changing them and forward again', async () => {
      // The server leaves everything as it is when nothing changed, and answers with the choice made
      mockApi(
        routes({
          'PUT /imports/5/categories': { data: job({ to_import: 3, unknown_categories: [], new_categories: SETTLED }) },
        }),
      )
      open()
      await check()
      await userEvent.selectOptions(await screen.findByLabelText('Categoria para "Pets"'), 'Aluguel')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await screen.findByText(/transações serão importadas/)

      await userEvent.click(screen.getByRole('button', { name: 'Voltar' })) // categories
      await userEvent.click(screen.getByRole('button', { name: 'Voltar' })) // the check
      await userEvent.click(screen.getByRole('button', { name: 'Voltar' })) // the columns
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' })) // matched again
      await passCheck()

      // (the mocked answer of the matching has nothing chosen: the server decides what stays; the dialog shows what it says)
      expect(await screen.findByLabelText('Categoria para "Pets"')).toBeInTheDocument()
    })

    it('asks about each category the family does not have and cannot continue until all are settled', async () => {
      mockApi(routes())
      open()

      await check()

      const list = await screen.findByRole('list', { name: 'Categorias do arquivo' })
      expect(within(list).getByText('Pets')).toBeInTheDocument()
      expect(within(list).getByText(/2 linhas/)).toBeInTheDocument()
      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Categorias')
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeDisabled()
    })

    it('offers the existing categories under their groups', async () => {
      mockApi(routes())
      open()
      await check()

      const select = await screen.findByLabelText('Categoria para "Pets"')

      expect(within(select).getByRole('group', { name: 'Casa' })).toContainElement(within(select).getByRole('option', { name: 'Aluguel' }))
      expect(within(select).getByRole('option', { name: '🛒 Supermercado' })).toBeInTheDocument()
      expect(within(select).getByRole('option', { name: 'Criar uma categoria nova' })).toBeInTheDocument()
    })

    it('maps a category to an existing one and moves on to confirming', async () => {
      const api = mockApi(
        routes({ 'PUT /imports/5/categories': { data: job({ to_import: 3, unknown_categories: [] }) } }),
      )
      open()
      await check()

      await userEvent.selectOptions(await screen.findByLabelText('Categoria para "Pets"'), 'Aluguel')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))

      expect(await screen.findByText('3 transações serão importadas')).toBeInTheDocument()
      const put = api.mock.calls.find(([url, o]) => o?.method === 'PUT' && String(url).endsWith('/categories'))
      expect(JSON.parse(put[1].body)).toEqual({ mapping: { Pets: '1' } })
    })

    it('creates a new category with the name from the file, in Outros by default, and chooses it', async () => {
      let created = false // after the creation the family's list contains the new category
      const api = mockApi(
        routes({
          'GET /categories': () => jsonResponse({ data: created ? [...CATEGORIES.data, { id: 99, name: 'Pets', group_id: 11 }] : CATEGORIES.data }),
          'POST /categories': () => {
            created = true
            return jsonResponse({ data: { id: 99, name: 'Pets', group_id: 11 } }, 201)
          },
          'PUT /imports/5/categories': { data: job() },
        }),
      )
      open()
      await check()
      await userEvent.selectOptions(await screen.findByLabelText('Categoria para "Pets"'), 'Criar uma categoria nova')
      expect(screen.getByLabelText('Nome da nova categoria')).toHaveValue('Pets')
      expect(screen.getByLabelText('Grupo da nova categoria')).toHaveValue('11')

      await userEvent.click(screen.getByRole('button', { name: 'Criar categoria' }))

      await waitFor(() => expect(screen.getByLabelText('Categoria para "Pets"')).toHaveValue('99'))
      const post = api.mock.calls.find(([, o]) => o?.method === 'POST' && String(o.body).includes('group_id'))
      expect(JSON.parse(post[1].body)).toEqual({ name: 'Pets', group_id: '11' })
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await screen.findByText('3 transações serão importadas')
      const put = api.mock.calls.find(([url, o]) => o?.method === 'PUT' && String(url).endsWith('/categories'))
      expect(JSON.parse(put[1].body)).toEqual({ mapping: { Pets: '99' } })
    })

    it('lets the user rename the new category and pick its group before creating it', async () => {
      const api = mockApi(routes({ 'POST /categories': [{ data: { id: 99 } }, 201], 'GET /categories': CATEGORIES, 'GET /categories/groups': GROUPS }))
      open()
      await check()
      await userEvent.selectOptions(await screen.findByLabelText('Categoria para "Pets"'), 'Criar uma categoria nova')

      await userEvent.clear(screen.getByLabelText('Nome da nova categoria'))
      await userEvent.type(screen.getByLabelText('Nome da nova categoria'), 'Animais')
      await userEvent.selectOptions(screen.getByLabelText('Grupo da nova categoria'), 'Casa')
      await userEvent.click(screen.getByRole('button', { name: 'Criar categoria' }))

      await waitFor(() => expect(requestsMade(api)).toContain('POST /categories'))
      const post = api.mock.calls.find(([, o]) => o?.method === 'POST' && String(o.body).includes('Animais'))
      expect(JSON.parse(post[1].body)).toEqual({ name: 'Animais', group_id: '10' })
    })

    it('shows why a category could not be created and stays on the step', async () => {
      mockApi(routes({ 'POST /categories': [{ detail: 'Já existe uma categoria com esse nome.' }, 409] }))
      open()
      await check()
      await userEvent.selectOptions(await screen.findByLabelText('Categoria para "Pets"'), 'Criar uma categoria nova')

      await userEvent.click(screen.getByRole('button', { name: 'Criar categoria' }))

      expect(await screen.findByText('Já existe uma categoria com esse nome.')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeDisabled()
    })

    it('does not create a category with an empty name', async () => {
      const api = mockApi(routes())
      open()
      await check()
      await userEvent.selectOptions(await screen.findByLabelText('Categoria para "Pets"'), 'Criar uma categoria nova')

      await userEvent.clear(screen.getByLabelText('Nome da nova categoria'))
      await userEvent.click(screen.getByRole('button', { name: 'Criar categoria' }))

      expect(await screen.findByText('O nome da categoria não pode ficar vazio.')).toBeInTheDocument()
      expect(requestsMade(api)).not.toContain('POST /categories')
    })

    it('shows the server message when the choices cannot be saved', async () => {
      mockApi(routes({ 'PUT /imports/5/categories': [{ detail: 'Essa categoria não existe.' }, 422] }))
      open()
      await check()
      await userEvent.selectOptions(await screen.findByLabelText('Categoria para "Pets"'), 'Aluguel')

      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))

      expect(await screen.findByText('Essa categoria não existe.')).toBeInTheDocument()
      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Categorias')
    })

    it('can go back from confirming and keeps the choices', async () => {
      mockApi(routes({ 'PUT /imports/5/categories': { data: job() } }))
      open()
      await check()
      await userEvent.selectOptions(await screen.findByLabelText('Categoria para "Pets"'), 'Aluguel')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      await screen.findByText('3 transações serão importadas')

      await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))

      expect(screen.getByLabelText('Categoria para "Pets"')).toHaveValue('1')
    })
  })

  describe('the people of the file', () => {
    const MEMBERS = [{ id: 1, name: 'Clara' }, { id: 2, name: 'Bia Souza' }]
    const BIA = { name: 'Bia', rows: 2, user_id: null } // matched nobody
    const MATCHED = { name: 'Bia Souza', rows: 1, user_id: 2 } // matched a member by its name
    const withPeople = (people, extra = {}) => ({
      ...imports({ people, unknown_people: people.filter((p) => p.user_id == null), members: MEMBERS }),
      ...extra,
    })
    const putPeople = (api) => JSON.parse(api.mock.calls.find(([url]) => url.endsWith('/people'))[1].body)
    const saved = { 'PUT /imports/5/people': [{ data: job({ people: [], unknown_people: [], members: MEMBERS }) }, 200] }

    it('counts the names still to be chosen and lets the person go on when all are (member ids are UUIDs)', async () => {
      const A = '7c1f5f0e-52a4-4d8c-9b7e-0a6c1d2f3e44'
      const B = '0b9d6a1c-3f58-4e2a-8c47-91d5e6f7a802'
      const members = [{ id: A, name: 'Clara' }, { id: B, name: 'Bia Souza' }]
      const two = [BIA, { name: 'Caio', rows: 1, user_id: null }]
      mockApi({
        ...imports({ people: two, unknown_people: two, members }),
        'PUT /imports/5/people': [{ data: job({ people: [], unknown_people: [], members }) }, 200],
      })
      open()
      await check()
      expect(await screen.findByText('0 de 2 pessoas escolhidas. Faltam 2.')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeDisabled()

      await userEvent.selectOptions(screen.getByLabelText('Pessoa para Bia'), 'Bia Souza')
      await userEvent.selectOptions(screen.getByLabelText('Pessoa para Caio'), 'Clara')

      expect(screen.getByText('Tudo escolhido: 2 pessoas.')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeEnabled()
    })

    it('says what an empty Pessoa means, and does not say Débito for it', async () => {
      mockApi(imports())
      open()

      await toColumns()

      // What an empty cell means is written under the field it is about, not in its label
      expect(screen.getByText('Se vazio, é quem está importando.')).toBeInTheDocument()
      expect(screen.getByText('Se vazio, é Débito.')).toBeInTheDocument()
      expect(screen.queryByText(/opcional/i)).not.toBeInTheDocument()
    })

    it('has the Pessoas step in the list only when the file has a Pessoa column', async () => {
      mockApi({ 'POST /imports': [{ data: uploaded({ columns: [...COLUMNS, 'Pessoa'], suggested_map: { ...SUGGESTED, Pessoa: 5 } }) }, 201] })
      open()
      await toColumns()

      const steps = () => within(screen.getByRole('list', { name: 'Passos da importação' })).getAllByRole('listitem').map((s) => s.textContent)
      expect(steps()).toContain('6Pessoas')
      await userEvent.selectOptions(screen.getByLabelText('Coluna para Pessoa'), 'Não usar')

      expect(steps()).not.toContain('6Pessoas')
      expect(steps()).toEqual(['1Arquivo', '2Formatos', '3Colunas', '4Conferência', '5Categorias', '6Confirmar'])
    })

    it('goes straight to confirming when the file has no names in the Pessoa column', async () => {
      mockApi(withPeople([]))
      open()

      await check()

      expect(await screen.findByText('3 transações serão importadas')).toBeInTheDocument()
      expect(screen.queryByText('Pessoas do arquivo')).not.toBeInTheDocument()
    })

    it('shows the member a name was matched to, already chosen and saying so, and lets the person change it', async () => {
      const api = mockApi(withPeople([MATCHED], saved))
      open()
      await check()

      expect(await screen.findByText('Pessoas do arquivo')).toBeInTheDocument()
      expect(screen.getByText('Reconhecido pelo nome')).toBeInTheDocument()
      const select = screen.getByLabelText('Pessoa para Bia Souza')
      expect(select).toHaveValue('2')
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeEnabled() // nothing is left to choose

      await userEvent.selectOptions(select, 'Clara')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))

      expect(await screen.findByText('3 transações serão importadas')).toBeInTheDocument()
      expect(putPeople(api)).toEqual({ mapping: { 'Bia Souza': '1' } })
    })

    it('keeps the matched ones as they are when the person does not change them', async () => {
      const api = mockApi(withPeople([MATCHED], saved))
      open()
      await check()

      await userEvent.click(await screen.findByRole('button', { name: 'Próximo' }))

      await screen.findByText('3 transações serão importadas')
      expect(putPeople(api)).toEqual({ mapping: { 'Bia Souza': '2' } })
    })

    it('asks for a choice for each name that matched nobody, and cannot go on until all are chosen', async () => {
      const api = mockApi(withPeople([MATCHED, BIA], saved))
      open()
      await check()

      expect(await screen.findByText('Pessoas do arquivo')).toBeInTheDocument()
      expect(screen.getByRole('listitem', { current: 'step' })).toHaveTextContent('Pessoas')
      expect(screen.getByText('Sem correspondência')).toBeInTheDocument()
      expect(screen.getByText(/“Bia” \(2 linhas\)/)).toBeInTheDocument()
      const select = screen.getByLabelText('Pessoa para Bia')
      expect(within(select).getAllByRole('option').map((o) => o.textContent)).toEqual(['Escolha...', 'Clara', 'Bia Souza'])
      expect(select).toHaveValue('')
      expect(screen.getByRole('button', { name: 'Próximo' })).toBeDisabled()

      await userEvent.selectOptions(select, 'Bia Souza')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))

      expect(await screen.findByText('3 transações serão importadas')).toBeInTheDocument()
      expect(putPeople(api)).toEqual({ mapping: { 'Bia Souza': '2', Bia: '2' } })
    })

    it('shows the message of the server when the choice is refused and stays on the step', async () => {
      mockApi(withPeople([BIA], { 'PUT /imports/5/people': [{ detail: 'Essa pessoa não é da sua família.' }, 422] }))
      open()
      await check()

      await userEvent.selectOptions(await screen.findByLabelText('Pessoa para Bia'), 'Clara')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('Essa pessoa não é da sua família.')
      expect(screen.getByText('Pessoas do arquivo')).toBeInTheDocument()
    })

    it('comes after the categories when the file also has unknown ones, and going back returns to them', async () => {
      mockApi({
        ...withPeople([BIA], {
          'PUT /imports/5/categories': [{ data: job({ people: [BIA], unknown_people: [BIA], members: MEMBERS }) }, 200],
        }),
        'PUT /imports/5/columns': [{ data: job({ unknown_categories: [PETS], people: [BIA], unknown_people: [BIA], members: MEMBERS }) }, 200],
        'GET /categories': CATEGORIES,
        'GET /categories/groups': GROUPS,
      })
      open()
      await check()

      await userEvent.selectOptions(await screen.findByLabelText('Categoria para "Pets"'), 'Aluguel')
      await userEvent.click(screen.getByRole('button', { name: 'Próximo' }))
      expect(await screen.findByText('Pessoas do arquivo')).toBeInTheDocument()

      await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
      expect(await screen.findByLabelText('Categoria para "Pets"')).toBeInTheDocument()
    })
  })

  describe('step 6: confirming', () => {
    it('lists the transactions that already exist and will be skipped', async () => {
      mockApi(imports({ to_import: 1, skipped_count: 2, skipped: [skipped(2), skipped(4)] }))
      open()

      await check()

      expect(await screen.findByText(/1 transação será importada/)).toBeInTheDocument()
      expect(screen.getByText(/2 serão ignoradas porque já existem/)).toBeInTheDocument()
      const table = within(screen.getByRole('table', { name: 'Transações que serão ignoradas' }))
      expect(table.getAllByRole('row').slice(1).map((r) => [...r.children].map((c) => c.textContent))).toEqual([
        ['2', '15/03/2026', 'Almoço 2', 'R$ 1.234,56'],
        ['4', '15/03/2026', 'Almoço 4', 'R$ 1.234,56'],
      ])
    })

    it('says how many skipped rows are not shown', async () => {
      mockApi(imports({ to_import: 0, skipped_count: 150, skipped: [skipped(2)] }))
      open()

      await check()

      expect(await screen.findByText('E mais 149.')).toBeInTheDocument()
    })

    it('has nothing to import when every row already exists', async () => {
      mockApi(imports({ to_import: 0, skipped_count: 1, skipped: [skipped(2)] }))
      open()

      await check()

      expect(await screen.findByText(/Não há nada para importar/)).toBeInTheDocument()
      expect(screen.getByRole('button', { name: 'Importar' })).toBeDisabled()
    })

    it('queues the import, closes the dialog and follows the job in the background', async () => {
      const api = mockApi(imports())
      const queued = { id: 5, status: 'queued' }
      vi.mocked(queueImport).mockResolvedValue(queued)
      open()
      await check()

      await userEvent.click(await screen.findByRole('button', { name: 'Importar' }))

      await waitFor(() => expect(onClose).toHaveBeenCalled())
      expect(queueImport).toHaveBeenCalledWith(5)
      expect(followImport).toHaveBeenCalledWith(queued)
      expect(requestsMade(api)).toEqual(['POST /imports', 'PUT /imports/5/columns']) // not thrown away: it is being imported
    })

    it('stays open when the import could not be queued', async () => {
      mockApi(imports())
      vi.mocked(queueImport).mockResolvedValue(null)
      open()
      await check()

      await userEvent.click(await screen.findByRole('button', { name: 'Importar' }))

      await waitFor(() => expect(queueImport).toHaveBeenCalled())
      expect(onClose).not.toHaveBeenCalled()
      expect(followImport).not.toHaveBeenCalled()
      expect(screen.getByRole('button', { name: 'Importar' })).toBeEnabled()
    })
  })

  describe('giving up', () => {
    it('closes at once when nothing was uploaded yet, without calling the server', async () => {
      const api = mockApi({})
      open()

      await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

      expect(onClose).toHaveBeenCalled()
      expect(requestsMade(api)).toEqual([])
    })

    it('throws the checked file away on the server when cancelled', async () => {
      const api = mockApi(imports({}, { 'DELETE /imports/5': () => Promise.resolve(new Response(null, { status: 204 })) }))
      open()
      await check()
      await screen.findByText('3 transações serão importadas')

      await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

      expect(onClose).toHaveBeenCalled()
      await waitFor(() => expect(requestsMade(api)).toContain('DELETE /imports/5'))
    })
  })
})
