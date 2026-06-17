import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { ExpenseForm } from '../components/ExpenseForm'
import { createExpenseFn } from '../lib/expenses'
import type { CreateExpenseInput } from '../lib/types'

export const Route = createFileRoute('/expenses/new')({
  component: NewExpense,
})

function NewExpense() {
  const navigate = useNavigate()

  async function handleCreate(data: CreateExpenseInput) {
    await createExpenseFn({ data })
    navigate({ to: '/expenses' })
  }

  return (
    <div>
      <h2>Add Expense</h2>
      <ExpenseForm onSubmit={handleCreate} submitLabel="Add Expense" />
    </div>
  )
}
