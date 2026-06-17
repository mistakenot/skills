import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { ExpenseList } from '../components/ExpenseList'
import { fetchFilteredExpenses } from '../lib/expenses'
import { CATEGORIES } from '../lib/types'

type ExpensesSearch = {
  category?: string
}

export const Route = createFileRoute('/expenses/')({
  component: ExpensesPage,
  validateSearch: (search: Record<string, unknown>): ExpensesSearch => ({
    category:
      typeof search.category === 'string' ? search.category : undefined,
  }),
  loaderDeps: ({ search }) => ({ category: search.category }),
  loader: async ({ deps: { category } }) => {
    return fetchFilteredExpenses({ data: category })
  },
})

function ExpensesPage() {
  const expenses = Route.useLoaderData()
  const { category } = Route.useSearch()
  const navigate = useNavigate()

  return (
    <div>
      <h2>Expenses</h2>
      <div className="filter-bar">
        <label>
          Filter by category:{' '}
          <select
            value={category ?? ''}
            onChange={(e) =>
              navigate({
                to: '/expenses',
                search: { category: e.target.value || undefined },
              })
            }
          >
            <option value="">All</option>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
      </div>
      <ExpenseList expenses={expenses} />
    </div>
  )
}
