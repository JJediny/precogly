import {
  Document,
  ImageRun,
  Paragraph,
  Table,
  TextRun,
  HeadingLevel,
} from 'docx'
import type { DiagramNode, DiagramEdge } from '@/features/dfd-editor/types'
import { isDataFlowEdge } from '@/features/dfd-editor/types'
import type { GuestThreat, GuestCountermeasure, GuestSystemContext, ThreatStatus } from '../types'
import { GUEST_THREAT_STATUS_OPTIONS } from '../types'
import { STRIDE_CONFIG } from '@/types/domain'
import type { STRIDECategory } from '@/types/domain'
import {
  CONTENT_WIDTH,
  h1,
  h2,
  para,
  spacer,
  pageBreak,
  buildTable,
  downloadDocx,
  slugify,
  createDocumentStyles,
  createNumberingConfig,
  createPageProperties,
} from '@/features/reports/utils/wordHelpers'

// ---------------------------------------------------------------------------
// Input data interface
// ---------------------------------------------------------------------------

export interface GuestReportData {
  title: string
  nodes: DiagramNode[]
  edges: DiagramEdge[]
  threats: GuestThreat[]
  countermeasures: GuestCountermeasure[]
  diagramImage?: Uint8Array
  systemContext?: GuestSystemContext
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map node type strings to human-readable labels. */
function formatNodeType(type: string | undefined): string {
  switch (type) {
    case 'process': return 'Process'
    case 'datastore': return 'Data Store'
    case 'humanActor': return 'Human Actor'
    case 'systemActor': return 'System Actor'
    case 'trustZone': return 'Trust Zone'
    case 'systemScope': return 'System Scope'
    case 'stickyNote': return 'Sticky Note'
    default: return type ?? '—'
  }
}

const ACTOR_TYPE_LABELS: Record<string, string> = {
  user: 'User',
  power_user: 'Power User',
  administrator: 'Administrator',
  engineer: 'Engineer',
  third_party: 'Third Party',
  customer: 'Customer',
}

function formatActorType(actorType: string): string {
  return ACTOR_TYPE_LABELS[actorType] ?? actorType
}

/** Resolve a target name from its ID by searching nodes and edges. */
function resolveTargetName(targetId: string, nodes: DiagramNode[], edges: DiagramEdge[]): string {
  const node = nodes.find((n) => n.id === targetId)
  if (node) return (node.data as { label?: string }).label ?? node.id
  const edge = edges.find((e) => e.id === targetId)
  if (edge) return (edge.data as { label?: string })?.label ?? edge.id
  return targetId
}

/** Format a STRIDE category value to its display label. */
function formatStrideCategory(category: STRIDECategory | undefined): string {
  if (!category) return '—'
  return STRIDE_CONFIG[category]?.label ?? category
}

/** Capitalize first letter. */
function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1)
}

/** Format a ThreatStatus to its display label. */
function formatThreatStatus(status: ThreatStatus | undefined): string {
  if (!status) return 'Open'
  return GUEST_THREAT_STATUS_OPTIONS.find((o) => o.value === status)?.label ?? capitalize(status)
}

// ---------------------------------------------------------------------------
// Section: Diagram Overview
// ---------------------------------------------------------------------------

function buildOverviewSection(data: GuestReportData, sectionNum: number): (Paragraph | Table)[] {
  return [
    h1(`${sectionNum}. Diagram Overview`),
    spacer(),
    buildTable(
      [4680, 4680],
      ['Metric', 'Count'],
      [
        ['Components (Nodes)', String(data.nodes.filter((n) => n.type !== 'trustZone' && n.type !== 'systemScope').length)],
        ['Data Flows (Edges)', String(data.edges.filter(isDataFlowEdge).length)],
        ['Threats', String(data.threats.length)],
        ['Countermeasures', String(data.countermeasures.length)],
      ],
    ),
    spacer(),
  ]
}

