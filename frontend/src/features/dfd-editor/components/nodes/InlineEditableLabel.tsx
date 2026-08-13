import { memo, useCallback, useEffect, useRef, useState } from 'react'
import { useReactFlow } from '@xyflow/react'
import { cn } from '@/lib/utils'
import type { DiagramNode } from '../../types'

interface InlineEditableLabelProps {
  nodeId: string
  label: string
  isEditing?: boolean
  className?: string
  inputClassName?: string
}

export const InlineEditableLabel = memo(function InlineEditableLabel({
  nodeId,
  label,
  isEditing,
  className,
  inputClassName,
}: InlineEditableLabelProps) {
  const { setNodes } = useReactFlow<DiagramNode>()
  const [editValue, setEditValue] = useState(label)
  const inputRef = useRef<HTMLInputElement>(null)
  const hasCommittedRef = useRef(false)
  const originalLabelRef = useRef(label)

  // Reset local state and focus input when entering edit mode.
  // Intentionally depends only on isEditing — we capture label at the moment editing
  // starts and must NOT re-run on label changes during typing (which would re-select all text).
  useEffect(() => {
    if (isEditing) {
      hasCommittedRef.current = false
      originalLabelRef.current = label
      setEditValue(label)
      requestAnimationFrame(() => {
        inputRef.current?.focus()
        inputRef.current?.select()
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- Only run when isEditing transitions, not on every label keystroke
  }, [isEditing])

  // Update both local state (for fast input) and node data (for panel sync)
  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value
      setEditValue(value)
      setNodes((nodes) =>
        nodes.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, label: value } }
            : n
        )
      )
    },
    [nodeId, setNodes]
  )

  const finishEdit = useCallback(
    (revert: boolean) => {
      if (hasCommittedRef.current) return
      hasCommittedRef.current = true

      const finalLabel = revert
        ? originalLabelRef.current
        : (editValue.trim() || originalLabelRef.current)

      setNodes((nodes) =>
        nodes.map((n) =>
          n.id === nodeId
            ? { ...n, data: { ...n.data, label: finalLabel, isInlineEditing: false } }
            : n
        )
      )
    },
    [nodeId, editValue, setNodes]
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      e.stopPropagation()
      if (e.key === 'Enter') {
        finishEdit(false)
      } else if (e.key === 'Escape') {
        finishEdit(true)
      }
    },
    [finishEdit]
  )

  const handleBlur = useCallback(() => {
    finishEdit(false)
  }, [finishEdit])

  // Prevent React Flow from interpreting mouse events on the input
  const stopPropagation = useCallback((e: React.MouseEvent) => {
    e.stopPropagation()
  }, [])

  if (!isEditing) {
    return <span title={label} className={className}>{label}</span>
  }

  return (
    <input
      ref={inputRef}
      type="text"
      value={editValue}
      onChange={handleChange}
      onKeyDown={handleKeyDown}
      onBlur={handleBlur}
      onClick={stopPropagation}
      onMouseDown={stopPropagation}
      onDoubleClick={stopPropagation}
      className={cn(
        'nodrag nopan nowheel',
        'bg-transparent border-b border-current outline-none',
        'text-inherit font-inherit',
        inputClassName
      )}
    />
  )
})
