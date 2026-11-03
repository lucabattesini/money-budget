import { describe, expect, it } from 'vitest'
import { CURRENCIES, formatDate, formatMoney, getLocale, setLocale } from './locale'
import { formatCents, maskAmount } from './money'

describe('the family\'s currency and language', () => {
  it('start as reais and Portuguese, as the app always looked', () => {
    expect(getLocale()).toEqual({ currency: 'BRL', language: 'pt' })
    expect(formatCents(123450)).toBe('R$ 1.234,50')
  })

  it.each([
    ['BRL', 'pt', 'R$ 1.234,50'],
    ['BRL', 'en', 'R$1,234.50'],
    ['USD', 'pt', 'US$ 1.234,50'],
    ['USD', 'en', 'US$1,234.50'], // the same as the WhatsApp assistant writes
    ['CAD', 'en', 'CA$1,234.50'],
    ['EUR', 'pt', '€ 1.234,50'],
    ['GBP', 'en', '£1,234.50'],
  ])('shows 1234.5 in %s for the language %s as "%s"', (currency, language, text) => {
    setLocale({ currency, language })

    expect(formatMoney(1234.5)).toBe(text)
  })

  it('offers Canadian dollars', () => {
    expect(CURRENCIES.map((c) => c.code)).toContain('CAD')
  })

  it('formats cents and the amount being typed in the language of the family', () => {
    setLocale({ currency: 'USD', language: 'en' })

    expect(formatCents(123456)).toBe('US$1,234.56')
    expect(maskAmount('123456')).toBe('1,234.56')
    expect(maskAmount('5')).toBe('0.05')
  })

  it('writes dates in the order of the language', () => {
    expect(formatDate('2026-03-05T12:00:00')).toBe('05/03/2026')

    setLocale({ language: 'en' })

    expect(formatDate('2026-03-05T12:00:00')).toBe('3/5/2026')
  })

  it('changes one setting and keeps the other', () => {
    setLocale({ currency: 'EUR' })
    setLocale({ language: 'en' })

    expect(getLocale()).toEqual({ currency: 'EUR', language: 'en' })
  })

  it('ignores a value that is not offered, so a bad answer never breaks the page', () => {
    setLocale({ currency: 'JPY', language: 'fr' })

    expect(getLocale()).toEqual({ currency: 'BRL', language: 'pt' })
    expect(formatCents(100)).toBe('R$ 1,00')
  })
})