// ---------------------------------------------------------------------------
// Diagram Image Section (between Overview and Component Inventory)
// ---------------------------------------------------------------------------

/** CONTENT_WIDTH in DXA = 6.5 inches at 1440 DXA/inch. Convert to pixels at 96 DPI. */
const CONTENT_WIDTH_PX = (CONTENT_WIDTH / 1440) * 96 // ≈ 624 px

function buildDiagramImageSection(diagramImage: Uint8Array): (Paragraph | Table)[] {
  // Decode PNG header to read image dimensions (width × height at bytes 16–23)
  const widthBytes = diagramImage.slice(16, 20)
  const heightBytes = diagramImage.slice(20, 24)
  const pngWidth = (widthBytes[0] << 24) | (widthBytes[1] << 16) | (widthBytes[2] << 8) | widthBytes[3]
  const pngHeight = (heightBytes[0] << 24) | (heightBytes[1] << 16) | (heightBytes[2] << 8) | heightBytes[3]

  // The diagram is captured at 2x resolution (IMAGE_SCALE = 2 in export-diagram-image.ts).
  // Use logical (1x) dimensions so the image displays at its intended on-screen size.
  const IMAGE_CAPTURE_SCALE = 2
  const logicalWidth = pngWidth / IMAGE_CAPTURE_SCALE
  const logicalHeight = pngHeight / IMAGE_CAPTURE_SCALE

  // Scale to fit page content width while maintaining aspect ratio
  const scale = CONTENT_WIDTH_PX / logicalWidth
  const displayWidth = Math.round(logicalWidth * scale)
  const displayHeight = Math.round(logicalHeight * scale)

  return [
    h1('Data Flow Diagram'),
    spacer(),
    new Paragraph({
      children: [
        new ImageRun({
          data: diagramImage,
          transformation: { width: displayWidth, height: displayHeight },
          type: 'png',
        }),
      ],
    }),
    spacer(),
  ]
}

// ---------------------------------------------------------------------------
// Section: System Information
// ---------------------------------------------------------------------------

function buildSystemInfoSection(systemContext: GuestSystemContext, sectionNum: number): (Paragraph | Table)[] {
  const children: (Paragraph | Table)[] = [h1(`${sectionNum}. System Information`), spacer()]

  if (systemContext.systemInfo.description) {
    children.push(
      h2(`${sectionNum}.1 Description`),
      spacer(),
      para(systemContext.systemInfo.description),
      spacer(),
    )
  }

  children.push(
    h2(`${sectionNum}.2 Criticality`),
    spacer(),
    para(capitalize(systemContext.systemInfo.criticality), { bold: true }),
    spacer(),
  )

  return children
}

// ---------------------------------------------------------------------------
// Section: Data Assets
// ---------------------------------------------------------------------------

function buildDataAssetsSection(systemContext: GuestSystemContext, sectionNum: number): (Paragraph | Table)[] {
  const children: (Paragraph | Table)[] = [h1(`${sectionNum}. Data Assets`), spacer()]

  if (systemContext.dataAssets.length === 0) {
    children.push(
      para('No data assets have been defined.', { italic: true }),
      spacer(),
    )
    return children
  }

  children.push(
    buildTable(
      [1800, 1560, 2400, 1080, 1080, 1080, 1360],
      ['Name', 'Classification', 'Description', 'C', 'I', 'A', 'Sensitivity'],
      systemContext.dataAssets.map((asset) => [
        asset.name,
        capitalize(asset.classification),
        asset.description || '—',
        capitalize(asset.confidentiality),
        capitalize(asset.integrity),
        capitalize(asset.availability),
        asset.dataSensitivity.length > 0 ? asset.dataSensitivity.join(', ') : '—',
      ]),
    ),
    spacer(),
  )

  return children
}

// ---------------------------------------------------------------------------
// Section: Assumptions
// ---------------------------------------------------------------------------

