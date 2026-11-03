// How this family sees amounts and dates: its currency and language (a setting of the family, loaded when the app
// opens and kept here). Amounts are stored as integer cents and are never converted between currencies: the currency
// only decides the symbol. The language decides the separators and the order of day and month.
//
// Until the settings arrive (or when they cannot be loaded) the app looks as it always did: reais, Portuguese.
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

const DEFAULT = Object.freeze({ currency: 'BRL', language: 'pt' })
const BCP47 = { pt: 'pt-BR', en: 'en-US' } // the language tag each language is formatted with

let current = DEFAULT
const listeners = new Set()

export const getLocale = () => current

/** Use what the family chose. A value that is not offered is ignored, so a bad answer never breaks the page. */
export function setLocale({ currency, language } = {}) {
  const next = {
    currency: CURRENCIES.some((c) => c.code === currency) ? currency : current.currency,
    language: LANGUAGES.some((l) => l.code === language) ? language : current.language,
  }
  if (next.currency === current.currency && next.language === current.language) return
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

/** The family's { currency, language }; the component shows the new format as soon as it changes. */
export const useLocale = () => useSyncExternalStore(subscribe, getLocale)

/** The language tag for Intl and toLocale...String: "pt-BR" or "en-US". */
export const languageTag = () => BCP47[current.language]

/** 1234.5 -> "R$ 1.234,50" (Portuguese) or "R$1,234.50" (English). The amount is in whole units, not cents. */
export const formatMoney = (value, options = {}) =>
  new Intl.NumberFormat(languageTag(), { style: 'currency', currency: current.currency, ...options })
    .format(value || 0)
    .replace(/\s/g, ' ')

/** A date as people write it: 05/03/2026 in Portuguese, 3/5/2026 in English. */
export const formatDate = (value, options) => new Date(value).toLocaleDateString(languageTag(), options)
