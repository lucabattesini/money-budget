import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { setLocale } from '../lib/locale'
import { renderApp } from '../test/helpers'
import CashFlowCard from './CashFlowCard'

const plain = (label) => screen.getByLabelText(label).textContent.replace(/\s/g, ' ')

describe('CashFlowCard', () => {
  it('shows what came in, what went out and what was left', () => {
    renderApp(<CashFlowCard entered={500000} spent={123456} month="2026-03" />)

    expect(screen.getByRole('heading', { name: 'Entradas e saídas' })).toBeInTheDocument()
    expect(plain('Entradas do mês')).toBe('R$ 5.000,00')
    expect(plain('Saídas do mês')).toBe('R$ 1.234,56')
    expect(plain('Saldo do mês')).toBe('R$ 3.765,44')
    expect(screen.getByText('sobrou')).toBeInTheDocument()
  })

  it('shows a negative balance with a minus sign and says it fell short', () => {
    renderApp(<CashFlowCard entered={10000} spent={25050} month="2026-03" />)

    expect(plain('Saldo do mês')).toBe('−R$ 150,50')
    expect(screen.getByText('faltou')).toBeInTheDocument()
  })

  it('has a zero balance when the same came in and went out', () => {
    renderApp(<CashFlowCard entered={4000} spent={4000} month="2026-03" />)

    expect(plain('Saldo do mês')).toBe('R$ 0,00')
    expect(screen.getByText('sobrou')).toBeInTheDocument()
  })

  it('says so when nothing came in or went out', () => {
    renderApp(<CashFlowCard entered={0} spent={0} month="2026-03" />)

    expect(plain('Entradas do mês')).toBe('R$ 0,00')
    expect(plain('Saídas do mês')).toBe('R$ 0,00')
    expect(screen.getByText('Nenhuma entrada ou saída neste mês.')).toBeInTheDocument()
  })

  it('writes the amounts in the currency and language of the family', () => {
    setLocale({ currency: 'USD', language: 'en' })

    renderApp(<CashFlowCard entered={123456} spent={0} month="2026-03" />)

    expect(plain('Entradas do mês')).toBe('US$1,234.56')
  })

  describe('the bar', () => {
    const bar = () => ({
      spent: document.querySelector('[data-part="spent"]').style.width,
      left: document.querySelector('[data-part="left"]'),
    })

    it('is red as far as what went out is of what came in, and green for the rest', () => {
      renderApp(<CashFlowCard entered={400000} spent={100000} month="2026-03" />)

      expect(bar().spent).toBe('25%')
      expect(bar().left).not.toBeNull()
    })

    it('is all red, with nothing green, when more went out than came in', () => {
      renderApp(<CashFlowCard entered={10000} spent={25050} month="2026-03" />)

      expect(bar().spent).toBe('100%')
      expect(bar().left).toBeNull()
    })

    it('is all red when money went out and nothing came in', () => {
      renderApp(<CashFlowCard entered={0} spent={5000} month="2026-03" />)

      expect(bar().spent).toBe('100%')
      expect(bar().left).toBeNull()
    })

    it('is all green when money came in and nothing went out', () => {
      renderApp(<CashFlowCard entered={5000} spent={0} month="2026-03" />)

      expect(bar().spent).toBe('0%')
      expect(bar().left).not.toBeNull()
    })

    it('has nothing in it, and no green, when the same came in and went out', () => {
      renderApp(<CashFlowCard entered={4000} spent={4000} month="2026-03" />)

      expect(bar().spent).toBe('100%')
      expect(bar().left).toBeNull()
    })

    it('is empty when nothing came in or went out', () => {
      renderApp(<CashFlowCard entered={0} spent={0} month="2026-03" />)

      expect(bar().spent).toBe('0%')
      expect(bar().left).toBeNull()
    })
  })
})