function buildAssumptionsSection(systemContext: GuestSystemContext, sectionNum: number): (Paragraph | Table)[] {
  const children: (Paragraph | Table)[] = [h1(`${sectionNum}. Assumptions`), spacer()]

  if (systemContext.assumptions.length === 0) {
    children.push(
      para('No assumptions have been documented.', { italic: true }),
      spacer(),
    )
    return children
  }

  children.push(
    buildTable(
      [4680, 1800, 2880],
      ['Description', 'Validity', 'Topics'],
      systemContext.assumptions.map((assumption) => [
        assumption.description,
        capitalize(assumption.validity),
        assumption.topics.length > 0 ? assumption.topics.join(', ') : '—',
      ]),
    ),
    spacer(),
  )

  return children
}

// ---------------------------------------------------------------------------
// Section: Out of Scope
// ---------------------------------------------------------------------------

function buildOutOfScopeSection(systemContext: GuestSystemContext, sectionNum: number): (Paragraph | Table)[] {
  const children: (Paragraph | Table)[] = [h1(`${sectionNum}. Out of Scope`), spacer()]

  if (systemContext.outOfScopeItems.length === 0) {
    children.push(
      para('No out-of-scope items have been documented.', { italic: true }),
      spacer(),
    )
    return children
  }

  children.push(
    buildTable(
      [4680, 4680],
      ['Item', 'Reason'],
      systemContext.outOfScopeItems.map((item) => [
        item.name,
        item.reason || '—',
      ]),
    ),
    spacer(),
  )

  return children
}

// ---------------------------------------------------------------------------
// Section: Component Inventory
// ---------------------------------------------------------------------------

function buildComponentInventorySection(data: GuestReportData, sectionNum: number): (Paragraph | Table)[] {
  const children: (Paragraph | Table)[] = [h1(`${sectionNum}. Component Inventory`), spacer()]

  // Group nodes by type — exclude container types (trustZone, systemScope)
  const componentNodes = data.nodes.filter(
    (n) => n.type !== 'trustZone' && n.type !== 'systemScope',
  )

  if (componentNodes.length > 0) {
    children.push(
      h2(`${sectionNum}.1 Components`),
      spacer(),
      buildTable(
        [3120, 2160, 4080],
        ['Name', 'Type', 'Description'],
        componentNodes.map((node) => {
          const nodeData = node.data as { label?: string; description?: string; actorType?: string }
          const typeName = formatNodeType(node.type)
          const displayType = node.type === 'humanActor' && nodeData.actorType
            ? `${typeName}\n(${formatActorType(nodeData.actorType)})`
            : typeName
          return [
            nodeData.label ?? '—',
            displayType,
            nodeData.description ?? '—',
          ]
        }),
      ),
      spacer(),
    )
  } else {
    children.push(
      para('No components have been added to the diagram.', { italic: true }),
      spacer(),
    )
  }

  // Data flows
  const dataFlows = data.edges.filter(isDataFlowEdge)
  if (dataFlows.length > 0) {
    children.push(
      h2(`${sectionNum}.2 Data Flows`),
      spacer(),
      buildTable(
        [3120, 3120, 3120],
        ['Name', 'Source', 'Destination'],
        dataFlows.map((edge) => {
          const edgeData = edge.data as { label?: string }
          const sourceName = resolveTargetName(edge.source, data.nodes, data.edges)
          const destName = resolveTargetName(edge.target, data.nodes, data.edges)
          return [edgeData?.label ?? '—', sourceName, destName]
        }),
      ),
      spacer(),
    )
  }

  return children
}

// ---------------------------------------------------------------------------
// Section 3: Threat Analysis
// ---------------------------------------------------------------------------

