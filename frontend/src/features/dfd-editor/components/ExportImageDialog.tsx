import { useState } from 'react'
import { useReactFlow, useStoreApi } from '@xyflow/react'
import { toast } from 'sonner'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import type { ExportImageOptions } from '../lib/export-diagram-image'

interface ExportImageDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  onExport: (format: 'png' | 'svg', options: ExportImageOptions) => void | Promise<void>
}

export function ExportImageDialog({ open, onOpenChange, onExport }: ExportImageDialogProps) {
  const [format, setFormat] = useState<'png' | 'svg'>('png')
  const [transparent, setTransparent] = useState(false)
  const [selectedOnly, setSelectedOnly] = useState(false)
  const [exporting, setExporting] = useState(false)
  const { getNodes, getEdges } = useReactFlow()
  const store = useStoreApi()

  // Snapshot on open: getNodes()/getEdges() are non-reactive, and the export
  // itself deselects everything mid-flight — reading on every render would
  // flicker the checkbox while exporting
  const [snapshot, setSnapshot] = useState({ hasNodes: false, hasSelection: false })
  const [wasOpen, setWasOpen] = useState(false)
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) {
      setSnapshot({
        hasNodes: getNodes().length > 0,
        hasSelection:
          getNodes().some((node) => node.selected) || getEdges().some((edge) => edge.selected),
      })
    }
  }
  const { hasNodes, hasSelection } = snapshot

  const handleExport = async () => {
    const nodes = getNodes()
    const edges = getEdges()
    const selectedNodeIds = new Set(nodes.filter((n) => n.selected).map((n) => n.id))
    const selectedEdges = edges.filter((e) => e.selected)

    let excludeIds: Set<string> | undefined
    // Trust the fresh reads, not the open-time snapshot: if the selection is
    // somehow gone, fall back to a full export instead of excluding everything
    const keptNodeIds = new Set(selectedNodeIds)
    for (const edge of selectedEdges) {
      keptNodeIds.add(edge.source)
      keptNodeIds.add(edge.target)
    }
    if (selectedOnly && keptNodeIds.size > 0) {
      // Selected nodes plus the endpoints of explicitly selected edges,
      // so a selected edge is never exported dangling
      excludeIds = new Set([
        ...nodes.filter((n) => !keptNodeIds.has(n.id)).map((n) => n.id),
        // An edge stays when selected itself or when both endpoints are exported
        ...edges
          .filter((e) => !e.selected && !(keptNodeIds.has(e.source) && keptNodeIds.has(e.target)))
          .map((e) => e.id),
      ])
    }

    // Deselect everything so selection borders, delete buttons, and node
    // toolbars don't bake into the capture; 'select' changes bypass undo
    // history and unsaved-changes tracking in both editors' state hooks.
    store.getState().unselectNodesAndEdges()
    setExporting(true)
    try {
      await onExport(format, {
        backgroundColor: transparent ? undefined : '#ffffff',
        excludeIds,
      })
      onOpenChange(false)
    } catch (error) {
      console.error('Image export failed:', error)
      toast.error('Image export failed')
    } finally {
      const { triggerNodeChanges, triggerEdgeChanges } = store.getState()
      if (selectedNodeIds.size > 0) {
        triggerNodeChanges([...selectedNodeIds].map((id) => ({ id, type: 'select' as const, selected: true })))
      }
      if (selectedEdges.length > 0) {
        triggerEdgeChanges(selectedEdges.map((e) => ({ id: e.id, type: 'select' as const, selected: true })))
      }
      setExporting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Export Image</DialogTitle>
          <DialogDescription>Download the diagram cropped to its content.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <RadioGroup
            value={format}
            onValueChange={(value) => setFormat(value as 'png' | 'svg')}
            className="flex gap-6"
          >
            <div className="flex items-center gap-2">
              <RadioGroupItem value="png" id="export-format-png" />
              <Label htmlFor="export-format-png">PNG</Label>
            </div>
            <div className="flex items-center gap-2">
              <RadioGroupItem value="svg" id="export-format-svg" />
              <Label htmlFor="export-format-svg">SVG</Label>
            </div>
          </RadioGroup>

          <div className="flex items-center gap-2">
            <Checkbox
              id="export-transparent"
              checked={transparent}
              onCheckedChange={(checked) => setTransparent(checked === true)}
            />
            <Label htmlFor="export-transparent">Transparent background</Label>
          </div>

          <div className="flex items-center gap-2">
            <Checkbox
              id="export-selected-only"
              checked={selectedOnly && hasSelection}
              disabled={!hasSelection}
              onCheckedChange={(checked) => setSelectedOnly(checked === true)}
            />
            <Label
              htmlFor="export-selected-only"
              className={hasSelection ? undefined : 'text-muted-foreground'}
            >
              Export only selected elements
            </Label>
          </div>
          {!hasSelection && (
            <p className="text-xs text-muted-foreground">
              Select elements on the canvas first to export a subset.
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={exporting}>
            Cancel
          </Button>
          <Button onClick={handleExport} disabled={exporting || !hasNodes}>
            {exporting ? 'Exporting…' : 'Export'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
