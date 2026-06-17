export type Category = 'food' | 'transport' | 'housing' | 'entertainment' | 'other'

export const CATEGORIES: Category[] = [
  'food',
  'transport',
  'housing',
  'entertainment',
  'other',
]

export interface Expense {
  id: string
  description: string
  amount: number
  category: Category
  date: string
  createdAt: string
}

export interface CreateExpenseInput {
  description: string
  amount: number
  category: Category
  date: string
}

export interface MonthlySummary {
  total: number
  average: number
  count: number
}

export interface CategoryBreakdown {
  category: Category
  total: number
  count: number
}