function buildThreatAnalysisSection(data: GuestReportData, sectionNum: number): (Paragraph | Table)[] {
  const children: (Paragraph | Table)[] = [h1(`${sectionNum}. Threat Analysis`), spacer()]

  if (data.threats.length === 0) {
    children.push(
      para('No threats have been identified.', { italic: true }),
      spacer(),
    )
    return children
  }

  // Summary stats
  const severityCounts: Record<string, number> = { critical: 0, high: 0, medium: 0, low: 0 }
  const strideCounts: Record<string, number> = {}
  const statusCounts: Record<string, number> = { open: 0, accept: 0, mitigate: 0, delegate: 0, eliminate: 0 }

  for (const threat of data.threats) {
    severityCounts[threat.severity] = (severityCounts[threat.severity] ?? 0) + 1
    const threatStatus = threat.status || 'open'
    statusCounts[threatStatus] = (statusCounts[threatStatus] ?? 0) + 1
    if (threat.category) {
      const label = formatStrideCategory(threat.category)
      strideCounts[label] = (strideCounts[label] ?? 0) + 1
    }
  }

  let subSectionNum = 1

  children.push(
    h2(`${sectionNum}.${subSectionNum} Summary`),
    spacer(),
    buildTable(
      [4680, 4680],
      ['Severity', 'Count'],
      [
        ['Critical', String(severityCounts.critical)],
        ['High', String(severityCounts.high)],
        ['Medium', String(severityCounts.medium)],
        ['Low', String(severityCounts.low)],
        ['Total', String(data.threats.length)],
      ],
    ),
    spacer(),
  )
  subSectionNum++

  // Status distribution
  children.push(
    h2(`${sectionNum}.${subSectionNum} Status Distribution`),
    spacer(),
    buildTable(
      [4680, 4680],
      ['Status', 'Count'],
      GUEST_THREAT_STATUS_OPTIONS.map((opt) => [
        opt.label,
        String(statusCounts[opt.value] ?? 0),
      ]),
    ),
    spacer(),
  )
  subSectionNum++

  // STRIDE distribution
  if (Object.keys(strideCounts).length > 0) {
    children.push(
      h2(`${sectionNum}.${subSectionNum} STRIDE Distribution`),
      spacer(),
      buildTable(
        [4680, 4680],
        ['STRIDE Category', 'Count'],
        Object.entries(strideCounts).map(([category, count]) => [category, String(count)]),
      ),
      spacer(),
    )
    subSectionNum++
  }

  // Main threats table with Status and Rationale columns
  children.push(
    h2(`${sectionNum}.${subSectionNum} Threat Details`),
    spacer(),
    buildTable(
      [1800, 1440, 1200, 900, 900, 1560, 1560],
      ['Threat Name', 'Target', 'STRIDE', 'Severity', 'Status', 'Rationale', 'Description'],
      data.threats.map((threat) => [
        threat.name,
        resolveTargetName(threat.targetId, data.nodes, data.edges),
        formatStrideCategory(threat.category),
        capitalize(threat.severity),
        formatThreatStatus(threat.status),
        threat.decisionRationale || '—',
        threat.description || '—',
      ]),
    ),
    spacer(),
  )

  return children
}

// ---------------------------------------------------------------------------
// Section 4: Countermeasures
// ---------------------------------------------------------------------------

