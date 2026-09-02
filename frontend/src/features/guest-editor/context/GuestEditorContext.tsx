import { createContext, useContext, type ReactNode } from 'react'
import type { DiagramNode, DiagramEdge } from '@/features/dfd-editor/types'
import type {
  GuestThreat,
  GuestCountermeasure,
  GuestSessionMetadata,
  GuestSystemInfo,
  GuestDataAsset,
  GuestAssumption,
  GuestOutOfScopeItem,
  GuestSystemContext,
  ThreatStatus,
} from '../types'
import type { STRIDECategory } from '@/types/domain'

interface GuestEditorContextType {
  // Diagram data (read-only from context consumers)
  nodes: DiagramNode[]
  edges: DiagramEdge[]
  title: string

  // Threat operations
  addThreat: (
    targetId: string,
    targetType: GuestThreat['targetType'],
    name: string,
    description: string,
    severity: GuestThreat['severity'],
    category?: STRIDECategory,
    status?: ThreatStatus,
    decisionRationale?: string
  ) => void
  updateThreat: (
    threatId: string,
    updates: Partial<Pick<GuestThreat, 'name' | 'description' | 'severity' | 'category' | 'status' | 'decisionRationale'>>
  ) => void
  removeThreat: (threatId: string) => void
  getThreatsForTarget: (targetId: string) => GuestThreat[]
  getThreatCount: (targetId: string) => number
  getAllThreats: () => GuestThreat[]
  loadThreats: (threats: GuestThreat[]) => void

  // Countermeasure operations
  addCountermeasure: (
    threatId: string,
    name: string,
    description: string,
    controlFunction: GuestCountermeasure['controlFunction'],
    controlNature: GuestCountermeasure['controlNature']
  ) => void
  updateCountermeasure: (
    countermeasureId: string,
    updates: Partial<Pick<GuestCountermeasure, 'name' | 'description' | 'controlFunction' | 'controlNature'>>
  ) => void
  removeCountermeasure: (countermeasureId: string) => void
  getCountermeasuresForThreat: (threatId: string) => GuestCountermeasure[]
  getCountermeasureCount: (threatId: string) => number
  getAllCountermeasures: () => GuestCountermeasure[]
  loadCountermeasures: (countermeasures: GuestCountermeasure[]) => void

  // System Context state (read-only)
  session: GuestSessionMetadata
  systemInfo: GuestSystemInfo
  dataAssets: GuestDataAsset[]
  assumptions: GuestAssumption[]
  outOfScopeItems: GuestOutOfScopeItem[]

  // System Context operations
  updateSession: (updates: Partial<GuestSessionMetadata>) => void
  updateSystemInfo: (updates: Partial<GuestSystemInfo>) => void
  addDataAsset: (asset: Omit<GuestDataAsset, 'id'>) => void
  updateDataAsset: (assetId: string, updates: Partial<Omit<GuestDataAsset, 'id'>>) => void
  removeDataAsset: (assetId: string) => void
  addAssumption: (assumption: Omit<GuestAssumption, 'id'>) => void
  updateAssumption: (assumptionId: string, updates: Partial<Omit<GuestAssumption, 'id'>>) => void
  removeAssumption: (assumptionId: string) => void
  addOutOfScopeItem: (item: Omit<GuestOutOfScopeItem, 'id'>) => void
  updateOutOfScopeItem: (itemId: string, updates: Partial<Omit<GuestOutOfScopeItem, 'id'>>) => void
  removeOutOfScopeItem: (itemId: string) => void
  loadSystemContext: (context: GuestSystemContext) => void
  getSystemContext: () => GuestSystemContext
}

const GuestEditorContext = createContext<GuestEditorContextType | null>(null)

export function GuestEditorProvider({
  children,
  value,
}: {
  children: ReactNode
  value: GuestEditorContextType
}) {
  return (
    <GuestEditorContext.Provider value={value}>
      {children}
    </GuestEditorContext.Provider>
  )
}

export function useGuestEditor(): GuestEditorContextType | null {
  return useContext(GuestEditorContext)
}
