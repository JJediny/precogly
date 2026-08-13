import { useCallback, useEffect } from 'react'
import { useReactFlow } from '@xyflow/react'
import type { DiagramNode, DiagramEdge } from '../types'

interface UseKeyboardShortcutsOptions {
  onSave?: () => void
  onUndo?: () => void
  onRedo?: () => void
  onSelectAll?: () => void
  onDeselect?: () => void
  onDelete?: () => void
  onCopy?: () => void
  onPaste?: () => void
  onDuplicate?: () => void
  enabled?: boolean
}

interface ClipboardData {
  nodes: DiagramNode[]
  edges: DiagramEdge[]
}

// Module-level clipboard for copy/paste
let clipboard: ClipboardData | null = null

export function useKeyboardShortcuts({
  onSave,
  onUndo,
  onRedo,
  onSelectAll,
  onDeselect,
  onDelete,
  onCopy,
  onPaste,
  onDuplicate,
  enabled = true,
}: UseKeyboardShortcutsOptions = {}) {
  const { getNodes, getEdges, setNodes, setEdges } = useReactFlow()

  // Default delete handler
  const handleDelete = useCallback(() => {
    const nodes = getNodes() as DiagramNode[]
    const edges = getEdges() as DiagramEdge[]

    const selectedNodes = nodes.filter((n) => n.selected)
    const selectedEdges = edges.filter((e) => e.selected)

    if (selectedNodes.length === 0 && selectedEdges.length === 0) return

    const selectedNodeIds = new Set(selectedNodes.map((n) => n.id))

    // For boundary nodes, convert children to root nodes
    const boundaryIds = selectedNodes
      .filter((n) => n.type === 'trustZone' || n.type === 'systemScope')
      .map((n) => n.id)

    const updatedNodes = nodes
      .filter((n) => !selectedNodeIds.has(n.id))
      .map((n) => {
        if (n.parentId && boundaryIds.includes(n.parentId)) {
          const parent = nodes.find((p) => p.id === n.parentId)
          if (parent) {
            return {
              ...n,
              parentId: undefined,
              position: {
                x: n.position.x + parent.position.x,
                y: n.position.y + parent.position.y,
              },
            }
          }
        }
        return n
      })

    const selectedEdgeIds = new Set(selectedEdges.map((e) => e.id))
    const updatedEdges = edges.filter(
      (e) =>
        !selectedEdgeIds.has(e.id) &&
        !selectedNodeIds.has(e.source) &&
        !selectedNodeIds.has(e.target)
    )

    setNodes(updatedNodes)
    setEdges(updatedEdges)
  }, [getNodes, getEdges, setNodes, setEdges])

  // Default copy handler
  const handleCopy = useCallback(() => {
    const nodes = getNodes() as DiagramNode[]
    const edges = getEdges() as DiagramEdge[]

    const selectedNodes = nodes.filter((n) => n.selected)
    if (selectedNodes.length === 0) return

    const selectedNodeIds = new Set(selectedNodes.map((n) => n.id))

    // Copy edges that connect selected nodes
    const connectedEdges = edges.filter(
      (e) => selectedNodeIds.has(e.source) && selectedNodeIds.has(e.target)
    )

    clipboard = {
      nodes: selectedNodes,
      edges: connectedEdges,
    }
  }, [getNodes, getEdges])

  // Default paste handler
  const handlePaste = useCallback(() => {
    if (!clipboard || clipboard.nodes.length === 0) return

    const timestamp = Date.now()
    const offset = 50 // Offset pasted nodes

    // Create ID mapping for new nodes
    const idMap = new Map<string, string>()
    clipboard.nodes.forEach((node) => {
      idMap.set(node.id, `${node.type}-${timestamp}-${Math.random().toString(36).slice(2, 7)}`)
    })

    // Create new nodes with offset positions
    const newNodes: DiagramNode[] = clipboard.nodes.map((node) => ({
      ...node,
      id: idMap.get(node.id)!,
      position: {
        x: node.position.x + offset,
        y: node.position.y + offset,
      },
      selected: true,
      parentId: node.parentId && idMap.has(node.parentId)
        ? idMap.get(node.parentId)
        : undefined,
    }))

    // Create new edges with updated references
    const newEdges: DiagramEdge[] = clipboard.edges.map((edge) => ({
      ...edge,
      id: `edge-${timestamp}-${Math.random().toString(36).slice(2, 7)}`,
      source: idMap.get(edge.source) || edge.source,
      target: idMap.get(edge.target) || edge.target,
      selected: false,
    }))

    // Deselect existing nodes and add new ones
    setNodes((nodes) => [
      ...nodes.map((n) => ({ ...n, selected: false })),
      ...newNodes,
    ])

    setEdges((edges) => [...edges, ...newEdges])
  }, [setNodes, setEdges])

  // Default duplicate handler (copy + paste in one action)
  const handleDuplicate = useCallback(() => {
    handleCopy()
    handlePaste()
  }, [handleCopy, handlePaste])

  // Default select all handler
  const handleSelectAll = useCallback(() => {
    setNodes((nodes) => nodes.map((n) => ({ ...n, selected: true })))
    setEdges((edges) => edges.map((e) => ({ ...e, selected: true })))
  }, [setNodes, setEdges])

  // Default deselect handler
  const handleDeselect = useCallback(() => {
    setNodes((nodes) => nodes.map((n) => ({ ...n, selected: false })))
    setEdges((edges) => edges.map((e) => ({ ...e, selected: false })))
  }, [setNodes, setEdges])

  // Keyboard event handler
  useEffect(() => {
    if (!enabled) return

    const handleKeyDown = (event: KeyboardEvent) => {
      // Don't handle shortcuts when typing in inputs or while focus is
      // inside a modal — canvas edits behind an open dialog are invisible
      const target = event.target as HTMLElement
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable ||
        target.closest?.('[role="dialog"], [role="alertdialog"]')
      ) {
        return
      }

      const isMod = event.metaKey || event.ctrlKey
      const key = event.key.toLowerCase()

      // Save: Cmd/Ctrl + S
      if (isMod && key === 's') {
        event.preventDefault()
        onSave?.()
        return
      }

      // Undo: Cmd/Ctrl + Z
      if (isMod && key === 'z' && !event.shiftKey) {
        event.preventDefault()
        onUndo?.()
        return
      }

      // Redo: Cmd/Ctrl + Shift + Z or Cmd/Ctrl + Y
      if ((isMod && key === 'z' && event.shiftKey) || (isMod && key === 'y')) {
        event.preventDefault()
        onRedo?.()
        return
      }

      // Select All: Cmd/Ctrl + A
      if (isMod && key === 'a') {
        event.preventDefault()
        ;(onSelectAll || handleSelectAll)()
        return
      }

      // Deselect: Escape
      if (key === 'escape') {
        event.preventDefault()
        ;(onDeselect || handleDeselect)()
        return
      }

      // Delete: Delete or Backspace
      if (key === 'delete' || key === 'backspace') {
        event.preventDefault()
        ;(onDelete || handleDelete)()
        return
      }

      // Copy: Cmd/Ctrl + C
      if (isMod && key === 'c') {
        event.preventDefault()
        ;(onCopy || handleCopy)()
        return
      }

      // Paste: Cmd/Ctrl + V
      if (isMod && key === 'v') {
        event.preventDefault()
        ;(onPaste || handlePaste)()
        return
      }

      // Duplicate: Cmd/Ctrl + D
      if (isMod && key === 'd') {
        event.preventDefault()
        ;(onDuplicate || handleDuplicate)()
        return
      }

      // Zoom to fit: Cmd/Ctrl + 0
      if (isMod && key === '0') {
        event.preventDefault()
        // React Flow's fitView is handled by the component itself
        return
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [
    enabled,
    onSave,
    onUndo,
    onRedo,
    onSelectAll,
    onDeselect,
    onDelete,
    onCopy,
    onPaste,
    onDuplicate,
    handleSelectAll,
    handleDeselect,
    handleDelete,
    handleCopy,
    handlePaste,
    handleDuplicate,
  ])

  return {
    handleCopy,
    handlePaste,
    handleDuplicate,
    handleDelete,
    handleSelectAll,
    handleDeselect,
  }
}
