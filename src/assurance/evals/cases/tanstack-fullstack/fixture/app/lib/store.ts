import type {
  Expense,
  CreateExpenseInput,
  Category,
  MonthlySummary,
  CategoryBreakdown,
} from './types'
import { CATEGORIES } from './types'

let nextId = 11

const expenses: Expense[] = [
  { id: '1', description: 'Weekly groceries', amount: 8540, category: 'food', date: '2026-01-15', createdAt: '2026-01-15T10:00:00Z' },
  { id: '2', description: 'Train ticket', amount: 3200, category: 'transport', date: '2026-01-20', createdAt: '2026-01-20T08:30:00Z' },
  { id: '3', description: 'Monthly rent', amount: 120000, category: 'housing', date: '2026-02-01', createdAt: '2026-02-01T09:00:00Z' },
  { id: '4', description: 'Cinema tickets', amount: 2400, category: 'entertainment', date: '2026-02-14', createdAt: '2026-02-14T19:00:00Z' },
  { id: '5', description: 'Lunch with team', amount: 1850, category: 'food', date: '2026-02-28', createdAt: '2026-02-28T12:30:00Z' },
  { id: '6', description: 'Bus pass', amount: 6500, category: 'transport', date: '2026-03-01', createdAt: '2026-03-01T07:00:00Z' },
  { id: '7', description: 'Internet bill', amount: 3999, category: 'housing', date: '2026-03-05', createdAt: '2026-03-05T10:00:00Z' },
  { id: '8', description: 'Birthday dinner', amount: 7800, category: 'food', date: '2026-03-15', createdAt: '2026-03-15T20:00:00Z' },
  { id: '9', description: 'Gym membership', amount: 4999, category: 'other', date: '2026-03-20', createdAt: '2026-03-20T11:00:00Z' },
  { id: '10', description: 'Taxi ride', amount: 1500, category: 'transport', date: '2026-03-25', createdAt: '2026-03-25T23:15:00Z' },
]

export function getAllExpenses(): Expense[] {
  return [...expenses].sort((a, b) => b.date.localeCompare(a.date))
}

export function getExpenseById(id: string): Expense | undefined {
  return expenses.find((e) => e.id === id)
}

export function addExpense(input: CreateExpenseInput): Expense {
  const expense: Expense = {
    id: String(nextId++),
    ...input,
    createdAt: new Date().toISOString(),
  }
  expenses.push(expense)
  return expense
}

export function updateExpense(
  id: string,
  input: Partial<CreateExpenseInput>,
): Expense | null {
  const idx = expenses.findIndex((e) => e.id === id)
  if (idx === -1) return null
  expenses[idx] = { ...expenses[idx], ...input }
  return expenses[idx]
}

export function deleteExpense(id: string): boolean {
  const idx = expenses.findIndex((e) => e.id === id)
  if (idx === -1) return false
  expenses.splice(idx, 1)
  return true
}

export function getExpensesByMonth(year: number, month: number): Expense[] {
  const prefix = `${year}-${String(month).padStart(2, '0')}`
  return expenses.filter((e) => e.date.startsWith(prefix))
}

export function getMonthlySummary(
  year: number,
  month: number,
): MonthlySummary {
  const monthExpenses = getExpensesByMonth(year, month)
  const total = monthExpenses.reduce((sum, e) => sum + e.amount, 0)
  const average = total / expenses.length
  return { total, average, count: monthExpenses.length }
}

export function getCategoryBreakdown(): CategoryBreakdown[] {
  return CATEGORIES.map((category) => {
    const matching = expenses.filter((e) => e.category === category)
    return {
      category,
      total: matching.reduce((sum, e) => sum + e.amount, 0),
      count: matching.length,
    }
  })
}

export function getFilteredExpenses(category?: string): Expense[] {
  const all = getAllExpenses()
  if (!category) return all
  return all.filter((e) => e.category === category)
}
