/**
 * Undo History Hook
 *
 * A modular hook for managing undo functionality in the DFD editor.
 * Can be easily removed by:
 * 1. Deleting this file
 * 2. Removing the import and usage from useDiagramState.ts
 * 3. Removing the undo keyboard shortcut from useKeyboardShortcuts.ts
 */

import { useCallback, useRef } from 'react'
import type { DiagramNode, DiagramEdge } from '../types'

interface HistoryState {
  nodes: DiagramNode[]
  edges: DiagramEdge[]
}

interface UseUndoHistoryOptions {
  maxHistorySize?: number
}

interface UseUndoHistoryReturn {
  /** Push current state to history (call before making changes) */
  pushToHistory: (state: HistoryState) => void
  /** Undo to previous state, returns the state to restore or null if no history */
  undo: (currentState: HistoryState) => HistoryState | null
  /** Redo the last undone state, returning the state to restore or null. */
  redo: (currentState: HistoryState) => HistoryState | null
  /** Check if undo is available */
  canUndo: () => boolean
  canRedo: () => boolean
  /** Clear all history */
  clearHistory: () => void
}

export function useUndoHistory({
  maxHistorySize = 30,
}: UseUndoHistoryOptions = {}): UseUndoHistoryReturn {
  const historyRef = useRef<HistoryState[]>([])
  const redoRef = useRef<HistoryState[]>([])

  const cloneState = (state: HistoryState): HistoryState => ({
    nodes: JSON.parse(JSON.stringify(state.nodes)),
    edges: JSON.parse(JSON.stringify(state.edges)),
  })

  const pushToHistory = useCallback(
    (state: HistoryState) => {
      // Deep clone to avoid reference issues
      historyRef.current.push(cloneState(state))
      // A new edit starts a new branch of history.
      redoRef.current = []

      // Cap history size
      if (historyRef.current.length > maxHistorySize) {
        historyRef.current.shift()
      }
    },
    [maxHistorySize]
  )

  const undo = useCallback((currentState: HistoryState): HistoryState | null => {
    if (historyRef.current.length === 0) {
      return null
    }

    redoRef.current.push(cloneState(currentState))
    const previousState = historyRef.current.pop()
    return previousState || null
  }, [])

  const redo = useCallback((currentState: HistoryState): HistoryState | null => {
    if (redoRef.current.length === 0) return null
    historyRef.current.push(cloneState(currentState))
    return redoRef.current.pop() || null
  }, [])

  const canUndo = useCallback(() => {
    return historyRef.current.length > 0
  }, [])

  const canRedo = useCallback(() => {
    return redoRef.current.length > 0
  }, [])

  const clearHistory = useCallback(() => {
    historyRef.current = []
    redoRef.current = []
  }, [])

  return {
    pushToHistory,
    undo,
    redo,
    canUndo,
    canRedo,
    clearHistory,
  }
}
