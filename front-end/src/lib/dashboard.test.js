import { describe, expect, it } from 'vitest'
import { countsAsSpending, isSpending, latestSpending, spendingByDay, spendingOfMonth } from './dashboard'

const tx = (date, value, type = 'debit', id = Math.random()) => ({ id, transactioned_at: `${date}T10:00:00`, value, type })

describe('isSpending', () => {
  it('counts debits and transactions with no type, not credits', () => {
    expect(isSpending({ type: 'debit' })).toBe(true)
    expect(isSpending({})).toBe(true)
    expect(isSpending({ type: 'credit' })).toBe(false)
  })
})

describe('countsAsSpending', () => {
  const categories = [
    { id: 1, group_name: 'Alimentação' },
    { id: 2, group_name: 'Transferências' },
    { id: 3, group_name: 'Receitas' },
    { id: 4, group_name: 'Outros' },
  ]
  const at = (category_id, type = 'debit') => ({ ...tx('2026-03-10', 100, type), category_id })

  it('keeps the debits of ordinary categories', () => {
    const food = at(1)
    const other = at(4)

    expect(countsAsSpending([food, other], categories)).toEqual([food, other])
  })

  it('leaves out transfers between accounts, such as paying the card bill, even though they are debits', () => {
    expect(countsAsSpending([at(2)], categories)).toEqual([])
  })

  it('leaves out the income group even when a row there is a debit', () => {
    expect(countsAsSpending([at(3)], categories)).toEqual([])
  })

  it('leaves out credits, in any category', () => {
    expect(countsAsSpending([at(1, 'credit'), at(2, 'credit'), at(4, 'credit')], categories)).toEqual([])
  })

  it('still counts a debit whose category is unknown or has no group', () => {
    const lost = at(99)

    expect(countsAsSpending([lost], categories)).toEqual([lost])
    expect(countsAsSpending([lost], [{ id: 99 }])).toEqual([lost])
  })

  it('does not change the list it is given', () => {
    const list = [at(1), at(2)]

    countsAsSpending(list, categories)

    expect(list).toHaveLength(2)
  })
})

describe('spendingOfMonth', () => {
  it('keeps the spending of that month only, not another month, another year or a credit', () => {
    const march = [tx('2026-03-01', 1), tx('2026-03-31', 2)]
    const others = [tx('2026-02-28', 4), tx('2026-04-01', 8), tx('2025-03-15', 16), tx('2026-03-10', 32, 'credit')]

    expect(spendingOfMonth([...others, ...march], '2026-03')).toEqual(march)
  })
})

describe('spendingByDay', () => {
  const now = new Date(2026, 2, 15, 12) // 15 March

  it('adds the spending up day by day and stops at today in the current month', () => {
    const { days, spent, upToDay } = spendingByDay([tx('2026-03-02', 100), tx('2026-03-02', 50), tx('2026-03-10', 25)], '2026-03', now)

    expect(days).toHaveLength(31)
    expect(days[0].current).toBe(0)
    expect(days[1].current).toBe(150)
    expect(days[9].current).toBe(175)
    expect(days[14].current).toBe(175) // today
    expect(days[15].current).toBeNull() // tomorrow: not yet
    expect(upToDay).toBe(15)
    expect(spent).toBe(175)
  })

  it('draws the whole month once it is over', () => {
    const { days, upToDay, spent } = spendingByDay([tx('2026-02-28', 300)], '2026-02', now)

    expect(days).toHaveLength(28)
    expect(days[27].current).toBe(300)
    expect(upToDay).toBe(28)
    expect(spent).toBe(300)
  })

  it('puts the month before behind it, and nothing past its last day', () => {
    const { days } = spendingByDay([tx('2026-02-10', 400), tx('2026-03-10', 100)], '2026-03', now)

    expect(days[9].previous).toBe(400)
    expect(days[27].previous).toBe(400) // 28 February, its last day
    expect(days[28].previous).toBeNull() // 29 March: February had no such day
  })

  it('compares with the month before up to the same day only', () => {
    const transactions = [tx('2026-03-05', 15000), tx('2026-02-15', 10000), tx('2026-02-16', 90000), tx('2026-02-10', 5000, 'credit')]

    const { change, previousSoFar } = spendingByDay(transactions, '2026-03', now)

    expect(previousSoFar).toBe(10000) // not the 16th, not the credit
    expect(change).toBeCloseTo(0.5)
  })

  it('goes down when the month is cheaper', () => {
    expect(spendingByDay([tx('2026-03-05', 5000), tx('2026-02-05', 10000)], '2026-03', now).change).toBeCloseTo(-0.5)
  })

  it('has nothing to compare with when the month before had no spending by then', () => {
    expect(spendingByDay([tx('2026-03-05', 5000)], '2026-03', now).change).toBeNull()
  })

  it('works across a year boundary', () => {
    const { previousSoFar } = spendingByDay([tx('2025-12-03', 700)], '2026-01', new Date(2026, 0, 20))

    expect(previousSoFar).toBe(700)
  })

  it('handles a month without spending', () => {
    const { spent, days } = spendingByDay([], '2026-03', now)

    expect(spent).toBe(0)
    expect(days.every((d) => d.current === null || d.current === 0)).toBe(true)
  })
})

describe('latestSpending', () => {
  it('puts the newest first, whatever the order they come in, and cuts at the limit', () => {
    const list = [tx('2026-03-02', 1, 'debit', 1), tx('2026-03-09', 1, 'debit', 2), tx('2026-03-05', 1, 'debit', 3)]

    expect(latestSpending(list, 2).map((t) => t.id)).toEqual([2, 3])
  })

  it('does not change the list it was given', () => {
    const list = [tx('2026-03-02', 1, 'debit', 1), tx('2026-03-09', 1, 'debit', 2)]

    latestSpending(list)

    expect(list.map((t) => t.id)).toEqual([1, 2])
  })
})
