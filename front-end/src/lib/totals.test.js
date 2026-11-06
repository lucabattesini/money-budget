import { describe, expect, it } from 'vitest'
import { leftOutByDefault } from './totals'

describe('what starts out left out of the totals', () => {
  const category = (name, group_name) => ({ id: name, name, group_name })

  it('is a transfer or a card payment, with or without the emoji', () => {
    expect(leftOutByDefault(category('🔄 Transferência', 'Transferências'))).toBe(true)
    expect(leftOutByDefault(category('Pagamento de fatura do cartão', 'Transferências'))).toBe(true)
  })

  it('is not a balance adjustment, a purchase, or the same words in another group', () => {
    expect(leftOutByDefault(category('🧮 Ajustes de saldo', 'Transferências'))).toBe(false)
    expect(leftOutByDefault(category('🛒 Supermercado', 'Alimentação'))).toBe(false)
    expect(leftOutByDefault(category('Transferência', 'Outros'))).toBe(false)
  })

  it('is nothing for a category that is not known', () => {
    expect(leftOutByDefault(undefined)).toBe(false)
  })
})
