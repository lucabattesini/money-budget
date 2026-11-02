import { describe, expect, it } from 'vitest'
import { EMPTY_FILTERS, applyFilters, hasActiveFilters } from './transactionFilters'

const t = (id, label, value, date, category_id = 1) => ({ id, label, value, transactioned_at: date, category_id })
const DATA = [
  t(1, 'Almoço', 2550, '2026-03-15T00:00:00'),
  t(2, 'Uber', 1800, '2026-03-10T23:59:59', 2),
  t(3, 'Mercado', 12000, '2026-03-02T10:00:00'),
]
const ids = (filters) => applyFilters(DATA, { ...EMPTY_FILTERS, ...filters }).map((x) => x.id)

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
