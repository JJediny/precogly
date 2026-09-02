import type { STRIDECategory } from '@/types/domain'

export type ThreatStatus = 'open' | 'accept' | 'mitigate' | 'delegate' | 'eliminate'

export interface GuestThreat {
  id: string
  targetId: string
  targetType: 'component' | 'dataflow' | 'systemScope'
  name: string
  description: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  category?: STRIDECategory
  status: ThreatStatus
  decisionRationale?: string
  createdAt: string
}

export type ControlFunction = 'preventive' | 'detective' | 'corrective' | 'deterrent' | 'recovery' | 'compensating'
export type ControlNature = 'technical' | 'administrative' | 'physical'

export interface GuestCountermeasure {
  id: string
  threatId: string
  name: string
  description: string
  controlFunction: ControlFunction[]
  controlNature: ControlNature
  createdAt: string
}

export const GUEST_CONTROL_FUNCTIONS = [
  { value: 'preventive' as const, label: 'Preventive', description: 'Stops an attack or fault from occurring. E.g. input validation, access control, encryption at rest.' },
  { value: 'detective' as const, label: 'Detective', description: 'Identifies an attack or fault during or after the fact. E.g. audit logging, intrusion detection, anomaly alerting.' },
  { value: 'corrective' as const, label: 'Corrective', description: 'Limits damage and fixes the problem once detected. E.g. applying a patch, revoking a compromised token.' },
  { value: 'deterrent' as const, label: 'Deterrent', description: 'Discourages a threat actor from attempting an attack. E.g. warning banners, visible monitoring, legal notices.' },
  { value: 'recovery' as const, label: 'Recovery', description: 'Restores systems or data to normal after an incident. E.g. restoring from backup, failover, disaster-recovery procedures.' },
  { value: 'compensating' as const, label: 'Compensating', description: 'Alternative control when the primary is not feasible. E.g. enforced manual review where automated gating is unavailable.' },
] as const

export const GUEST_CONTROL_NATURES = [
  { value: 'technical' as const, label: 'Technical', description: 'Implemented in software, firmware, or hardware and enforced by the system. E.g. firewall rules, cryptographic controls, ACLs.' },
  { value: 'administrative' as const, label: 'Administrative / Procedural', description: 'Implemented through policies, processes, and human behaviour. E.g. secure-coding standards, code-review steps, security training.' },
  { value: 'physical' as const, label: 'Physical', description: 'Implemented through physical-world barriers and safeguards. E.g. locked server rooms, badge readers, tamper-evident seals.' },
] as const

// --- System Context types ---

export interface GuestSessionMetadata {
  facilitator: string
  participants: string[]
  meetingDate: string // ISO date (YYYY-MM-DD) or empty
}

export interface GuestSystemInfo {
  description: string
  criticality: 'low' | 'medium' | 'high' | 'critical'
}

export interface GuestDataAsset {
  id: string
  name: string
  description: string
  classification: string
  confidentiality: 'low' | 'medium' | 'high'
  integrity: 'low' | 'medium' | 'high'
  availability: 'low' | 'medium' | 'high'
  complianceTags: string[]
  dataSensitivity: string[]
}

export interface GuestAssumption {
  id: string
  description: string
  validity: 'unconfirmed' | 'confirmed' | 'rejected'
  topics: string[]
}

export interface GuestOutOfScopeItem {
  id: string
  name: string
  reason: string
}

export interface GuestSystemContext {
  session: GuestSessionMetadata
  systemInfo: GuestSystemInfo
  dataAssets: GuestDataAsset[]
  assumptions: GuestAssumption[]
  outOfScopeItems: GuestOutOfScopeItem[]
}

export interface SystemContextExtension {
  session: GuestSessionMetadata
  systemInfo: GuestSystemInfo
  dataAssets: GuestDataAsset[]
  assumptions: GuestAssumption[]
  outOfScopeItems: GuestOutOfScopeItem[]
}

export const GUEST_CRITICALITY_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
] as const

export const GUEST_CIA_LEVELS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
] as const

export const GUEST_ASSUMPTION_VALIDITY = [
  { value: 'unconfirmed', label: 'Unconfirmed' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'rejected', label: 'Rejected' },
] as const

export const GUEST_THREAT_STATUS_OPTIONS = [
  { value: 'open', label: 'Open', description: 'Not yet triaged — needs a decision' },
  { value: 'accept', label: 'Accept', description: 'Risk is tolerable — no action needed' },
  { value: 'mitigate', label: 'Mitigate', description: 'Reduce risk with countermeasures' },
  { value: 'delegate', label: 'Delegate', description: 'Transfer risk to another party' },
  { value: 'eliminate', label: 'Eliminate', description: 'Remove the threat source entirely' },
] as const

export const RATIONALE_REQUIRED_STATUSES: ThreatStatus[] = ['accept', 'delegate', 'eliminate']

export const STATUS_COLORS: Record<ThreatStatus, string> = {
  open: 'bg-gray-100 text-gray-800',
  accept: 'bg-yellow-100 text-yellow-800',
  mitigate: 'bg-green-100 text-green-800',
  delegate: 'bg-purple-100 text-purple-800',
  eliminate: 'bg-blue-100 text-blue-800',
}

export function getThreatWarning(
  threat: GuestThreat,
  countermeasureCount: number
): string | null {
  if (
    RATIONALE_REQUIRED_STATUSES.includes(threat.status) &&
    !threat.decisionRationale?.trim()
  ) {
    return `Decision rationale recommended for "${threat.status}" status`
  }
  if (threat.status === 'mitigate' && countermeasureCount === 0) {
    return 'Status is "mitigate" but no countermeasures defined'
  }
  return null
}

