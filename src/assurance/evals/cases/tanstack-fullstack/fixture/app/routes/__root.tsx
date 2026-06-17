import { createRootRoute, Link, Outlet } from '@tanstack/react-router'
import '../styles/app.css'

export const Route = createRootRoute({
  component: RootLayout,
})

function RootLayout() {
  return (
    <>
      <header className="app-header">
        <h1>Expense Tracker</h1>
        <nav>
          <Link to="/" activeProps={{ className: 'active' }}>
            Dashboard
          </Link>
          <Link to="/expenses" activeProps={{ className: 'active' }}>
            Expenses
          </Link>
          <Link to="/expenses/new" activeProps={{ className: 'active' }}>
            Add Expense
          </Link>
        </nav>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </>
  )
}
