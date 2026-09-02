import { useState } from 'react'
import { ChevronDown, ChevronUp, X } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ReadOnlyDFDViewer } from '@/components/shared/ReadOnlyDFDViewer'
import type { ReportArchitecture } from '@/features/reports/types/report'
import { ReportSection } from '../ReportSection'

interface ArchitectureSectionProps {
  architecture: ReportArchitecture
}

export function ArchitectureSection({ architecture }: ArchitectureSectionProps) {
  const primaryDfdId = architecture.dfds.find((dfd) => dfd.isPrimary)?.id ?? null
  const [expandedDFDId, setExpandedDFDId] = useState<string | null>(primaryDfdId)

  return (
    <ReportSection title="Architecture">
      <div className="space-y-4">
        {/* DFDs */}
        {architecture.dfds.length > 0 && (
          <div>
            <h4 className="font-medium mb-2">Data Flow Diagrams</h4>
            <div className="space-y-3">
              {architecture.dfds.map((dfd) => {
                const isExpanded = expandedDFDId === dfd.id

                return (
                  <div key={dfd.id} className="border rounded-lg overflow-hidden">
                    <button
                      onClick={() => setExpandedDFDId(isExpanded ? null : dfd.id)}
                      className="w-full flex items-center justify-between p-4 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
                    >
                      <div>
                        <h4 className="font-medium">
                          {dfd.name}
                          {dfd.isPrimary ? (
                            <span className="ml-2 text-xs text-green-600 font-medium">(Primary)</span>
                          ) : (
                            <span className="ml-2 text-xs text-muted-foreground">(Reference)</span>
                          )}
                        </h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          {dfd.nodeCount} components, {dfd.edgeCount} data flows
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-muted-foreground">
                          {isExpanded ? 'Hide diagram' : 'View diagram'}
                        </span>
                        {isExpanded ? (
                          <ChevronUp className="h-5 w-5 text-muted-foreground" />
                        ) : (
                          <ChevronDown className="h-5 w-5 text-muted-foreground" />
                        )}
                      </div>
                    </button>

                    {isExpanded && dfd.canvasData && (
                      <div className="border-t">
                        <div className="p-2 bg-muted/20 flex items-center justify-between">
                          <span className="text-xs text-muted-foreground">
                            Pan and zoom to explore the diagram
                          </span>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setExpandedDFDId(null)}
                          >
                            <X className="h-4 w-4 mr-1" />
                            Close
                          </Button>
                        </div>
                        <ReadOnlyDFDViewer
                          canvasData={dfd.canvasData}
                          className="h-[500px] w-full"
                        />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Trust Zones */}
        {architecture.trustZones.length > 0 && (
          <div>
            <h4 className="font-medium mb-2">Trust Zones</h4>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Name</TableHead>
                  <TableHead className="text-right">Trust Level</TableHead>
                  <TableHead>Description</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {architecture.trustZones.map((zone) => (
                  <TableRow key={zone.id}>
                    <TableCell className="font-medium">{zone.name}</TableCell>
                    <TableCell className="text-right">{zone.trustLevel}</TableCell>
                    <TableCell className="text-muted-foreground">{zone.description}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* Trust Boundaries */}
        {architecture.trustBoundaries.length > 0 && (
          <div>
            <h4 className="font-medium mb-2">Trust Boundaries</h4>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Label</TableHead>
                  <TableHead>Zone A</TableHead>
                  <TableHead>Zone B</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {architecture.trustBoundaries.map((boundary) => (
                  <TableRow key={boundary.id}>
                    <TableCell className="font-medium">{boundary.label}</TableCell>
                    <TableCell>{boundary.zoneA}</TableCell>
                    <TableCell>{boundary.zoneB}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        {/* Reference Images */}
        {architecture.referenceImages.length > 0 && (
          <div>
            <h4 className="font-medium mb-2">Reference Images</h4>
            <div className="space-y-1">
              {architecture.referenceImages.map((img) => (
                <div key={img.id} className="text-sm">
                  <span className="font-medium">{img.filename}</span>
                  {img.description && (
                    <span className="text-muted-foreground"> — {img.description}</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </ReportSection>
  )
}
