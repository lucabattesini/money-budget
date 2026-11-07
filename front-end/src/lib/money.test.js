import { describe, expect, it } from 'vitest'
import { budgetEditText, budgetFieldText, budgetTextToCents, digitsToCents, formatBudgetCents, formatCents, maskAmount, sanitizeBudgetText } from './money'

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
  it('does not put back the zero in front of the decimals while the person edits', () => {
    expect(sanitizeBudgetText(',5')).toBe(',5')
    expect(sanitizeBudgetText('0,5')).toBe('0,5')
  })

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
    ['12,345', 1234500], // three digits after the separator: thousands
    ['0,05', 5],
    ['0', 0], // a plan to spend nothing
    ['', null], // no plan
    ['abc', null],
    ['1.500', 150000], // a thousands separator, as the field shows saved amounts
    ['1.500,00', 150000],
    ['1,500', 150000],
    ['1.234.567', 123456700],
    ['1.50', 150], // two digits after it: decimals
    ['0,500', 50], // zero reais is not thousands
    ['1500,501', 150050], // four whole digits: decimals, the third is dropped
    [',', null], // only a separator is no plan, not a 0 plan
    ['.', null],
    [',5', 50],
    ['99999999', 999999900], // a digit that would not fit the database is not accepted
    ['21474835,99', 2147483599],
    ['21474836', 214748300]
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
