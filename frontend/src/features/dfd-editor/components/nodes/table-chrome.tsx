import type { ReactNode, CSSProperties } from 'react'
import { GripVertical, Trash2 } from 'lucide-react'
import { ContextMenu, ContextMenuTrigger } from '@/components/ui/context-menu'
import { cn } from '@/lib/utils'

/**
 * The controls drawn around a table node: the grips that select a row or
 * column, and the small buttons that add and remove them.
 *
 * Both are presentation over a few callbacks, so they leave TableNode behind a
 * small props contract. The row and column variants differ only by axis, so
 * they are one component — two would let a fix land in the column version and
 * miss the row one.
 */

/** Thickness of the hit area for a divider drag. */
export const DIVIDER_HIT = 7
/**
 * Thickness of the row and column grips. Notion and FigJam both span the whole
 * edge rather than offering a small target. The first version here was a 14px
 * strip that appeared only on hover, and it could not be found.
 */
export const GRIP = 18
/** Side of the square corner handles that scale the whole table. */
export const HANDLE = 8
/** Side of the small square action buttons: append a row/column, delete one. */
export const BUTTON = 18
/** Clearance between an action button and whatever edge it sits beside. */
export const GAP = 6

export const CORNERS = [
  { corner: 'nw', cursor: 'cursor-nwse-resize', style: (h: number) => ({ left: -h / 2, top: -h / 2 }) },
  { corner: 'ne', cursor: 'cursor-nesw-resize', style: (h: number) => ({ right: -h / 2, top: -h / 2 }) },
  { corner: 'se', cursor: 'cursor-nwse-resize', style: (h: number) => ({ right: -h / 2, bottom: -h / 2 }) },
  { corner: 'sw', cursor: 'cursor-nesw-resize', style: (h: number) => ({ left: -h / 2, bottom: -h / 2 }) },
] as const

/**
 * The small square buttons that sit outside the table: append a row or column,
 * delete the selected one.
 *
 * `pointer-events-auto` because several of these live inside grid items that
 * are `pointer-events-none` — those items exist to occupy a track, not to
 * intercept clicks meant for the cell beneath.
 */
export function TableActionButton({
  onClick,
  title,
  disabled,
  destructive,
  className,
  style,
  children,
}: {
  onClick: () => void
  title: string
  disabled?: boolean
  destructive?: boolean
  className?: string
  style?: CSSProperties
  children: ReactNode
}) {
  return (
    <button
      onPointerDown={(event) => event.stopPropagation()}
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={cn(
        'nodrag nopan pointer-events-auto absolute flex items-center justify-center rounded-sm border border-slate-300 bg-white text-slate-500 shadow-sm disabled:opacity-40',
        destructive ? 'hover:bg-red-50 hover:text-red-600' : 'hover:bg-slate-100 hover:text-slate-800',
        className
      )}
      style={{ width: BUTTON, height: BUTTON, ...style }}
    >
      {children}
    </button>
  )
}

/**
 * One row or column grip: a bar spanning that whole row or column, drawn rather
 * than revealed on hover so there is something to aim at.
 *
 * The grip is a grid item in its own track, pushing its visible bar outside the
 * grid with `bottom: 100%` (columns) or `right: 100%` (rows). It therefore stays
 * aligned with a row that has grown past its stored height, with no offset to
 * recompute.
 */
export function TableAxisGrip({
  axis,
  index,
  selected,
  deleteDisabled,
  onSelect,
  onDelete,
  menu,
}: {
  axis: 'row' | 'column'
  index: number
  selected: boolean
  deleteDisabled: boolean
  onSelect: () => void
  onDelete: () => void
  menu: ReactNode
}) {
  const isColumn = axis === 'column'
  const label = isColumn ? 'Column' : 'Row'

  return (
    <div
      className="pointer-events-none relative"
      style={isColumn ? { gridColumn: index + 1, gridRow: 1 } : { gridRow: index + 1, gridColumn: 1 }}
    >
      <ContextMenu>
        <ContextMenuTrigger asChild>
          <button
            onPointerDown={(event) => event.stopPropagation()}
            onClick={onSelect}
            title={`${label} ${index + 1}`}
            className={cn(
              'nodrag nopan pointer-events-auto absolute flex items-center justify-center border text-slate-400',
              isColumn ? 'inset-x-0 rounded-t-sm border-b-0' : 'inset-y-0 rounded-l-sm border-r-0',
              selected
                ? 'border-blue-400 bg-blue-100 text-blue-600'
                : 'border-slate-300 bg-slate-100 hover:bg-slate-200 hover:text-slate-600'
            )}
            style={isColumn ? { bottom: '100%', height: GRIP } : { right: '100%', width: GRIP }}
          >
            <GripVertical className={cn('h-3 w-3', isColumn && 'rotate-90')} />
          </button>
        </ContextMenuTrigger>
        {menu}
      </ContextMenu>

      {selected && (
        <TableActionButton
          onClick={onDelete}
          disabled={deleteDisabled}
          destructive
          title={`Delete ${axis}`}
          className={isColumn ? 'left-1/2 -translate-x-1/2' : 'top-1/2 -translate-y-1/2'}
          // Clears the edge of the track, then the grip sitting beyond it.
          style={
            isColumn
              ? { bottom: `calc(100% + ${GRIP + GAP}px)` }
              : { right: `calc(100% + ${GRIP + GAP}px)` }
          }
        >
          <Trash2 className="h-3 w-3" />
        </TableActionButton>
      )}
    </div>
  )
}
