import { describe, expect, it } from 'vitest'
import { EMPTY_FILTERS, applyFilters, filtersFromLink, hasActiveFilters, writeFilters } from './transactionFilters'
import { transactionsLink } from './budget'

const t = (id, label, value, date, category_id = 1) => ({ id, label, value, transactioned_at: date, category_id })
const DATA = [
  t(1, 'Almoço', 2550, '2026-03-15T00:00:00'),
  t(2, 'Uber', 1800, '2026-03-10T23:59:59', 2),
  t(3, 'Mercado', 12000, '2026-03-02T10:00:00'),
]
const ids = (filters) => applyFilters(DATA, { ...EMPTY_FILTERS, ...filters }).map((x) => x.id)

describe('the filter on what counts in the totals', () => {
  const list = [{ id: 1, transactioned_at: '2026-03-10T10:00:00', value: 100 }, { id: 2, transactioned_at: '2026-03-10T10:00:00', value: 100, excluded: true }]
  const only = (counting) => applyFilters(list, { ...EMPTY_FILTERS, counting }).map((x) => x.id)

  it('shows everything by default, only the ones that count, or only the ones left out', () => {
    expect([only(''), only('counted'), only('left_out')]).toEqual([[1, 2], [1], [2]])
  })

  it('counts as an active filter', () => {
    expect(hasActiveFilters({ ...EMPTY_FILTERS, counting: 'left_out' })).toBe(true)
  })
})

describe('applyFilters', () => {
  it('keeps everything when no filter is set', () => {
    expect(ids({})).toEqual([1, 2, 3])
  })

  it('treats the date range as whole days, both ends included', () => {
    expect(ids({ from: '2026-03-15' })).toEqual([1])
    expect(ids({ to: '2026-03-10' })).toEqual([2, 3]) // 23:59:59 on the last day still counts
    expect(ids({ from: '2026-03-02', to: '2026-03-02' })).toEqual([3])
  })

  it('includes amounts equal to the limits', () => {
    expect(ids({ min: '18,00', max: '25,50' })).toEqual([1, 2])
  })

  it('matches the category by id', () => {
    expect(ids({ category: '2' })).toEqual([2])
  })

  it('ignores case and surrounding spaces in the search and tolerates missing labels', () => {
    expect(ids({ search: '  uBER ' })).toEqual([2])
    expect(applyFilters([t(9, null, 100, '2026-03-01T00:00:00')], { ...EMPTY_FILTERS, search: 'x' })).toEqual([])
  })
})

describe('hasActiveFilters', () => {
  it('is false for the empty filters and true as soon as one is set', () => {
    expect(hasActiveFilters(EMPTY_FILTERS)).toBe(false)
    expect(hasActiveFilters({ ...EMPTY_FILTERS, max: '1,00' })).toBe(true)
  })
})

describe('filtersFromLink', () => {
  it('has no filter without a link', () => {
    expect(filtersFromLink('')).toEqual(EMPTY_FILTERS)
  })

  it('reads the days and the type a link asks for', () => {
    expect(filtersFromLink('?from=2026-03-01&to=2026-03-31&type=debit')).toEqual({
      ...EMPTY_FILTERS,
      from: '2026-03-01',
      to: '2026-03-31',
      type: 'debit',
    })
    expect(filtersFromLink('?type=credit').type).toBe('credit')
  })

  it('ignores what is not a day or a type, and anything else in the link', () => {
    expect(filtersFromLink('?from=ontem&to=2026-13-45&type=pix&counting=maybe&category=abc&min=<b>&other=1')).toEqual(EMPTY_FILTERS)
    expect(filtersFromLink('?from=2026-3-1&to=2026-03-31')).toEqual({ ...EMPTY_FILTERS, to: '2026-03-31' })
  })

  it('reads and writes every filter, so the page can be reloaded or shared with its filters', () => {
    const filters = { search: 'pão', category: '3', type: 'debit', person: '2', merchant: '7', counting: 'left_out', from: '2026-03-01', to: '2026-03-31', min: '12,50', max: '1.000,00' }

    const params = writeFilters(new URLSearchParams('page=2'), filters)

    expect(filtersFromLink(params.toString())).toEqual(filters)
    expect(params.get('page')).toBe('2') // what is not a filter is kept
    expect(writeFilters(params, EMPTY_FILTERS).toString()).toBe('page=2') // empty filters leave no trace
  })

  it('reads back what the dashboard link asks for', () => {
    const search = transactionsLink('2026-03', 'debit').split('?')[1]

    expect(filtersFromLink(search)).toEqual({ ...EMPTY_FILTERS, from: '2026-03-01', to: '2026-03-31', type: 'debit' })
  })

  it('filters the transactions of the month, the last day included', () => {
    const list = [
      { transactioned_at: '2026-02-28T23:59:00', value: 1, type: 'debit' },
      { transactioned_at: '2026-03-01T00:00:00', value: 2, type: 'debit' },
      { transactioned_at: '2026-03-31T23:59:00', value: 4, type: 'debit' },
      { transactioned_at: '2026-04-01T00:00:00', value: 8, type: 'debit' },
      { transactioned_at: '2026-03-10T10:00:00', value: 16, type: 'credit' },
    ]

    const kept = applyFilters(list, filtersFromLink('?from=2026-03-01&to=2026-03-31&type=debit'))

    expect(kept.map((t) => t.value)).toEqual([2, 4])
  })
})
