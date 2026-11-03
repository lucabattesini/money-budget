import { describe, expect, it } from 'vitest'
import { budgetStatus, monthKey, monthLabel, shiftMonth } from './budget'
import { setLocale } from './locale'

describe('months', () => {
  it('names the month a date falls in', () => {
    expect(monthKey(new Date(2026, 10, 30, 23, 59))).toBe('2026-11')
    expect(monthKey(new Date(2027, 0, 1))).toBe('2027-01')
  })

  it.each([
    ['2026-11', 1, '2026-12'],
    ['2026-12', 1, '2027-01'],
    ['2027-01', -1, '2026-12'],
    ['2026-03', -3, '2025-12'],
    ['2026-11', 0, '2026-11'],
    ['2026-01', 13, '2027-02'],
  ])('%s moved by %i is %s', (key, delta, expected) => {
    expect(shiftMonth(key, delta)).toBe(expected)
  })

  it('writes the month in the language of the family', () => {
    expect(monthLabel('2026-11')).toBe('novembro de 2026')

    setLocale({ language: 'en' })

    expect(monthLabel('2026-11')).toBe('November 2026')
  })
})

describe('how a category is going', () => {
  it.each([
    [0, 10000, 'ok', 0],
    [7999, 10000, 'ok', 80],
    [8000, 10000, 'warn', 80], // from 80% on the bar warns
    [10000, 10000, 'warn', 100], // spending exactly the plan is not over it
    [10001, 10000, 'over', 100], // the bar never grows past full
    [25000, 10000, 'over', 100],
  ])('spent %i of %i is %s (bar at %i%%)', (spent, budgeted, state, percent) => {
    expect(budgetStatus(spent, budgeted)).toEqual({ state, percent })
  })

  it('has no bar when nothing is planned, however much was spent', () => {
    expect(budgetStatus(5000, 0)).toEqual({ state: 'none', percent: 0 })
    expect(budgetStatus(5000, null)).toEqual({ state: 'none', percent: 0 })
  })
})
