import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { renderApp } from '../test/helpers'
import { DateFilter } from './dateFilter'

describe('DateFilter', () => {
  it.each([
    ['Hoje', 'day'],
    ['Este Mês', 'month'],
  ])('tells the page which period "%s" means', async (label, period) => {
    const onChange = vi.fn()
    renderApp(<DateFilter filterChange={onChange} />)

    await userEvent.click(screen.getByRole('tab', { name: label }))

    expect(onChange).toHaveBeenLastCalledWith(period)
  })

  it('clears the filter with "Tudo"', async () => {
    const onChange = vi.fn()
    renderApp(<DateFilter filterChange={onChange} />)
    await userEvent.click(screen.getByRole('tab', { name: 'Hoje' }))

    await userEvent.click(screen.getByRole('tab', { name: 'Tudo' }))

    expect(onChange).toHaveBeenLastCalledWith(null)
  })

  it('starts on "Tudo"', () => {
    renderApp(<DateFilter filterChange={() => {}} />)

    expect(screen.getByRole('tab', { name: 'Tudo' })).toHaveAttribute('aria-selected', 'true')
  })
})
