import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { EMPTY_FILTERS } from '../lib/transactionFilters'
import { setLocale } from '../lib/locale'
import { renderApp } from '../test/helpers'
import TransactionFilters from './TransactionFilters'

const renderFilters = () => renderApp(<TransactionFilters filters={EMPTY_FILTERS} onChange={() => {}} categories={[]} />)

describe('the filter on the totals', () => {
  it('offers every transaction, only those that count, or only those left out, and reports the choice', async () => {
    const onChange = vi.fn()
    renderApp(<TransactionFilters filters={EMPTY_FILTERS} onChange={onChange} categories={[]} />)
    const select = screen.getByLabelText('Totais')

    expect([...select.options].map((o) => [o.value, o.textContent])).toEqual([
      ['', 'Todas'],
      ['counted', 'Só as que contam'],
      ['left_out', 'Só as fora dos totais'],
    ])
    await userEvent.selectOptions(select, 'left_out')

    expect(onChange).toHaveBeenCalledWith({ ...EMPTY_FILTERS, counting: 'left_out' })
  })
})

describe('the amount fields of the filters', () => {
  it('show an empty amount the way the family writes it: with a comma in Portuguese', () => {
    renderFilters()

    expect(screen.getAllByPlaceholderText('0,00')).toHaveLength(2)
  })

  it('show the currency of the family in front of the number, and name it for a screen reader', () => {
    setLocale({ currency: 'USD', language: 'en' })

    renderFilters()

    expect(screen.getAllByText('US$')).toHaveLength(2)
    expect(screen.getByRole('textbox', { name: 'Valor mínimo em dólares (US$)' })).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Valor máximo em dólares (US$)' })).toBeInTheDocument()
  })

  it('and with a dot in English', () => {
    setLocale({ language: 'en' })

    renderFilters()

    expect(screen.getAllByPlaceholderText('0.00')).toHaveLength(2)
  })
})