function buildCountermeasuresSection(data: GuestReportData, sectionNum: number): (Paragraph | Table)[] {
  const children: (Paragraph | Table)[] = [h1(`${sectionNum}. Countermeasures`), spacer()]

  if (data.countermeasures.length === 0) {
    children.push(
      para('No countermeasures have been defined.', { italic: true }),
      spacer(),
    )
    return children
  }

  // Summary by control function
  const controlFunctionCounts: Record<string, number> = {}
  for (const cm of data.countermeasures) {
    for (const fn of cm.controlFunction) {
      const label = capitalize(fn)
      controlFunctionCounts[label] = (controlFunctionCounts[label] ?? 0) + 1
    }
  }

  // Summary by control nature
  const controlNatureCounts: Record<string, number> = {}
  for (const cm of data.countermeasures) {
    const label = capitalize(cm.controlNature)
    controlNatureCounts[label] = (controlNatureCounts[label] ?? 0) + 1
  }

  children.push(
    h2(`${sectionNum}.1 Summary by Function`),
    spacer(),
    buildTable(
      [4680, 4680],
      ['Control Function', 'Count'],
      [
        ...Object.entries(controlFunctionCounts).map(([type, count]) => [type, String(count)]),
      ],
    ),
    spacer(),
    h2(`${sectionNum}.2 Summary by Nature`),
    spacer(),
    buildTable(
      [4680, 4680],
      ['Control Nature', 'Count'],
      [
        ...Object.entries(controlNatureCounts).map(([type, count]) => [type, String(count)]),
        ['Total Countermeasures', String(data.countermeasures.length)],
      ],
    ),
    spacer(),
  )

  // Build a threat lookup map
  const threatMap = new Map(data.threats.map((t) => [t.id, t]))

  // Main countermeasures table
  children.push(
    h2(`${sectionNum}.3 Countermeasure Details`),
    spacer(),
    buildTable(
      [1800, 1560, 1200, 1800, 3000],
      ['Countermeasure', 'Control Function', 'Control Nature', 'Associated Threat', 'Description'],
      data.countermeasures.map((cm) => {
        const associatedThreat = threatMap.get(cm.threatId)
        return [
          cm.name,
          cm.controlFunction.map(capitalize).join(', '),
          capitalize(cm.controlNature),
          associatedThreat?.name ?? '—',
          cm.description || '—',
        ]
      }),
    ),
    spacer(),
  )

  return children
}

// ---------------------------------------------------------------------------
// Section 5: Coverage Summary
// ---------------------------------------------------------------------------

