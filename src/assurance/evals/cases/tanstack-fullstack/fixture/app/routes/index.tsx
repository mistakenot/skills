import { createFileRoute } from '@tanstack/react-router'
import { ExpenseSummary } from '../components/ExpenseSummary'
import { fetchMonthlySummary, fetchCategoryBreakdown } from '../lib/expenses'

export const Route = createFileRoute('/')({
  component: Dashboard,
  loader: async () => {
    const now = new Date()
    const [monthly, breakdown] = await Promise.all([
      fetchMonthlySummary({
        data: { year: now.getFullYear(), month: now.getMonth() + 1 },
      }),
      fetchCategoryBreakdown(),
    ])
    return { monthly, breakdown }
  },
})

function Dashboard() {
  const { monthly, breakdown } = Route.useLoaderData()
  return (
    <div>
      <h2>Dashboard</h2>
      <ExpenseSummary monthly={monthly} breakdown={breakdown} />
    </div>
  )
}
