/* eslint-disable react-refresh/only-export-components */
import { memo, type ComponentType } from 'react'
import { useParams } from 'react-router-dom'
import { EdgeLabelRenderer, type EdgeProps, type NodeProps } from '@xyflow/react'
import { useThreatModelThreats } from '@/features/threat-models/api/threats'

// Import original node components
import { ProcessNode } from './ProcessNode'
import { DataStoreNode } from './DataStoreNode'
import { HumanActorNode } from './HumanActorNode'
import { SystemActorNode } from './SystemActorNode'
import { TrustZoneNode } from './TrustZoneNode'
import { SystemScopeNode } from './SystemScopeNode'
import { StickyNoteNode } from './StickyNoteNode'
import { DataFlowEdge as DataFlowEdgeComponent } from '../edges/DataFlowEdge'
import { TrustBoundaryEdge as TrustBoundaryEdgeComponent } from '../edges/TrustBoundaryEdge'

function ThreatBadge({ count }: { count: number }) {
  if (count === 0) return null
  return (
    <div
      className="absolute -top-2 -right-2 z-10 flex items-center justify-center min-w-[20px] h-5 px-1 rounded-full bg-red-500 text-white text-xs font-bold shadow-sm"
      style={{ pointerEvents: 'none' }}
    >
      {count}
    </div>
  )
}

function useThreatCount(canvasElementId: string): number {
  const { id: threatModelId } = useParams<{ id: string }>()
  const { data: threatData } = useThreatModelThreats(threatModelId)

  if (!threatData?.componentThreats) return 0

  return threatData.componentThreats.filter(
    (t) => t.componentId === canvasElementId && !t.dismissed
  ).length
}

function withThreatBadge<P extends NodeProps>(NodeComponent: ComponentType<P>) {
  const WrappedNode = memo(function WrappedNode(props: P) {
    const count = useThreatCount(props.id)

    return (
      <div className="relative w-full h-full">
        <ThreatBadge count={count} />
        <NodeComponent {...props} />
      </div>
    )
  })
  return WrappedNode
}

// Wrapped node types with threat badges
export const canvasNodeTypes = {
  process: withThreatBadge(ProcessNode),
  datastore: withThreatBadge(DataStoreNode),
  humanActor: withThreatBadge(HumanActorNode),
  systemActor: withThreatBadge(SystemActorNode),
  trustZone: withThreatBadge(TrustZoneNode),
  systemScope: withThreatBadge(SystemScopeNode),
  stickyNote: StickyNoteNode,
} as const

// Edge wrapper that adds a threat count badge
function withEdgeThreatBadge<P extends EdgeProps>(EdgeComponent: ComponentType<P>) {
  const WrappedEdge = memo(function WrappedEdge(props: P) {
    const count = useThreatCount(props.id)

    return (
      <>
        <EdgeComponent {...props} />
        {count > 0 && (
          <EdgeLabelRenderer>
            <div
              data-id={props.id}
              className="absolute pointer-events-none nodrag nopan"
              style={{
                left: (props.sourceX + props.targetX) / 2,
                top: (props.sourceY + props.targetY) / 2 - 20,
                transform: 'translate(-50%, -50%)',
              }}
            >
              <div className="flex items-center justify-center min-w-[20px] h-5 px-1 rounded-full bg-red-500 text-white text-xs font-bold shadow-sm">
                {count}
              </div>
            </div>
          </EdgeLabelRenderer>
        )}
      </>
    )
  })
  return WrappedEdge
}

// Wrapped edge types with threat badges
export const canvasEdgeTypes = {
  dataFlow: withEdgeThreatBadge(DataFlowEdgeComponent),
  trustBoundary: TrustBoundaryEdgeComponent,
} as const
