import { useState, useCallback } from 'react'
import type { GuestCountermeasure } from '../types'

export function useGuestCountermeasures() {
  const [countermeasures, setCountermeasures] = useState<GuestCountermeasure[]>([])

  const addCountermeasure = useCallback(
    (
      threatId: string,
      name: string,
      description: string,
      controlFunction: GuestCountermeasure['controlFunction'],
      controlNature: GuestCountermeasure['controlNature']
    ) => {
      const newCountermeasure: GuestCountermeasure = {
        id: crypto.randomUUID(),
        threatId,
        name,
        description,
        controlFunction,
        controlNature,
        createdAt: new Date().toISOString(),
      }
      setCountermeasures((prev) => [...prev, newCountermeasure])
    },
    []
  )

  const updateCountermeasure = useCallback(
    (
      countermeasureId: string,
      updates: Partial<Pick<GuestCountermeasure, 'name' | 'description' | 'controlFunction' | 'controlNature'>>
    ) => {
      setCountermeasures((prev) =>
        prev.map((c) => (c.id === countermeasureId ? { ...c, ...updates } : c))
      )
    },
    []
  )

  const removeCountermeasure = useCallback((countermeasureId: string) => {
    setCountermeasures((prev) => prev.filter((c) => c.id !== countermeasureId))
  }, [])

  const removeCountermeasuresForThreat = useCallback((threatId: string) => {
    setCountermeasures((prev) => prev.filter((c) => c.threatId !== threatId))
  }, [])

  const getCountermeasuresForThreat = useCallback(
    (threatId: string) => countermeasures.filter((c) => c.threatId === threatId),
    [countermeasures]
  )

  const getCountermeasureCount = useCallback(
    (threatId: string) => countermeasures.filter((c) => c.threatId === threatId).length,
    [countermeasures]
  )

  const getAllCountermeasures = useCallback(() => countermeasures, [countermeasures])

  const loadCountermeasures = useCallback((newCountermeasures: GuestCountermeasure[]) => {
    setCountermeasures(newCountermeasures)
  }, [])

  return {
    addCountermeasure,
    updateCountermeasure,
    removeCountermeasure,
    removeCountermeasuresForThreat,
    getCountermeasuresForThreat,
    getCountermeasureCount,
    getAllCountermeasures,
    loadCountermeasures,
  }
}
