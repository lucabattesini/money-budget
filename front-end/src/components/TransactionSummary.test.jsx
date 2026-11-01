import { screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderApp } from '../test/helpers'
import TransactionSummary from './TransactionSummary'

// Sunday 15 March 2026, noon. "Last 7 days" starts Sunday 8 March 00:00; the month starts 1 March.
const tx = (date, cents) => ({ id: Math.random(), date, value: cents, label: 'x' })

const totals = () => {
  const read = (label) => screen.getByText(label).nextElementSibling.textContent.replace(/\s/g, ' ')
  return { today: read('Hoje'), week: read('Últimos 7 dias'), month: read('Este Mês') }
}

describe('TransactionSummary', () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] })
    vi.setSystemTime(new Date(2026, 2, 15, 12, 0, 0))
  })

  it('shows zero everywhere without transactions', () => {
    renderApp(<TransactionSummary transactions={[]} />)

    expect(totals()).toEqual({ today: 'R$ 0,00', week: 'R$ 0,00', month: 'R$ 0,00' })
  })

  it('sums the amounts (cents to reais) for today, the last 7 days and this month', () => {
    renderApp(
      <TransactionSummary
        transactions={[
          tx('2026-03-15T09:00:00', 1000), // today
          tx('2026-03-10T09:00:00', 2000), // this week
          tx('2026-03-02T09:00:00', 3000), // this month
          tx('2026-02-20T09:00:00', 4000), // older: counts nowhere
        ]}
      />,
    )

    expect(totals()).toEqual({ today: 'R$ 10,00', week: 'R$ 30,00', month: 'R$ 60,00' })
  })

  it('counts a transaction at midnight on the first day of the window, but not the minute before', () => {
    renderApp(
      <TransactionSummary
        transactions={[tx('2026-03-08T00:00:00', 100), tx('2026-03-07T23:59:00', 5000)]}
      />,
    )

    expect(totals().week).toBe('R$ 1,00')
  })

  it('uses Brazilian formatting for thousands and cents', () => {
    renderApp(<TransactionSummary transactions={[tx('2026-03-15T09:00:00', 123456)]} />)

    expect(totals().today).toBe('R$ 1.234,56')
  })

  it('counts a transaction from midnight today, but not from the minute before', () => {
    renderApp(<TransactionSummary transactions={[tx('2026-03-15T00:00:00', 100), tx('2026-03-14T23:59:00', 5000)]} />)

    expect(totals().today).toBe('R$ 1,00')
  })

  it('counts a transaction from midnight on the first of the month, but not from the minute before', () => {
    vi.setSystemTime(new Date(2026, 2, 20, 12, 0, 0)) // far enough from 1 March that the 7-day window does not interfere
    renderApp(<TransactionSummary transactions={[tx('2026-03-01T00:00:00', 100), tx('2026-02-28T23:59:00', 5000)]} />)

    expect(totals().month).toBe('R$ 1,00')
  })

  it('on a Wednesday early in the month, the last 7 days still reach into the previous month', () => {
    vi.setSystemTime(new Date(2026, 2, 4, 12, 0, 0)) // Wednesday 4 March: the window starts 25 February
    renderApp(
      <TransactionSummary
        transactions={[tx('2026-03-04T09:00:00', 100), tx('2026-02-27T10:00:00', 200), tx('2026-02-24T23:59:00', 400)]}
      />,
    )

    expect(totals()).toEqual({ today: 'R$ 1,00', week: 'R$ 3,00', month: 'R$ 1,00' })
  })

  it('handles the turn of the year', () => {
    vi.setSystemTime(new Date(2026, 0, 2, 12, 0, 0)) // Friday 2 January
    renderApp(<TransactionSummary transactions={[tx('2025-12-30T10:00:00', 700), tx('2026-01-02T08:00:00', 300)]} />)

    expect(totals()).toEqual({ today: 'R$ 3,00', week: 'R$ 10,00', month: 'R$ 3,00' })
  })
})
