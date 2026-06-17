import { createServerFn } from '@tanstack/start'
import type { CreateExpenseInput } from './types'
import {
  getAllExpenses,
  getExpenseById,
  addExpense,
  updateExpense,
  deleteExpense,
  getMonthlySummary,
  getCategoryBreakdown,
  getFilteredExpenses,
} from './store'

export const fetchExpenses = createServerFn()
  .handler(async () => {
    return getAllExpenses()
  })

export const fetchExpense = createServerFn()
  .validator((id: string) => id)
  .handler(async ({ data: id }) => {
    const expense = getExpenseById(id)
    if (!expense) throw new Error(`Expense ${id} not found`)
    return expense
  })

export const createExpenseFn = createServerFn()
  .validator((input: CreateExpenseInput) => input)
  .handler(async ({ data }) => {
    return addExpense(data)
  })

export const updateExpenseFn = createServerFn()
  .validator((input: { id: string } & Partial<CreateExpenseInput>) => input)
  .handler(async ({ data: { id, ...updates } }) => {
    const result = updateExpense(id, updates)
    if (!result) throw new Error(`Expense ${id} not found`)
    return result
  })

export const deleteExpenseFn = createServerFn()
  .validator((id: string) => id)
  .handler(async ({ data: id }) => {
    const deleted = deleteExpense(id)
    if (!deleted) throw new Error(`Expense ${id} not found`)
    return { success: true }
  })

export const fetchMonthlySummary = createServerFn()
  .validator((input: { year: number; month: number }) => input)
  .handler(async ({ data: { year, month } }) => {
    return getMonthlySummary(year, month)
  })

export const fetchCategoryBreakdown = createServerFn()
  .handler(async () => {
    return getCategoryBreakdown()
  })

export const fetchFilteredExpenses = createServerFn()
  .validator((category: string | undefined) => category)
  .handler(async ({ data: category }) => {
    return getFilteredExpenses(category)
  })
