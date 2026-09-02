import { useCallback, useEffect, useRef, useState } from 'react'
import { applyNodeChanges, applyEdgeChanges } from '@xyflow/react'
import type { NodeChange, EdgeChange } from '@xyflow/react'
import type { DiagramNode, DiagramEdge } from '@/features/dfd-editor/types'
import type { DFDNotationStyle } from '@/features/dfd-editor/types/notation'
import { useUndoHistory } from '@/features/dfd-editor/hooks/useUndoHistory'

interface LoadFromFileData {
  title: string
  nodes: DiagramNode[]
  edges: DiagramEdge[]
  notationStyle?: DFDNotationStyle
}

interface UseGuestDiagramStateReturn {
  title: string
  setTitle: (title: string) => void
  nodes: DiagramNode[]
  edges: DiagramEdge[]
  setNodes: React.Dispatch<React.SetStateAction<DiagramNode[]>>
  setEdges: React.Dispatch<React.SetStateAction<DiagramEdge[]>>
  onNodesChange: (changes: NodeChange<DiagramNode>[]) => void
  onEdgesChange: (changes: EdgeChange<DiagramEdge>[]) => void
  undo: () => void
  redo: () => void
  canUndo: boolean
  canRedo: boolean
  hasUnsavedChanges: boolean
  markSaved: () => void
  loadFromFile: (data: LoadFromFileData) => void
}

export function useGuestDiagramState(): UseGuestDiagramStateReturn {
  const [title, setTitleInternal] = useState('Untitled Diagram')
  const [nodes, setNodesInternal] = useState<DiagramNode[]>([])
  const [edges, setEdgesInternal] = useState<DiagramEdge[]>([])
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)

  const { pushToHistory, undo: undoFromHistory, redo: redoFromHistory, canUndo, canRedo } = useUndoHistory()
  const nodesRef = useRef<DiagramNode[]>(nodes)
  const edgesRef = useRef<DiagramEdge[]>(edges)
  const nodeDragHistoryRef = useRef(false)

  useEffect(() => {
    nodesRef.current = nodes
    edgesRef.current = edges
  }, [nodes, edges])

  const setTitle = useCallback((newTitle: string) => {
    setTitleInternal(newTitle)
    setHasUnsavedChanges(true)
  }, [])

  const setNodes: React.Dispatch<React.SetStateAction<DiagramNode[]>> = useCallback(
    (value) => {
      setNodesInternal(value)
      setHasUnsavedChanges(true)
    },
    []
  )

  const setEdges: React.Dispatch<React.SetStateAction<DiagramEdge[]>> = useCallback(
    (value) => {
      setEdgesInternal(value)
      setHasUnsavedChanges(true)
    },
    []
  )

  const handleNodesChange = useCallback(
    (changes: NodeChange<DiagramNode>[]) => {
      const hasRealChanges = changes.some(
        (c) => c.type !== 'select' && c.type !== 'dimensions'
      )
      const hasDraggingChange = changes.some(
        (c) => c.type === 'position' && c.dragging === true
      )
      const hasPositionChange = changes.some((c) => c.type === 'position')
      const endsDragging = changes.some(
        (c) => c.type === 'position' && c.dragging === false
      )
      if (hasRealChanges) {
        if (hasDraggingChange) {
          if (!nodeDragHistoryRef.current) {
            pushToHistory({ nodes: nodesRef.current, edges: edgesRef.current })
          }
          nodeDragHistoryRef.current = true
        } else if (!hasPositionChange || !nodeDragHistoryRef.current) {
          pushToHistory({ nodes: nodesRef.current, edges: edgesRef.current })
        }
      }
      if (endsDragging) nodeDragHistoryRef.current = false
      setNodesInternal((nds) => applyNodeChanges(changes, nds) as DiagramNode[])
      if (hasRealChanges) {
        setHasUnsavedChanges(true)
      }
    },
    [pushToHistory]
  )

  const handleEdgesChange = useCallback(
    (changes: EdgeChange<DiagramEdge>[]) => {
      const hasRealChanges = changes.some((c) => c.type !== 'select')
      if (hasRealChanges) {
        pushToHistory({ nodes: nodesRef.current, edges: edgesRef.current })
      }
      setEdgesInternal((eds) => applyEdgeChanges(changes, eds) as DiagramEdge[])
      if (hasRealChanges) {
        setHasUnsavedChanges(true)
      }
    },
    [pushToHistory]
  )

  const undo = useCallback(() => {
    const previousState = undoFromHistory({ nodes: nodesRef.current, edges: edgesRef.current })
    if (previousState) {
      setNodes(previousState.nodes)
      setEdges(previousState.edges)
    }
  }, [undoFromHistory, setNodes, setEdges])

  const redo = useCallback(() => {
    const nextState = redoFromHistory({ nodes: nodesRef.current, edges: edgesRef.current })
    if (nextState) {
      setNodes(nextState.nodes)
      setEdges(nextState.edges)
    }
  }, [redoFromHistory, setNodes, setEdges])

  const markSaved = useCallback(() => {
    setHasUnsavedChanges(false)
  }, [])

  const loadFromFile = useCallback((data: LoadFromFileData) => {
    setTitleInternal(data.title)
    setNodesInternal(data.nodes)
    setEdgesInternal(data.edges)
    setHasUnsavedChanges(false)
  }, [])

  // Warn before leaving with unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault()
        e.returnValue = ''
      }
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [hasUnsavedChanges])

  return {
    title,
    setTitle,
    nodes,
    edges,
    setNodes,
    setEdges,
    onNodesChange: handleNodesChange,
    onEdgesChange: handleEdgesChange,
    undo,
    canUndo: canUndo(),
    redo,
    canRedo: canRedo(),
    hasUnsavedChanges,
    markSaved,
    loadFromFile,
  }
}
