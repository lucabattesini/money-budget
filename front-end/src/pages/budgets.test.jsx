import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { toaster } from '../components/ui/toaster'
import { saveToken } from '../lib/auth'
import { monthKey, shiftMonth } from '../lib/budget'
import { setLocale } from '../lib/locale'
import { mockApi, renderApp, requestsMade } from '../test/helpers'
import Budgets from './budgets'

const NOW = monthKey(new Date())
const NEXT = shiftMonth(NOW, 1)
const PREV = shiftMonth(NOW, -1)

const category = (id, name, budgeted = null, spent = 0, since = budgeted ? NOW : null) => ({ id, name, budgeted, since, spent })
const group = (id, name, categories) => ({
  id,
  name,
  categories,
  budgeted: categories.reduce((sum, c) => sum + (c.budgeted || 0), 0),
  spent: categories.filter((c) => c.budgeted).reduce((sum, c) => sum + c.spent, 0),
})

// Food is planned and on track, Rent is nearly used up, Transport is over, Pets has nothing planned
function month(key, overrides = {}) {
  const groups = [
    group(1, 'Alimentação', [category(10, '🍽️ Restaurantes e Bares', 50000, 20000), category(11, '🛒 Supermercado')]),
    group(2, 'Moradia', [category(20, '🏠 Aluguel', 180000, 150000)]),
    group(3, 'Auto e Transporte', [category(30, '🚌 Transporte público', 10000, 15000)]),
    group(4, 'Viagem e Estilo de Vida', [category(40, '🐾 Pets')]), // nothing planned, nothing spent
  ]
  return {
    month: key,
    totals: { budgeted: 240000, spent: 185000, unbudgeted_spent: 0, remaining: 55000 },
    groups,
    ...overrides,
  }
}

const EMPTY = {
  month: NOW,
  totals: { budgeted: 0, spent: 0, unbudgeted_spent: 0, remaining: 0 },
  groups: [group(1, 'Alimentação', [category(10, '🍽️ Restaurantes e Bares')])],
}

const calls = (api, method) =>
  api.mock.calls.filter(([, o]) => (o?.method || 'GET').toUpperCase() === method).map(([url, o]) => ({ url, body: o?.body && JSON.parse(o.body) }))

beforeEach(() => {
  saveToken('tok')
  toaster.remove() // toasts live in a global store: an earlier test's toast would crowd out the one we look for
})

