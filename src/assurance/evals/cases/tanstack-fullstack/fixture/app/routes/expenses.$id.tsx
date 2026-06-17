import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { ExpenseForm } from '../components/ExpenseForm'
import {
  fetchExpense,
  updateExpenseFn,
  deleteExpenseFn,
} from '../lib/expenses'
import type { CreateExpenseInput } from '../lib/types'

export const Route = createFileRoute('/expenses/$id')({
  component: ExpenseDetail,
  loader: async ({ params: { id } }) => {
    return fetchExpense({ data: id })
  },
})

function ExpenseDetail() {
  const expense = Route.useLoaderData()
  const navigate = useNavigate()

  async function handleUpdate(data: CreateExpenseInput) {
    await updateExpenseFn({ data: { id: expense.id, ...data } })
    navigate({ to: '/expenses' })
  }

  async function handleDelete() {
    await deleteExpenseFn({ data: expense.id })
    navigate({ to: '/expenses' })
  }

  return (
    <div>
      <h2>Edit Expense</h2>
      <ExpenseForm
        initialValues={{
          description: expense.description,
          amount: expense.amount,
          category: expense.category,
          date: expense.date,
        }}
        onSubmit={handleUpdate}
        submitLabel="Update"
      />
      <button className="delete-btn" onClick={handleDelete}>
        Delete
      </button>
    </div>
  )
}
