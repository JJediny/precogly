import { memo, useCallback } from 'react'
import { NodeResizer, useReactFlow, type Node, type NodeProps, type ResizeDragEvent, type ResizeParams } from '@xyflow/react'
import { StickyNote } from 'lucide-react'
import { cn } from '@/lib/utils'
import { InlineEditableLabel } from './InlineEditableLabel'
import type { DiagramNode, StickyNoteNodeData, StickyNoteColor, StickyNoteTextSize } from '../../types'

type StickyNoteNodeType = Node<StickyNoteNodeData, 'stickyNote'>

const NOTE_COLORS: Record<StickyNoteColor, { background: string; border: string; text: string }> = {
  yellow: { background: '#fef9c3', border: '#eab308', text: '#713f12' },
  blue: { background: '#dbeafe', border: '#3b82f6', text: '#1e3a8a' },
  green: { background: '#dcfce7', border: '#22c55e', text: '#14532d' },
  pink: { background: '#fce7f3', border: '#ec4899', text: '#831843' },
  orange: { background: '#ffedd5', border: '#f97316', text: '#7c2d12' },
}

const TEXT_SIZE_CLASSES: Record<StickyNoteTextSize, string> = {
  small: 'text-xs',
  medium: 'text-sm',
  large: 'text-base',
}

export const StickyNoteNode = memo(function StickyNoteNode({ id, data, selected }: NodeProps<StickyNoteNodeType>) {
  const colors = NOTE_COLORS[data.noteColor || 'yellow']
  const textSize = data.textSize || 'medium'
  const { setNodes } = useReactFlow<DiagramNode>()

  const handleResizeEnd = useCallback(
    (_event: ResizeDragEvent, { width, height }: ResizeParams) => {
      setNodes((nodes) =>
        nodes.map((node) =>
          node.id === id
            ? { ...node, style: { ...node.style, width, height } }
            : node
        )
      )
    },
    [id, setNodes]
  )

  return (
    <>
      <NodeResizer
        minWidth={120}
        minHeight={80}
        isVisible={selected}
        lineClassName="!border-solid"
        handleClassName="!w-2 !h-2 !rounded-sm"
        lineStyle={{ borderColor: '#eab308' }}
        handleStyle={{ backgroundColor: '#eab308', borderColor: '#eab308' }}
        onResizeEnd={handleResizeEnd}
      />
      <div
        className={cn('relative h-full w-full rounded-sm border-2 p-3 shadow-sm transition-shadow', selected && 'shadow-md ring-2 ring-amber-300')}
        style={{ backgroundColor: colors.background, borderColor: colors.border, color: colors.text }}
      >
        <StickyNote className="absolute right-2 top-2 h-4 w-4 opacity-60" />
        <InlineEditableLabel
          nodeId={id}
          label={data.label}
          isEditing={data.isInlineEditing}
          className={cn('block max-w-[140px] whitespace-pre-line break-words', TEXT_SIZE_CLASSES[textSize], data.bold && 'font-bold', data.italic && 'italic')}
          inputClassName={cn('w-full', TEXT_SIZE_CLASSES[textSize], data.bold && 'font-bold', data.italic && 'italic')}
        />
      </div>
    </>
  )
})
