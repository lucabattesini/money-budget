import { describe, expect, it } from 'vitest'
import { digitsToCents, formatCents, maskAmount } from './money'

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
