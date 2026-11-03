import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { saveToken } from '../lib/auth'
import { formatCents } from '../lib/money'
import { useLocale } from '../lib/locale'
import { mockApi, renderApp } from '../test/helpers'
import Layout from './Layout'

function Amount() {
  useLocale()
  return <p>{formatCents(123450)}</p>
}

const renderLayout = () =>
  renderApp(
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Amount />} />
      </Route>
    </Routes>,
  )

beforeEach(() => saveToken('tok'))

describe('layout', () => {
  it('loads the currency and language of the family and every page shows them', async () => {
    mockApi({
      'GET /user/me': { data: { name: 'Clara' } },
      'GET /families/me': { data: { currency: 'USD', language: 'en', role: 'owner', members: [] } },
    })

    renderLayout()

    expect(await screen.findByText('$1,234.50')).toBeInTheDocument()
  })

  it('keeps reais and Portuguese when the settings cannot be loaded', async () => {
    mockApi({
      'GET /user/me': { data: { name: 'Clara' } },
      'GET /families/me': [{}, 500],
    })

    renderLayout()

    expect(await screen.findByText('R$ 1.234,50')).toBeInTheDocument()
  })
})
