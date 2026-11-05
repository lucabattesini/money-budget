import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { act, useState } from 'react'
import { describe, expect, it } from 'vitest'
import { setLocale } from '../lib/locale'
import { maskAmount } from '../lib/money'
import { renderApp } from '../test/helpers'
import AmountInput from './AmountInput'

function Field() {
  const [value, setValue] = useState('')
  return <AmountInput label="Valor" value={value} onChange={(e) => setValue(maskAmount(e.target.value))} />
}

describe('amount input', () => {
  it('shows the family\'s currency symbol next to the number and keeps the typed text free of it', async () => {
    setLocale({ currency: 'USD', language: 'en' })
    renderApp(<Field />)

    await userEvent.type(screen.getByRole('textbox'), '2550')

    expect(screen.getByText('US$')).toBeInTheDocument()
    expect(screen.getByRole('textbox')).toHaveValue('25.50')
  })

  it('has a name that says the currency, and asks for the numeric keyboard', () => {
    renderApp(<Field />)

    const input = screen.getByRole('textbox', { name: 'Valor em reais (R$)' })
    expect(input).toHaveAttribute('inputmode', 'numeric')
  })

  it('changes at once when the currency changes', () => {
    renderApp(<Field />)
    expect(screen.getByText('R$')).toBeInTheDocument()

    act(() => setLocale({ currency: 'EUR' }))

    expect(screen.queryByText('R$')).not.toBeInTheDocument()
    expect(screen.getByText('€')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Valor em euros (€)' })).toBeInTheDocument()
  })

  it('still deletes digit by digit', async () => {
    renderApp(<Field />)
    const input = screen.getByRole('textbox')

    await userEvent.type(input, '1234')
    expect(input).toHaveValue('12,34')
    await userEvent.type(input, '{Backspace}')

    expect(input).toHaveValue('1,23')
  })
})
