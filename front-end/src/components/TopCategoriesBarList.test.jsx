import { screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderApp } from '../test/helpers'
import TopCategoriesBarList from './TopCategoriesBarList'

const categories = [1, 2, 3, 4, 5, 6, 7].map((id) => ({ id, name: `Categoria ${id}` }))
const tx = (category_id, cents) => ({ category_id, value: cents })

describe('TopCategoriesBarList', () => {
  it('lists the categories with the highest spending first', () => {
    renderApp(<TopCategoriesBarList categories={categories} transactions={[tx(1, 1000), tx(2, 5000), tx(3, 3000)]} />)

    const text = document.body.textContent
    const order = ['Categoria 2', 'Categoria 3', 'Categoria 1'].map((name) => text.indexOf(name))
    expect(order.every((i) => i >= 0)).toBe(true)
    expect(order).toEqual([...order].sort((a, b) => a - b))
  })

  it('adds up several transactions of the same category', () => {
    renderApp(<TopCategoriesBarList categories={categories} transactions={[tx(1, 1000), tx(1, 2000), tx(2, 2500)]} />)

    // 1 + 2 = 30,00 beats 25,00, even though no single transaction does
    const text = document.body.textContent
    expect(text.indexOf('Categoria 1')).toBeLessThan(text.indexOf('Categoria 2'))
  })

  it('shows only the top 5', () => {
    const transactions = [1, 2, 3, 4, 5, 6, 7].map((id) => tx(id, id * 1000))

    renderApp(<TopCategoriesBarList categories={categories} transactions={transactions} />)

    for (const id of [3, 4, 5, 6, 7]) expect(screen.getByText(`Categoria ${id}`)).toBeInTheDocument()
    expect(screen.queryByText('Categoria 1')).not.toBeInTheDocument()
    expect(screen.queryByText('Categoria 2')).not.toBeInTheDocument()
  })

  it('calls a category that no longer exists "Desconhecido"', () => {
    renderApp(<TopCategoriesBarList categories={categories} transactions={[tx(99, 1000)]} />)

    expect(screen.getByText('Desconhecido')).toBeInTheDocument()
  })

  it('says so when nothing was spent', () => {
    renderApp(<TopCategoriesBarList categories={categories} transactions={[]} />)

    expect(screen.getByText('Nenhum gasto registrado.')).toBeInTheDocument()
    expect(screen.queryByText('Categoria 1')).not.toBeInTheDocument()
  })
})
