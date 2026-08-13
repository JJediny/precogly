import { memo } from 'react'
import {
  BaseEdge,
  EdgeLabelRenderer,
  type Edge,
  type EdgeProps,
} from '@xyflow/react'
import { Lock, ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { TrustBoundaryEdgeData } from '../../types'

type TrustBoundaryEdgeType = Edge<TrustBoundaryEdgeData, 'trustBoundary'>

/**
 * Determine security posture color based on configured auth & access control.
 * - Red: no auth and no access control configured
 * - Amber: either auth or access control configured (partial)
 * - Green: both auth and access control configured
 */
function getSecurityColor(data?: TrustBoundaryEdgeData): string {
  const hasAuth =
    data?.authenticationMethods &&
    data.authenticationMethods.length > 0 &&
    !data.authenticationMethods.every((m) => m === 'none')
  const hasAccessControl =
    data?.accessControlMethods &&
    data.accessControlMethods.length > 0 &&
    !data.accessControlMethods.every((m) => m === 'none')

  if (hasAuth && hasAccessControl) return '#22c55e'
  if (hasAuth || hasAccessControl) return '#f59e0b'
  return '#ef4444'
}

/**
 * Trust Boundary Edge — renders as a vertical or horizontal dividing line
 * in the gap between two trust zones, like a fence/wall separating them.
 */
export const TrustBoundaryEdge = memo(function TrustBoundaryEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
  selected,
}: EdgeProps<TrustBoundaryEdgeType>) {
  const color = getSecurityColor(data)

  const dx = targetX - sourceX
  const dy = targetY - sourceY
  const isHorizontalGap = Math.abs(dx) >= Math.abs(dy)

  // Generous extension so the line spans the full height/width of the zones
  const extension = 120

  let edgePath: string
  let labelX: number
  let labelY: number

  if (isHorizontalGap) {
    // Zones are side-by-side — draw a VERTICAL dividing line in the gap
    const midX = (sourceX + targetX) / 2
    const minY = Math.min(sourceY, targetY) - extension
    const maxY = Math.max(sourceY, targetY) + extension
    edgePath = `M ${midX} ${minY} L ${midX} ${maxY}`
    labelX = midX
    labelY = (sourceY + targetY) / 2 - extension - 20
  } else {
    // Zones are stacked — draw a HORIZONTAL dividing line in the gap
    const midY = (sourceY + targetY) / 2
    const minX = Math.min(sourceX, targetX) - extension
    const maxX = Math.max(sourceX, targetX) + extension
    edgePath = `M ${minX} ${midY} L ${maxX} ${midY}`
    labelX = (sourceX + targetX) / 2
    labelY = midY - 20
  }

  const hasAuth =
    data?.authenticationMethods &&
    data.authenticationMethods.length > 0 &&
    !data.authenticationMethods.every((m) => m === 'none')
  const hasAccessControl =
    data?.accessControlMethods &&
    data.accessControlMethods.length > 0 &&
    !data.accessControlMethods.every((m) => m === 'none')

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        className={cn(
          'transition-all',
          selected && '!stroke-blue-500'
        )}
        style={{
          stroke: selected ? undefined : color,
          strokeWidth: selected ? 3 : 2.5,
          strokeDasharray: '10 6',
          strokeLinecap: 'round',
        }}
      />

      <EdgeLabelRenderer>
        <div
          data-id={id}
          className={cn(
            'absolute pointer-events-auto nodrag nopan flex items-center gap-1.5',
            'transform -translate-x-1/2 transition-opacity',
            selected ? 'opacity-100' : 'opacity-70 hover:opacity-100'
          )}
          style={{
            left: labelX,
            top: labelY,
          }}
        >
          {/* Security badge icons */}
          {hasAuth && (
            <div
              className="p-1 rounded"
              style={{ backgroundColor: `${color}20`, color }}
              title="Authentication configured"
            >
              <Lock className="h-3 w-3" />
            </div>
          )}
          {hasAccessControl && (
            <div
              className="p-1 rounded"
              style={{ backgroundColor: `${color}20`, color }}
              title="Access control configured"
            >
              <ShieldCheck className="h-3 w-3" />
            </div>
          )}

          {/* Label or "no security" indicator */}
          <div
            className="px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap border"
            style={{
              backgroundColor: `${color}15`,
              borderColor: color,
              color,
            }}
          >
            {data?.label || 'Trust Boundary'}
          </div>
        </div>
      </EdgeLabelRenderer>
    </>
  )
})
