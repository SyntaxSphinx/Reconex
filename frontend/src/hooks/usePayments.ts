import { useEffect, useState } from 'react'
import { paymentRepository } from '../data/payments/paymentRepository'
import type { Payment } from '../types/payment'
import { useWorkspaceRefresh } from './useWorkspaceRefresh'

export function usePaymentList() {
  const { tick } = useWorkspaceRefresh()
  const [items, setItems] = useState<Payment[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    paymentRepository
      .list()
      .then((nextItems) => {
        if (!cancelled) setItems(nextItems)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Unable to load payments')
      })

    return () => {
      cancelled = true
    }
  }, [tick])

  return { items, error }
}

type PaymentQuery = {
  paymentId: string
  payment: Payment | null
  error: string | null
}

export function usePayment(paymentId: string | undefined) {
  const { tick } = useWorkspaceRefresh()
  const [query, setQuery] = useState<PaymentQuery | null>(null)

  useEffect(() => {
    if (!paymentId) return

    let cancelled = false

    paymentRepository
      .getById(paymentId)
      .then((result) => {
        if (!cancelled) {
          setQuery({ paymentId, payment: result, error: null })
        }
      })
      .catch((err: unknown) => {
        if (cancelled) return
        setQuery({
          paymentId,
          payment: null,
          error: err instanceof Error ? err.message : 'Unable to load payment',
        })
      })

    return () => {
      cancelled = true
    }
  }, [paymentId, tick])

  if (!paymentId) {
    return { payment: null, error: null }
  }

  if (query?.paymentId !== paymentId) {
    return { payment: undefined, error: null }
  }

  return { payment: query.payment, error: query.error }
}
