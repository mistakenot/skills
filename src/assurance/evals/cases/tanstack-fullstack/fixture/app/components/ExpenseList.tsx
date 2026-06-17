import { Link } from '@tanstack/react-router'
import type { Expense } from '../lib/types'

export function ExpenseList({ expenses }: { expenses: Expense[] }) {
  if (expenses.length === 0) {
    return <p className="empty-state">No expenses found.</p>
  }

  return (
    <table className="expense-table">
      <thead>
        <tr>
          <th>Date</th>
          <th>Description</th>
          <th>Category</th>
          <th>Amount</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {expenses.map((expense) => (
          <tr key={expense.id}>
            <td>{expense.date}</td>
            <td>{expense.description}</td>
            <td>{expense.category}</td>
            <td>£{(expense.amount / 100).toFixed(2)}</td>
            <td>
              <Link to="/expenses/$id" params={{ id: expense.id }}>
                View
              </Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
