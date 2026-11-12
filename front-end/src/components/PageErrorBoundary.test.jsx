import { lazy, Suspense } from 'react'
import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Provider } from './ui/provider'
import PageErrorBoundary from './PageErrorBoundary'

const broken = () => lazy(() => Promise.reject(new TypeError('Failed to fetch dynamically imported module: /assets/budgets-OLD.js')))

describe('a page file that cannot be downloaded', () => {
  let reload
  beforeEach(() => {
    sessionStorage.clear()
    reload = vi.fn()
    vi.stubGlobal('location', { ...window.location, reload })
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  const show = () => {
    const Page = broken()
    render(
      <Provider>
        <PageErrorBoundary>
          <Suspense fallback="carregando">
            <Page />
          </Suspense>
        </PageErrorBoundary>
      </Provider>,
    )
  }

  it('reloads once to get the new version, and shows a way to reload by hand', async () => {
    show()

    expect(await screen.findByText('Não foi possível abrir esta página.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Recarregar' })).toBeInTheDocument()
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('does not reload again when the reload did not help (no loop)', async () => {
    sessionStorage.setItem('money-budget-reloaded-for-new-version', '1')

    show()

    expect(await screen.findByText('Não foi possível abrir esta página.')).toBeInTheDocument()
    expect(reload).not.toHaveBeenCalled()
  })
})
