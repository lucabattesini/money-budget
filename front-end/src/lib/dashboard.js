// Numbers for the dashboard. Money is in cents here; the components turn it into reais to show it.
// A month is written "2026-11", like in the budgets.

/** Money going out. Credits are money coming in and are not spending. */
export const isSpending = (transaction) => transaction.type !== 'credit'

// Money coming in and money moving between accounts (a transfer, paying the card bill) are not spending. These are the
// groups the budget leaves out too (the server's UNBUDGETED_GROUPS), so the budget and the other cards agree.
export const NOT_SPENDING_GROUPS = ['Receitas', 'Transferências']

/**
 * What counts as spending: the debits, except those in a category of an income or transfer group and those the person
 * left out of the totals. A transaction whose category is unknown (deleted) still counts.
 */
export function countsAsSpending(transactions, categories) {
  const groupOf = new Map(categories.map((category) => [category.id, category.group_name]))
  return transactions.filter(
    (t) => !t.excluded && isSpending(t) && !NOT_SPENDING_GROUPS.includes(groupOf.get(t.category_id)),
  )
}

const parts = (key) => {
  const [year, month] = key.split('-').map(Number)
  return { year, month: month - 1 }
}

const daysIn = (year, month) => new Date(year, month + 1, 0).getDate()

const previousKey = (key) => {
  const { year, month } = parts(key)
  const date = new Date(year, month - 1, 1)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

/** The transactions of one month. */
export function transactionsOfMonth(transactions, key) {
  const { year, month } = parts(key)
  return transactions.filter((t) => {
    const date = new Date(t.transactioned_at)
    return date.getFullYear() === year && date.getMonth() === month
  })
}

/** The spending of one month, credits left out. */
export const spendingOfMonth = (transactions, key) => transactionsOfMonth(transactions, key).filter(isSpending)

/**
 * What counts as money that came in: the credits, except those in a transfer between accounts (the other side of a
 * debit that is not spending either). A salary and a refund both count.
 */
export function countsAsIncoming(transactions, categories) {
  const groupOf = new Map(categories.map((category) => [category.id, category.group_name]))
  return transactions.filter((t) => !t.excluded && t.type === 'credit' && groupOf.get(t.category_id) !== 'Transferências')
}

/** The total of the transactions, in cents. */
export const sumCents = (transactions) => transactions.reduce((total, t) => total + t.value, 0)

// What was spent up to each day of the month (index 0 is day 1)
function runningTotal(transactions, key) {
  const { year, month } = parts(key)
  const perDay = Array(daysIn(year, month)).fill(0)
  spendingOfMonth(transactions, key).forEach((t) => {
    perDay[new Date(t.transactioned_at).getDate() - 1] += t.value
  })
  let total = 0
  return perDay.map((cents) => (total += cents))
}

/**
 * The spending of month `key` day by day, with the month before behind it to compare. `now` is today: a month that is
 * not over has no line after today. `upToDay` is the last day compared (today, or the whole month once it is over);
 * `change` is a fraction (0.12 is 12% more than the month before by then), null when nothing was spent by then.
 */
export function spendingByDay(transactions, key, now) {
  const { year, month } = parts(key)
  const length = daysIn(year, month)
  const isCurrent = year === now.getFullYear() && month === now.getMonth()
  const upToDay = isCurrent ? now.getDate() : length

  const current = runningTotal(transactions, key)
  const before = runningTotal(transactions, previousKey(key))
  const days = current.map((total, index) => ({
    day: index + 1,
    current: index < upToDay ? total : null,
    previous: index < before.length ? before[index] : null,
  }))

  const spent = current[length - 1]
  const spentSoFar = current[upToDay - 1]
  const previousSoFar = before[Math.min(upToDay, before.length) - 1]
  return {
    days,
    spent,
    upToDay,
    previousSoFar,
    change: previousSoFar > 0 ? (spentSoFar - previousSoFar) / previousSoFar : null,
  }
}

/** The latest spending first, at most `limit` of it. Ties keep the order the server gave (ids are UUIDs: they have no order). */
export function latestSpending(transactions, limit = 6) {
  return [...transactions]
    .sort((a, b) => new Date(b.transactioned_at) - new Date(a.transactioned_at))
    .slice(0, limit)
}
