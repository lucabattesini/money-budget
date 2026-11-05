import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it } from 'vitest'
import { saveToken } from '../lib/auth'
import { getLocale } from '../lib/locale'
import { mockApi, renderApp, requestsMade } from '../test/helpers'
import AccountPreferences from './account-preferences'

const family = (settings = {}) => ({ data: { currency: 'BRL', language: 'pt', timezone: 'America/Sao_Paulo', role: 'member', members: [], ...settings } })

beforeEach(() => saveToken('tok'))

describe('preferences', () => {
  it('shows what the family chose', async () => {
    mockApi({ 'GET /families/me': family({ currency: 'USD', language: 'en' }) })

    renderApp(<AccountPreferences />)

    expect(await screen.findByLabelText('Moeda')).toHaveValue('USD')
    expect(screen.getByLabelText('Idioma')).toHaveValue('en')
  })

  it('offers the currencies, Canadian dollars included, and Portuguese and English', async () => {
    mockApi({ 'GET /families/me': family() })

    renderApp(<AccountPreferences />)

    const options = (name) => screen.getAllByRole('option', { name: (_, el) => el.parentElement === screen.getByLabelText(name) })
    await screen.findByLabelText('Moeda')
    expect(options('Moeda').map((o) => o.value)).toEqual(['BRL', 'USD', 'CAD', 'EUR', 'GBP'])
    expect(options('Idioma').map((o) => o.value)).toEqual(['pt', 'en'])
  })

  it('saves a new currency for the family and uses it at once', async () => {
    const api = mockApi({
      'GET /families/me': family(),
      'PATCH /families/me/settings': family({ currency: 'CAD' }),
    })
    renderApp(<AccountPreferences />)

    await userEvent.selectOptions(await screen.findByLabelText('Moeda'), 'CAD')

    expect(await screen.findByText('Preferência salva para toda a família.')).toBeInTheDocument()
    const call = api.mock.calls.find(([, options]) => options?.method?.toUpperCase() === 'PATCH')
    expect(JSON.parse(call[1].body)).toEqual({ currency: 'CAD' }) // only what was changed
    expect(getLocale().currency).toBe('CAD')
  })

  it('saves a new language', async () => {
    const api = mockApi({
      'GET /families/me': family(),
      'PATCH /families/me/settings': family({ language: 'en' }),
    })
    renderApp(<AccountPreferences />)

    await userEvent.selectOptions(await screen.findByLabelText('Idioma'), 'en')

    await waitFor(() => expect(getLocale().language).toBe('en'))
    expect(requestsMade(api)).toContain('PATCH /families/me/settings')
  })

  it('goes back to the previous choice and says so when it cannot be saved', async () => {
    mockApi({
      'GET /families/me': family(),
      'PATCH /families/me/settings': [{ detail: 'Não foi possível salvar agora.' }, 500],
    })
    renderApp(<AccountPreferences />)

    await userEvent.selectOptions(await screen.findByLabelText('Moeda'), 'EUR')

    expect(await screen.findByText('Não foi possível salvar agora.')).toBeInTheDocument()
    expect(screen.getByLabelText('Moeda')).toHaveValue('BRL')
    expect(getLocale().currency).toBe('BRL')
  })

  it('says so when the preferences cannot be loaded', async () => {
    mockApi({ 'GET /families/me': [{}, 500] })

    renderApp(<AccountPreferences />)

    expect(await screen.findByText(/Não foi possível carregar as preferências/)).toBeInTheDocument()
  })

  it('shows and offers the timezones', async () => {
    mockApi({ 'GET /families/me': family({ timezone: 'America/Toronto' }) })

    renderApp(<AccountPreferences />)

    expect(await screen.findByLabelText('Fuso horário')).toHaveValue('America/Toronto')
    expect(screen.getByRole('option', { name: 'Brasília (São Paulo)' })).toBeInTheDocument()
  })

  it('saves a new timezone for the family, and only that', async () => {
    const api = mockApi({
      'GET /families/me': family(),
      'PATCH /families/me/settings': family({ timezone: 'Europe/London' }),
    })
    renderApp(<AccountPreferences />)

    await userEvent.selectOptions(await screen.findByLabelText('Fuso horário'), 'Europe/London')

    await waitFor(() => expect(getLocale().timezone).toBe('Europe/London'))
    const call = api.mock.calls.find(([, options]) => options?.method?.toUpperCase() === 'PATCH')
    expect(JSON.parse(call[1].body)).toEqual({ timezone: 'Europe/London' })
  })
})
