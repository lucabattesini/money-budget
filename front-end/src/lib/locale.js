// How this family sees amounts and dates: its currency, language and timezone (a setting of the family, loaded when the
// app opens and kept here). Amounts are stored as integer cents and are never converted between currencies: the currency
// only decides the symbol. The language decides the separators and the order of day and month.
//
// The timezone says which clock "now" is read from: a transaction's date and time are the wall-clock time of the
// family (TKT-65), so "today" and "this month" must not depend on the clock of the device that opens the page.
//
// Until the settings arrive (or when they cannot be loaded) the app looks as it always did: reais, Portuguese,
// Brasília time.
import { useSyncExternalStore } from 'react'

// `name` is what the amount is "in" ("Em reais (R$)"), `label` is how the setting offers it
export const CURRENCIES = [
  { code: 'BRL', symbol: 'R$', name: 'reais', label: 'Real brasileiro (R$)' },
  { code: 'USD', symbol: 'US$', name: 'dólares', label: 'Dólar americano (US$)' },
  { code: 'CAD', symbol: 'CA$', name: 'dólares canadenses', label: 'Dólar canadense (CA$)' },
  { code: 'EUR', symbol: '€', name: 'euros', label: 'Euro (€)' },
  { code: 'GBP', symbol: '£', name: 'libras', label: 'Libra esterlina (£)' },
]

export const LANGUAGES = [
  { code: 'pt', label: 'Português' },
  { code: 'en', label: 'English' },
]

export const TIMEZONES = [
  { code: 'America/Sao_Paulo', label: 'Brasília (São Paulo)' },
  { code: 'America/New_York', label: 'Nova York' },
  { code: 'America/Chicago', label: 'Chicago' },
  { code: 'America/Denver', label: 'Denver' },
  { code: 'America/Los_Angeles', label: 'Los Angeles' },
  { code: 'America/Toronto', label: 'Toronto' },
  { code: 'America/Vancouver', label: 'Vancouver' },
  { code: 'Europe/Lisbon', label: 'Lisboa' },
  { code: 'Europe/London', label: 'Londres' },
  { code: 'Europe/Paris', label: 'Paris' },
  { code: 'Europe/Berlin', label: 'Berlim' },
  { code: 'UTC', label: 'UTC' },
]

const DEFAULT = Object.freeze({ currency: 'BRL', language: 'pt', timezone: 'America/Sao_Paulo', merchantsEnabled: false })
const BCP47 = { pt: 'pt-BR', en: 'en-US' } // the language tag each language is formatted with

let current = DEFAULT
const listeners = new Set()

export const getLocale = () => current

/** Use what the family chose. A value that is not offered is ignored, so a bad answer never breaks the page. */
export function setLocale({ currency, language, timezone, merchants_enabled: merchantsEnabled } = {}) {
  const next = {
    currency: CURRENCIES.some((c) => c.code === currency) ? currency : current.currency,
    language: LANGUAGES.some((l) => l.code === language) ? language : current.language,
    timezone: TIMEZONES.some((z) => z.code === timezone) ? timezone : current.timezone,
    merchantsEnabled: typeof merchantsEnabled === 'boolean' ? merchantsEnabled : current.merchantsEnabled,
  }
  if (Object.keys(next).every((key) => next[key] === current[key])) return
  current = Object.freeze(next)
  listeners.forEach((listener) => listener())
}

export const resetLocale = () => {
  current = DEFAULT
  listeners.forEach((listener) => listener())
}

const subscribe = (listener) => {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

/** The family's { currency, language, timezone, merchantsEnabled }; the component shows the new format as soon as it changes. */
export const useLocale = () => useSyncExternalStore(subscribe, getLocale)

/** The language tag for Intl and toLocale...String: "pt-BR" or "en-US". */
export const languageTag = () => BCP47[current.language]

/** 1234.5 -> "R$ 1.234,50" (Portuguese) or "R$1,234.50" (English). The amount is in whole units, not cents. */
export const formatMoney = (value, options = {}) => {
  // The symbol comes from the table above, not from Intl, so the page and the WhatsApp assistant write the same
  // ("US$1,234.50": Intl alone would write "$" for English)
  const symbol = CURRENCIES.find((c) => c.code === current.currency).symbol
  return new Intl.NumberFormat(languageTag(), { style: 'currency', currency: current.currency, ...options })
    .formatToParts(value || 0)
    .map((part) => (part.type === 'currency' ? symbol : part.value))
    .join('')
    .replace(/\s/g, ' ')
}

/** A date as people write it: 05/03/2026 in Portuguese, 3/5/2026 in English. */
export const formatDate = (value, options) => new Date(value).toLocaleDateString(languageTag(), options)

/**
 * What the clock on the family's wall says right now, as a Date whose local fields (getFullYear, getMonth, getDate,
 * getHours...) are those of the family's timezone. Read it with the local getters, like every stored date, and never
 * compare it with `Date.now()`. `new Date()` would be the clock of this device, which may be in another timezone.
 */
export const familyNow = () => {
  const parts = Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: current.timezone,
      hourCycle: 'h23',
      year: 'numeric',
      month: 'numeric',
      day: 'numeric',
      hour: 'numeric',
      minute: 'numeric',
      second: 'numeric',
    })
      .formatToParts(new Date())
      .map((part) => [part.type, Number(part.value)]),
  )
  return new Date(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second)
}
