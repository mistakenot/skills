import type { CategoryBreakdown, MonthlySummary } from '../lib/types'

interface ExpenseSummaryProps {
  monthly: MonthlySummary
  breakdown: CategoryBreakdown[]
}

export function ExpenseSummary({ monthly, breakdown }: ExpenseSummaryProps) {
  return (
    <div className="summary">
      <div className="summary-card">
        <h3>This Month</h3>
        <dl>
          <dt>Total</dt>
          <dd>£{(monthly.total / 100).toFixed(2)}</dd>
          <dt>Average per expense</dt>
          <dd>£{(monthly.average / 100).toFixed(2)}</dd>
          <dt>Count</dt>
          <dd>{monthly.count}</dd>
        </dl>
      </div>
      <div className="summary-card">
        <h3>By Category</h3>
        <ul>
          {breakdown
            .filter((b) => b.count > 0)
            .map((b) => (
              <li key={b.category}>
                <strong>{b.category}</strong>: £
                {(b.total / 100).toFixed(2)} ({b.count})
              </li>
            ))}
        </ul>
      </div>
    </div>
  )
}