describe('budgets page: what it shows', () => {
  it('shows the month, the totals and every group with its categories', async () => {
    mockApi({ [`GET /budgets?month=${NOW}`]: { data: month(NOW) } })

    renderApp(<Budgets />)

    expect(await screen.findByText('Orçado')).toBeInTheDocument()
    expect(screen.getByText('R$ 2.400,00')).toBeInTheDocument()
    expect(screen.getByText('R$ 1.850,00')).toBeInTheDocument()
    expect(screen.getByText('R$ 550,00')).toBeInTheDocument()
    expect(screen.getByText('Restante')).toBeInTheDocument()
    for (const name of ['Alimentação', 'Moradia', 'Auto e Transporte']) {
      expect(screen.getByRole('button', { name: new RegExp(`^${name}:`) })).toBeInTheDocument()
    }
  })

  it('shows what is planned in the field of each category and leaves the others empty', async () => {
    mockApi({ [`GET /budgets?month=${NOW}`]: { data: month(NOW) } })

    renderApp(<Budgets />)

    expect(await screen.findByLabelText('Orçamento de Restaurantes e Bares')).toHaveValue('500,00')
    expect(screen.getByLabelText('Orçamento de Aluguel')).toHaveValue('1.800,00')
    expect(screen.getByLabelText('Orçamento de Supermercado')).toHaveValue('')
    expect(screen.getByLabelText('Orçamento de Supermercado')).toHaveAttribute('placeholder', '0,00')
  })

  it('says what is left for a category and warns when it is close or over', async () => {
    mockApi({ [`GET /budgets?month=${NOW}`]: { data: month(NOW) } })

    renderApp(<Budgets />)

    await screen.findByText('Orçado')
    expect(within(screen.getByRole('list', { name: 'Alimentação' })).getByText('Restam R$ 300,00')).toBeInTheDocument() // 200 of 500
    expect(within(screen.getByRole('list', { name: 'Moradia' })).getByText('Perto do limite')).toBeInTheDocument() // 1.500 of 1.800 is 83%
    expect(within(screen.getByRole('list', { name: 'Alimentação' })).queryByText('Perto do limite')).not.toBeInTheDocument()
    expect(screen.getByText('Estourou R$ 50,00')).toBeInTheDocument() // Transport: 150 of 100
    expect(screen.getByText('Acima do orçamento')).toBeInTheDocument()
  })

  it('shows what was spent in a category that has nothing planned, without a bar', async () => {
    const data = month(NOW)
    data.groups[0].categories[1] = category(11, '🛒 Supermercado', null, 8000)
    data.totals.unbudgeted_spent = 8000
    mockApi({ [`GET /budgets?month=${NOW}`]: { data } })

    renderApp(<Budgets />)

    expect(await screen.findByLabelText('Gasto em Supermercado')).toHaveTextContent('R$ 80,00')
    expect(screen.queryByLabelText('Gasto de Supermercado no orçamento')).not.toBeInTheDocument()
    expect(screen.getByText(/Gasto em categorias sem orçamento: R\$ 80,00/)).toBeInTheDocument()
  })

  it('says "Estourou" with the amount over when the month is over budget', async () => {
    mockApi({
      [`GET /budgets?month=${NOW}`]: {
        data: month(NOW, { totals: { budgeted: 10000, spent: 16000, unbudgeted_spent: 0, remaining: -6000 } }),
      },
    })

    renderApp(<Budgets />)

    expect(await screen.findByText('Estourou')).toBeInTheDocument()
    expect(screen.getByText('R$ 60,00')).toBeInTheDocument()
    expect(screen.queryByText('Restante')).not.toBeInTheDocument()
  })

  it('suggests what to do when nothing is planned', async () => {
    mockApi({ [`GET /budgets?month=${NOW}`]: { data: EMPTY } })

    renderApp(<Budgets />)

    expect(await screen.findByText(/Nada planejado para este mês/)).toBeInTheDocument()
  })

  it('starts with every group open, the empty ones too, and lets each be closed and opened again', async () => {
    mockApi({ [`GET /budgets?month=${NOW}`]: { data: month(NOW) } })
    renderApp(<Budgets />)
    await screen.findByText('Orçado')

    for (const field of ['Aluguel', 'Restaurantes e Bares', 'Transporte público', 'Pets']) {
      expect(screen.getByLabelText(`Orçamento de ${field}`)).toBeInTheDocument()
    }
    for (const name of ['Alimentação', 'Moradia', 'Auto e Transporte', 'Viagem e Estilo de Vida']) {
      expect(screen.getByRole('button', { name: `${name}: fechar` })).toHaveAttribute('aria-expanded', 'true')
    }

    await userEvent.click(screen.getByRole('button', { name: 'Moradia: fechar' }))
    expect(screen.queryByLabelText('Orçamento de Aluguel')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Orçamento de Pets')).toBeInTheDocument() // the others stay as they were

    await userEvent.click(screen.getByRole('button', { name: 'Moradia: abrir' }))
    expect(screen.getByLabelText('Orçamento de Aluguel')).toBeInTheDocument()
  })

  it('lists the categories of a group A-Z in Portuguese order, accents and emoji aside', async () => {
    const data = month(NOW)
    data.groups[0].categories = [
      category(1, '🅱️ Zebra'),
      category(2, '🅰️ Água'),
      category(3, '🥐 Abelha'),
      category(4, 'Cafeterias'),
    ]
    mockApi({ [`GET /budgets?month=${NOW}`]: { data } })

    renderApp(<Budgets />)

    const list = await screen.findByRole('list', { name: 'Alimentação' })
    expect(within(list).getAllByRole('listitem').map((item) => within(item).getByRole('textbox').getAttribute('aria-label'))).toEqual([
      'Orçamento de Abelha',
      'Orçamento de Água',
      'Orçamento de Cafeterias',
      'Orçamento de Zebra',
    ])
  })

  it('says which month an amount is repeated from, and nothing when it was set in this month', async () => {
    const data = month(NOW)
    data.groups[0].categories[0] = category(10, '🍽️ Restaurantes e Bares', 50000, 20000, shiftMonth(NOW, -2))
    mockApi({ [`GET /budgets?month=${NOW}`]: { data } })

    renderApp(<Budgets />)

    const food = within((await screen.findByLabelText('Orçamento de Restaurantes e Bares')).closest('li'))
    expect(food.getByText(/Repetido de /)).toBeInTheDocument()
    const rent = within(screen.getByLabelText('Orçamento de Aluguel').closest('li')) // set in this very month
    expect(rent.queryByText(/Repetido de /)).not.toBeInTheDocument()
  })

  it('writes amounts in the currency and language of the family', async () => {
    setLocale({ currency: 'USD', language: 'en' })
    mockApi({ [`GET /budgets?month=${NOW}`]: { data: month(NOW) } })

    renderApp(<Budgets />)

    expect(await screen.findByText('US$2,400.00')).toBeInTheDocument()
    expect(screen.getByLabelText('Orçamento de Restaurantes e Bares')).toHaveValue('500.00')
  })

  it('says so when the month cannot be loaded', async () => {
    mockApi({ [`GET /budgets?month=${NOW}`]: [{}, 500] })

    renderApp(<Budgets />)

    expect(await screen.findByText(/Não foi possível carregar o orçamento/)).toBeInTheDocument()
  })
})

describe('budgets page: planning', () => {
  const planned = (data, id, amount) => {
    const copy = structuredClone(data)
    for (const g of copy.groups) for (const c of g.categories) if (c.id === id) c.budgeted = amount
    return copy
  }

  it('saves the amount typed in a category when the field is left, and shows the answer', async () => {
    const after = planned(month(NOW), 11, 30000)
    after.totals = { budgeted: 270000, spent: 185000, unbudgeted_spent: 0, remaining: 85000 }
    const api = mockApi({ [`GET /budgets?month=${NOW}`]: { data: month(NOW) }, 'PUT /budgets': { data: after } })
    renderApp(<Budgets />)

    const field = await screen.findByLabelText('Orçamento de Supermercado')
    await userEvent.type(field, '30000')
    expect(field).toHaveValue('300,00') // masked as it is typed
    await userEvent.tab()

    await waitFor(() => expect(screen.getByText('R$ 2.700,00')).toBeInTheDocument())
    expect(calls(api, 'PUT')).toEqual([{ url: 'http://api.test/budgets', body: { category_id: 11, month: NOW, amount: 30000 } }])
    expect(screen.getByLabelText('Orçamento de Supermercado')).toHaveValue('300,00')
  })

  it('saves with Enter as well', async () => {
    const api = mockApi({
      [`GET /budgets?month=${NOW}`]: { data: month(NOW) },
      'PUT /budgets': { data: planned(month(NOW), 11, 1234) },
    })
    renderApp(<Budgets />)

    await userEvent.type(await screen.findByLabelText('Orçamento de Supermercado'), '1234{Enter}')

    await waitFor(() => expect(calls(api, 'PUT')).toHaveLength(1))
    expect(calls(api, 'PUT')[0].body.amount).toBe(1234)
  })

  it('removes the budget when the field is emptied', async () => {
    const api = mockApi({
      [`GET /budgets?month=${NOW}`]: { data: month(NOW) },
      'PUT /budgets': { data: planned(month(NOW), 10, null) },
    })
    renderApp(<Budgets />)

    await userEvent.clear(await screen.findByLabelText('Orçamento de Restaurantes e Bares'))
    await userEvent.tab()

    await waitFor(() => expect(calls(api, 'PUT')).toHaveLength(1))
    expect(calls(api, 'PUT')[0].body).toEqual({ category_id: 10, month: NOW, amount: 0 })
    await waitFor(() => expect(screen.getByLabelText('Orçamento de Restaurantes e Bares')).toHaveValue(''))
  })

  it('does not call the server when nothing changed', async () => {
    const api = mockApi({ [`GET /budgets?month=${NOW}`]: { data: month(NOW) } })
    renderApp(<Budgets />)

    const field = await screen.findByLabelText('Orçamento de Restaurantes e Bares')
    await userEvent.click(field)
    await userEvent.tab()
    await userEvent.click(screen.getByLabelText('Orçamento de Supermercado'))
    await userEvent.tab()

    expect(calls(api, 'PUT')).toEqual([])
  })

  it('goes back to what is saved and says so when it cannot save', async () => {
    mockApi({
      [`GET /budgets?month=${NOW}`]: { data: month(NOW) },
      'PUT /budgets': [{ detail: 'Categoria não encontrada.' }, 404],
    })
    renderApp(<Budgets />)

    await userEvent.type(await screen.findByLabelText('Orçamento de Supermercado'), '500')
    await userEvent.tab()

    expect(await screen.findByText('Categoria não encontrada.')).toBeInTheDocument()
    expect(screen.getByLabelText('Orçamento de Supermercado')).toHaveValue('')
  })
})

describe('budgets page: months', () => {
  it('goes to the next and the previous month and asks the server for each', async () => {
    const api = mockApi({
      [`GET /budgets?month=${NOW}`]: { data: month(NOW) },
      [`GET /budgets?month=${NEXT}`]: { data: { ...EMPTY, month: NEXT } },
      [`GET /budgets?month=${PREV}`]: { data: { ...EMPTY, month: PREV } },
    })
    renderApp(<Budgets />)
    await screen.findByText('Orçado')

    await userEvent.click(screen.getByRole('button', { name: 'Próximo mês' }))
    await screen.findByText(/Nada planejado/)
    await userEvent.click(screen.getByRole('button', { name: 'Mês anterior' }))
    await userEvent.click(screen.getByRole('button', { name: 'Mês anterior' }))

    await waitFor(() =>
      expect(requestsMade(api).filter((r) => r.startsWith('GET /budgets'))).toEqual([
        `GET /budgets?month=${NOW}`,
        `GET /budgets?month=${NEXT}`,
        `GET /budgets?month=${NOW}`,
        `GET /budgets?month=${PREV}`,
      ]),
    )
  })

  it('names the month it shows', async () => {
    mockApi({
      [`GET /budgets?month=${NOW}`]: { data: month(NOW) },
      [`GET /budgets?month=${NEXT}`]: { data: { ...EMPTY, month: NEXT } },
    })
    renderApp(<Budgets />)
    const heading = await screen.findByRole('heading', { name: /\d{4}$/ })
    const before = heading.textContent

    await userEvent.click(screen.getByRole('button', { name: 'Próximo mês' }))

    await waitFor(() => expect(screen.getByRole('heading', { name: /\d{4}$/ }).textContent).not.toBe(before))
  })

  it('keeps the page of the month on screen when a slow answer for another month arrives late', async () => {
    let answerNow
    mockApi({
      [`GET /budgets?month=${NOW}`]: () =>
        new Promise((resolve) => {
          answerNow = () => resolve(new Response(JSON.stringify({ data: month(NOW) }), { status: 200 }))
        }),
      [`GET /budgets?month=${NEXT}`]: { data: { ...EMPTY, month: NEXT } },
    })
    renderApp(<Budgets />)

    await userEvent.click(screen.getByRole('button', { name: 'Próximo mês' }))
    await screen.findByText(/Nada planejado/)
    answerNow() // the answer for the month we already left

    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(screen.getByText(/Nada planejado/)).toBeInTheDocument()
    expect(within(document.body).queryByText('R$ 2.400,00')).not.toBeInTheDocument()
  })
})

describe('budgets page: slow and failing answers', () => {
  const withBudgets = (...changes) => {
    const data = structuredClone(month(NOW))
    for (const [id, amount] of changes)
      for (const g of data.groups) for (const c of g.categories) if (c.id === id) c.budgeted = amount
    return data
  }
  const answer = (data) => new Response(JSON.stringify({ data }), { status: 200 })

  it('keeps the newest answer when an older save finishes late', async () => {
    let finishFirst
    let puts = 0
    mockApi({
      [`GET /budgets?month=${NOW}`]: { data: month(NOW) },
      'PUT /budgets': () => {
        puts += 1
        if (puts === 1) return new Promise((resolve) => (finishFirst = () => resolve(answer(withBudgets([11, 30000])))))
        return Promise.resolve(answer(withBudgets([11, 30000], [40, 70000]))) // the server had both by then
      },
    })
    renderApp(<Budgets />)
    await userEvent.type(await screen.findByLabelText('Orçamento de Supermercado'), '30000')
    await userEvent.tab() // the first save is still on its way
    await userEvent.type(screen.getByLabelText('Orçamento de Pets'), '70000')
    await userEvent.tab()
    await waitFor(() => expect(screen.getByLabelText('Orçamento de Pets')).toHaveValue('700,00'))

    finishFirst() // the older answer arrives last, and knows nothing about Pets

    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(screen.getByLabelText('Orçamento de Pets')).toHaveValue('700,00')
    expect(screen.getByLabelText('Orçamento de Supermercado')).toHaveValue('300,00')
  })

  it('stops showing the error once another month loads', async () => {
    mockApi({
      [`GET /budgets?month=${NOW}`]: [{}, 500],
      [`GET /budgets?month=${NEXT}`]: { data: { ...EMPTY, month: NEXT } },
    })
    renderApp(<Budgets />)
    await screen.findByText(/Não foi possível carregar o orçamento/)

    await userEvent.click(screen.getByRole('button', { name: 'Próximo mês' }))

    expect(await screen.findByText(/Nada planejado/)).toBeInTheDocument()
    expect(screen.queryByText(/Não foi possível carregar o orçamento/)).not.toBeInTheDocument()
  })

  it.each([
    [new Date(2000, 0, 15), 'Mês anterior'],
    [new Date(2099, 11, 15), 'Próximo mês'],
  ])('does not go past the years the server offers (%s: %s is off)', async (now, button) => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(now)
    const key = monthKey(now)
    mockApi({ [`GET /budgets?month=${key}`]: { data: { ...EMPTY, month: key } } })

    renderApp(<Budgets />)

    await screen.findByText(/Nada planejado/)
    expect(screen.getByRole('button', { name: button })).toBeDisabled()
  })
})