function buildCoverageSummarySection(data: GuestReportData, sectionNum: number): (Paragraph | Table)[] {
  const children: (Paragraph | Table)[] = [h1(`${sectionNum}. Coverage Summary`), spacer()]

  if (data.threats.length === 0) {
    children.push(
      para('No threats have been identified — coverage analysis is not applicable.', { italic: true }),
      spacer(),
    )
    return children
  }

  // Count countermeasures per threat
  const countermeasuresByThreat = new Map<string, number>()
  for (const cm of data.countermeasures) {
    countermeasuresByThreat.set(cm.threatId, (countermeasuresByThreat.get(cm.threatId) ?? 0) + 1)
  }

  const rows = data.threats.map((threat) => {
    const cmCount = countermeasuresByThreat.get(threat.id) ?? 0
    const threatStatus = threat.status || 'open'
    // Only "mitigate" threats require countermeasures for coverage
    const needsCoverage = threatStatus === 'mitigate'
    let coveredLabel: string
    if (!needsCoverage) {
      coveredLabel = `N/A (${formatThreatStatus(threatStatus)})`
    } else {
      coveredLabel = cmCount > 0 ? 'Yes' : 'No'
    }
    return [
      threat.name,
      capitalize(threat.severity),
      formatThreatStatus(threatStatus),
      String(cmCount),
      coveredLabel,
    ]
  })

  // Only count gaps for threats with "mitigate" status
  const mitigateThreats = data.threats.filter((t) => (t.status || 'open') === 'mitigate')
  const gapCount = mitigateThreats.filter((t) => !countermeasuresByThreat.has(t.id)).length

  children.push(
    buildTable(
      [2400, 1200, 1200, 1800, 2760],
      ['Threat Name', 'Severity', 'Status', '# Countermeasures', 'Covered?'],
      rows,
    ),
    spacer(),
  )

  if (mitigateThreats.length === 0) {
    children.push(
      para('No threats are set to "Mitigate" status — countermeasure coverage analysis is not applicable.', { italic: true }),
      spacer(),
    )
  } else if (gapCount > 0) {
    children.push(
      para(`${gapCount} threat${gapCount > 1 ? 's' : ''} with "Mitigate" status without countermeasures — review recommended.`, { bold: true }),
      spacer(),
    )
  } else {
    children.push(
      para('All threats with "Mitigate" status have at least one countermeasure.', { italic: true }),
      spacer(),
    )
  }

  return children
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export async function exportGuestWordDoc(data: GuestReportData): Promise<void> {
  const systemContext = data.systemContext
  const hasSystemContext = systemContext && (
    systemContext.systemInfo.description ||
    systemContext.dataAssets.length > 0 ||
    systemContext.assumptions.length > 0 ||
    systemContext.outOfScopeItems.length > 0
  )

  // Title page
  const children: (Paragraph | Table)[] = [
    new Paragraph({
      heading: HeadingLevel.TITLE,
      children: [new TextRun({ text: data.title })],
    }),
    new Paragraph({
      children: [
        new TextRun({
          text: 'Threat Model Report (Guest)',
          size: 28,
          color: '444444',
        }),
      ],
    }),
    new Paragraph({
      children: [
        new TextRun({
          text: `Generated: ${new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}`,
          size: 24,
          color: '888888',
        }),
      ],
    }),
  ]

  // Session metadata on title page
  if (systemContext) {
    if (systemContext.session.facilitator) {
      children.push(
        new Paragraph({
          children: [
            new TextRun({ text: `Facilitator: ${systemContext.session.facilitator}`, size: 22, color: '666666' }),
          ],
        }),
      )
    }
    if (systemContext.session.participants.length > 0) {
      children.push(
        new Paragraph({
          children: [
            new TextRun({ text: `Participants: ${systemContext.session.participants.join(', ')}`, size: 22, color: '666666' }),
          ],
        }),
      )
    }
    if (systemContext.session.meetingDate) {
      children.push(
        new Paragraph({
          children: [
            new TextRun({ text: `Meeting Date: ${systemContext.session.meetingDate}`, size: 22, color: '666666' }),
          ],
        }),
      )
    }
  }

  children.push(
    spacer(),
    para('Generated from Precogly Guest Editor', { italic: true, size: 20 }),
    pageBreak(),
  )

  // Dynamic section numbering
  let sectionNum = 1

  // 1. Diagram Overview
  children.push(...buildOverviewSection(data, sectionNum++))

  // System Information (if present)
  if (hasSystemContext && systemContext.systemInfo.description) {
    children.push(...buildSystemInfoSection(systemContext, sectionNum++))
  }

  // Data Assets (if present)
  if (hasSystemContext && systemContext.dataAssets.length > 0) {
    children.push(...buildDataAssetsSection(systemContext, sectionNum++))
  }

  // DFD Image
  if (data.diagramImage) {
    children.push(...buildDiagramImageSection(data.diagramImage), pageBreak())
  } else {
    children.push(pageBreak())
  }

  // Component Inventory
  children.push(...buildComponentInventorySection(data, sectionNum++))
  children.push(pageBreak())

  // Threat Analysis
  children.push(...buildThreatAnalysisSection(data, sectionNum++))
  children.push(pageBreak())

  // Countermeasures
  children.push(...buildCountermeasuresSection(data, sectionNum++))
  children.push(pageBreak())

  // Coverage Summary
  children.push(...buildCoverageSummarySection(data, sectionNum++))

  // Assumptions (if present)
  if (hasSystemContext && systemContext.assumptions.length > 0) {
    children.push(pageBreak())
    children.push(...buildAssumptionsSection(systemContext, sectionNum++))
  }

  // Out of Scope (if present)
  if (hasSystemContext && systemContext.outOfScopeItems.length > 0) {
    children.push(pageBreak())
    children.push(...buildOutOfScopeSection(systemContext, sectionNum++))
  }

  const doc = new Document({
    styles: createDocumentStyles(),
    numbering: createNumberingConfig(),
    sections: [
      {
        properties: createPageProperties(),
        children,
      },
    ],
  })

  await downloadDocx(doc, `${slugify(data.title)}-guest-threat-model-report.docx`)
}
