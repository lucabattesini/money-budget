import { describe, expect, it } from 'vitest'
import { budgetsLink, budgetStatus, monthDays, monthFromLink, monthKey, monthLabel, shiftMonth, transactionsLink } from './budget'
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
    [9999, 10000, 'warn', 100],
    [10000, 10000, 'limit', 100], // exactly the plan: not over it, still within
    [10001, 10000, 'over', 100], // the bar never grows past full
    [25000, 10000, 'over', 100],
  ])('spent %i of %i is %s (bar at %i%%)', (spent, budgeted, state, percent) => {
    expect(budgetStatus(spent, budgeted)).toEqual({ state, percent })
  })

  it('has no bar when nothing is planned, however much was spent', () => {
    expect(budgetStatus(5000, null)).toEqual({ state: 'none', percent: 0 })
    expect(budgetStatus(5000, undefined)).toEqual({ state: 'none', percent: 0 })
  })

  it('treats 0 as a plan: spending nothing is within it, anything is over', () => {
    expect(budgetStatus(0, 0)).toEqual({ state: 'limit', percent: 0 })
    expect(budgetStatus(1, 0)).toEqual({ state: 'over', percent: 100 })
  })
})

describe('monthFromLink', () => {
  it('takes the month a link asks for', () => {
    expect(monthFromLink('2026-03', '2026-11')).toBe('2026-03')
    expect(monthFromLink('2000-01', '2026-11')).toBe('2000-01')
    expect(monthFromLink('2099-12', '2026-11')).toBe('2099-12')
  })

  it.each([null, undefined, '', 'março', '2026-3', '2026-13', '2026-00', '2026-03-15', '1999-12', '2100-01', '26-03'])(
    'falls back to the given month for %j',
    (value) => {
      expect(monthFromLink(value, '2026-11')).toBe('2026-11')
    },
  )
})

describe('monthDays', () => {
  it('gives the first and last day of the month', () => {
    expect(monthDays('2026-03')).toEqual({ from: '2026-03-01', to: '2026-03-31' })
    expect(monthDays('2026-04')).toEqual({ from: '2026-04-01', to: '2026-04-30' })
    expect(monthDays('2026-12')).toEqual({ from: '2026-12-01', to: '2026-12-31' })
  })

  it('knows February, leap years included', () => {
    expect(monthDays('2026-02').to).toBe('2026-02-28')
    expect(monthDays('2028-02').to).toBe('2028-02-29')
    expect(monthDays('2100-02').to).toBe('2100-02-28') // a century that is not a leap year
  })
})

describe('links from the dashboard', () => {
  it('opens the budgets on that month', () => {
    expect(budgetsLink('2026-03')).toBe('/budgets?month=2026-03')
  })

  it('opens the transactions with the days of that month, and optionally only debits or credits', () => {
    expect(transactionsLink('2026-02')).toBe('/transactions?from=2026-02-01&to=2026-02-28')
    expect(transactionsLink('2026-02', 'debit')).toBe('/transactions?from=2026-02-01&to=2026-02-28&type=debit')
    expect(transactionsLink('2026-02', 'credit')).toBe('/transactions?from=2026-02-01&to=2026-02-28&type=credit')
  })

  it('makes links the pages read back to the same month', () => {
    expect(monthFromLink(new URLSearchParams(budgetsLink('2027-05').split('?')[1]).get('month'), 'x')).toBe('2027-05')
  })
})
