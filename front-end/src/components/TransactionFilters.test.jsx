import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { EMPTY_FILTERS } from '../lib/transactionFilters'
import { setLocale } from '../lib/locale'
import { renderApp } from '../test/helpers'
import TransactionFilters from './TransactionFilters'

const renderFilters = () => renderApp(<TransactionFilters filters={EMPTY_FILTERS} onChange={() => {}} categories={[]} />)

describe('the amount fields of the filters', () => {
  it('show an empty amount the way the family writes it: with a comma in Portuguese', () => {
    renderFilters()

    expect(screen.getAllByPlaceholderText('0,00')).toHaveLength(2)
  })

  it('and with a dot in English', () => {
    setLocale({ language: 'en' })

    renderFilters()

    expect(screen.getAllByPlaceholderText('0.00')).toHaveLength(2)
  })
})
