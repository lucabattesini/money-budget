import { afterEach, describe, expect, it, vi } from 'vitest'
import { CURRENCIES, familyNow, formatDate, formatMoney, getLocale, setLocale, TIMEZONES } from './locale'
import { formatCents, maskAmount } from './money'

describe('the family\'s currency and language', () => {
  it('start as reais and Portuguese, as the app always looked', () => {
    expect(getLocale()).toEqual({ currency: 'BRL', language: 'pt', timezone: 'America/Sao_Paulo', merchantsEnabled: false })
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

    expect(getLocale()).toEqual({ currency: 'EUR', language: 'en', timezone: 'America/Sao_Paulo', merchantsEnabled: false })
  })

  it('ignores a value that is not offered, so a bad answer never breaks the page', () => {
    setLocale({ currency: 'JPY', language: 'fr' })

    expect(getLocale()).toEqual({ currency: 'BRL', language: 'pt', timezone: 'America/Sao_Paulo', merchantsEnabled: false })
    expect(formatCents(100)).toBe('R$ 1,00')
  })

  it('starts with merchants off, and the family can turn them on and off, ignoring anything that is not a boolean', () => {
    expect(getLocale().merchantsEnabled).toBe(false)

    setLocale({ merchants_enabled: true })
    expect(getLocale().merchantsEnabled).toBe(true)
    setLocale({ merchants_enabled: 'yes' })
    expect(getLocale().merchantsEnabled).toBe(true)
    setLocale({ currency: 'EUR' }) // another setting leaves it alone
    expect(getLocale().merchantsEnabled).toBe(true)
    setLocale({ merchants_enabled: false })
    expect(getLocale().merchantsEnabled).toBe(false)
  })
})

describe('"now" on the family\'s clock (TKT-65)', () => {
  afterEach(() => vi.useRealTimers())

  const at = (iso) => vi.useFakeTimers({ now: new Date(iso), toFake: ['Date'] })

  it('is still the last day of the month in Brasília when it is already the next one in UTC', () => {
    at('2026-04-01T01:30:15Z') // 22:30:15 on 31 March in Brasília (UTC-3)

    const now = familyNow()

    expect([now.getFullYear(), now.getMonth() + 1, now.getDate()]).toEqual([2026, 3, 31])
    expect([now.getHours(), now.getMinutes(), now.getSeconds()]).toEqual([22, 30, 15])
  })

  it('follows the timezone of the family', () => {
    at('2026-04-01T01:30:00Z')
    setLocale({ timezone: 'Europe/Lisbon' }) // UTC+1 in April

    const now = familyNow()

    expect([now.getMonth() + 1, now.getDate(), now.getHours(), now.getMinutes()]).toEqual([4, 1, 2, 30])
  })

  it('never shows 24 as the hour at midnight', () => {
    at('2026-04-01T03:00:00Z') // midnight in Brasília

    expect(familyNow().getHours()).toBe(0)
  })

  it('offers only timezones the back-end accepts, Brasília first', () => {
    expect(TIMEZONES[0].code).toBe('America/Sao_Paulo')
    expect(TIMEZONES.map((z) => z.code)).toContain('America/Toronto')
  })

  it('ignores a timezone that is not offered', () => {
    setLocale({ timezone: 'Mars/Olympus' })

    expect(getLocale().timezone).toBe('America/Sao_Paulo')
  })
})
