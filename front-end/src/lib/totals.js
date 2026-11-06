// What is left out of the totals (TKT-87). A transaction can be marked "fora dos totais": it stays in the list but is not
// counted in the dashboard, the budgets or the assistant's answers.
import { plainName } from './categoryName'

// A transfer between the person's own accounts and the payment of a card bill are not spending, so a new one starts out
// left out. This mirrors the server (back-end/api/utils/totals.py), which applies it when nothing is said.
const UNCOUNTED_GROUP = 'Transferências'
const UNCOUNTED_CATEGORIES = ['transferência', 'pagamento de fatura do cartão']

/** True if a new transaction in this category starts out left out of the totals. */
export function leftOutByDefault(category) {
  if (!category || category.group_name !== UNCOUNTED_GROUP) return false
  return UNCOUNTED_CATEGORIES.includes(plainName(category.name).toLowerCase())
}
