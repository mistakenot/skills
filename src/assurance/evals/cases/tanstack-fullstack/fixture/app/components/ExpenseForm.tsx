import { useState } from 'react'
import { CATEGORIES } from '../lib/types'
import type { CreateExpenseInput, Category } from '../lib/types'

interface ExpenseFormProps {
  initialValues?: Partial<CreateExpenseInput>
  onSubmit: (data: CreateExpenseInput) => void
  submitLabel?: string
}

export function ExpenseForm({
  initialValues,
  onSubmit,
  submitLabel = 'Save',
}: ExpenseFormProps) {
  const [description, setDescription] = useState(
    initialValues?.description ?? '',
  )
  const [amount, setAmount] = useState(
    initialValues?.amount != null
      ? (initialValues.amount / 100).toFixed(2)
      : '',
  )
  const [category, setCategory] = useState<Category>(
    initialValues?.category ?? 'other',
  )
  const [date, setDate] = useState(
    initialValues?.date ?? new Date().toISOString().slice(0, 10),
  )

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onSubmit({
      description,
      amount: Math.round(parseFloat(amount) * 100),
      category,
      date,
    })
  }

  return (
    <form className="expense-form" onSubmit={handleSubmit}>
      <div className="form-field">
        <label htmlFor="description">Description</label>
        <input
          id="description"
          type="text"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          required
        />
      </div>
      <div className="form-field">
        <label htmlFor="amount">Amount (£)</label>
        <input
          id="amount"
          type="number"
          step="0.01"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
          required
        />
      </div>
      <div className="form-field">
        <label htmlFor="category">Category</label>
        <select
          id="category"
          value={category}
          onChange={(e) => setCategory(e.target.value as Category)}
        >
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
      </div>
      <div className="form-field">
        <label htmlFor="date">Date</label>
        <input
          id="date"
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          required
        />
      </div>
      <button type="submit">{submitLabel}</button>
    </form>
  )
}
