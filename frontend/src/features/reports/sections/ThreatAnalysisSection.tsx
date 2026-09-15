import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { TaxonomyBadges } from '@/components/shared/TaxonomyBadges'
import type { ReportThreatAnalysis } from '@/features/reports/types/report'
import { ReportSection } from '../ReportSection'

interface ThreatAnalysisSectionProps {
  threatAnalysis: ReportThreatAnalysis
}

const STATUS_COLORS: Record<string, string> = {
  exposed: 'bg-red-100 text-red-700',
  addressable: 'bg-yellow-100 text-yellow-700',
  mitigated: 'bg-green-100 text-green-700',
}

const CM_STATUS_COLORS: Record<string, string> = {
  gap: 'bg-red-100 text-red-700',
  planned: 'bg-yellow-100 text-yellow-700',
  verified: 'bg-green-100 text-green-700',
  platform: 'bg-green-100 text-green-700',
  waived: 'bg-blue-100 text-blue-700',
}

const SEVERITY_COLORS: Record<string, string> = {
  critical: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  medium: 'bg-yellow-100 text-yellow-700',
  low: 'bg-green-100 text-green-700',
}

export function ThreatAnalysisSection({ threatAnalysis }: ThreatAnalysisSectionProps) {
  const { componentThreats, dataFlowThreats } = threatAnalysis
  const componentGroups = Object.entries(componentThreats)
  const flowGroups = Object.entries(dataFlowThreats)

  if (componentGroups.length === 0 && flowGroups.length === 0) {
    return (
      <ReportSection title="Threat Detail">
        <p className="text-sm text-muted-foreground">No active threats.</p>
      </ReportSection>
    )
  }

  return (
    <ReportSection title="Threat Detail">
      <div className="space-y-6">
        {/* Component threats */}
        {componentGroups.map(([componentName, threats]) => (
          <div key={componentName}>
            <h4 className="font-medium mb-2">{componentName}</h4>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Threat</TableHead>
                  <TableHead>Classifications</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Countermeasures</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {threats.map((threat) => (
                  <TableRow key={threat.id}>
                    <TableCell>
                      <div className="font-medium text-sm">{threat.threatName}</div>
                      <div className="text-xs text-muted-foreground line-clamp-2">
                        {threat.threatDescription}
                      </div>
                    </TableCell>
                    <TableCell>
                      <TaxonomyBadges entries={threat.taxonomyEntries} maxVisible={3} size="sm" />
                    </TableCell>
                    <TableCell>
                      <Badge className={SEVERITY_COLORS[threat.residualSeverity] || ''} variant="outline">
                        {threat.residualSeverity}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={STATUS_COLORS[threat.status] || ''}>
                        {threat.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {threat.countermeasures.map((cm) => (
                          <div key={cm.id} className="flex flex-col">
                            <Badge
                              variant="outline"
                              className={`text-xs ${CM_STATUS_COLORS[cm.status] || ''}`}
                            >
                              {cm.countermeasureName}: {cm.status}
                            </Badge>
                            {cm.complianceStandards && cm.complianceStandards.length > 0 && (
                              <span className="text-[10px] text-muted-foreground ml-1">
                                {cm.complianceStandards.map(s => `${s.frameworkName} ${s.sectionCode}`).join(', ')}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ))}

        {/* Data flow threats */}
        {flowGroups.map(([flowLabel, threats]) => (
          <div key={flowLabel}>
            <h4 className="font-medium mb-2">Flow: {flowLabel}</h4>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Threat</TableHead>
                  <TableHead>Classifications</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Countermeasures</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {threats.map((threat) => (
                  <TableRow key={threat.id}>
                    <TableCell>
                      <div className="font-medium text-sm">{threat.threatName}</div>
                    </TableCell>
                    <TableCell>
                      <TaxonomyBadges entries={threat.taxonomyEntries} maxVisible={3} size="sm" />
                    </TableCell>
                    <TableCell>
                      <Badge className={SEVERITY_COLORS[threat.residualSeverity] || ''} variant="outline">
                        {threat.residualSeverity}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge className={STATUS_COLORS[threat.status] || ''}>
                        {threat.status}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {threat.countermeasures.map((cm) => (
                          <div key={cm.id} className="flex flex-col">
                            <Badge
                              variant="outline"
                              className={`text-xs ${CM_STATUS_COLORS[cm.status] || ''}`}
                            >
                              {cm.countermeasureName}: {cm.status}
                            </Badge>
                            {cm.complianceStandards && cm.complianceStandards.length > 0 && (
                              <span className="text-[10px] text-muted-foreground ml-1">
                                {cm.complianceStandards.map(s => `${s.frameworkName} ${s.sectionCode}`).join(', ')}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ))}
      </div>
    </ReportSection>
  )
}
