import { describe, expect, it } from 'vitest'
import { budgetEditText, budgetFieldText, budgetTextToCents, digitsToCents, formatBudgetCents, formatCents, maskAmount } from './money'

describe('formatCents', () => {
  it.each([
    [2550, 'R$ 25,50'],
    [1800, 'R$ 18,00'],
    [5, 'R$ 0,05'],
    [0, 'R$ 0,00'],
    [123456, 'R$ 1.234,56'],
    [100000000, 'R$ 1.000.000,00'],
  ])('shows %i cents as "%s", always with two decimals', (cents, text) => {
    expect(formatCents(cents)).toBe(text)
  })

  it('shows R$ 0,00 for a missing amount', () => {
    expect(formatCents(undefined)).toBe('R$ 0,00')
    expect(formatCents(null)).toBe('R$ 0,00')
  })
})

describe('maskAmount', () => {
  it.each([
    ['', ''],
    ['abc', ''],
    ['0', '0,00'],
    ['5', '0,05'],
    ['55', '0,55'],
    ['2550', '25,50'],
    ['025', '0,25'],
    ['123456', '1.234,56'],
    ['123456789', '1.234.567,89'],
  ])('turns "%s" into "%s"', (typed, shown) => {
    expect(maskAmount(typed)).toBe(shown)
  })

  it('stops accepting digits once the amount no longer fits the database', () => {
    expect(maskAmount('2147483647')).toBe('21.474.836,47')
    expect(maskAmount('21474836479')).toBe('21.474.836,47')
  })

  it('ignores separators and letters, so editing the masked text keeps working', () => {
    expect(maskAmount('25,5')).toBe('2,55')
    expect(maskAmount('1.234,56x')).toBe('1.234,56')
  })
})

describe('digitsToCents', () => {
  it('reads the cents out of masked text', () => {
    expect(digitsToCents('1.234,56')).toBe(123456)
    expect(digitsToCents('0,05')).toBe(5)
    expect(digitsToCents('')).toBe(0)
  })
})

describe('budget amounts', () => {
  it('formats whole amounts without decimals and keeps them when there are cents', () => {
    expect(formatBudgetCents(150000)).toBe('R$ 1.500')
    expect(formatBudgetCents(150050)).toBe('R$ 1.500,50')
    expect(formatBudgetCents(0)).toBe('R$ 0')
  })

  it.each([
    ['1500', 150000],
    ['12,5', 1250],
    ['12.5', 1250],
    ['12,34', 1234],
    ['12,345', 1234],
    ['0,05', 5],
    ['0', 0], // a plan to spend nothing
    ['', null], // no plan
    ['abc', null],
    ['99999999', 2147483647],
  ])('reads "%s" as %s cents', (typed, cents) => {
    expect(budgetTextToCents(typed)).toBe(cents)
  })

  it('shows a saved amount to edit without thousands separators', () => {
    expect(budgetEditText(150000)).toBe('1500')
    expect(budgetEditText(150050)).toBe('1500,50')
    expect(budgetFieldText(150000)).toBe('1.500')
    expect(budgetFieldText(0)).toBe('0')
    expect(budgetFieldText(null)).toBe('')
  })
})
