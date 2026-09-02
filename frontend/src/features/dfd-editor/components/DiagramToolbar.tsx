import { memo, useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { XYPosition } from '@xyflow/react'
import { User, Server, Cog, Database, Shield, Box, ArrowUp, LayoutTemplate, ShieldAlert, ShieldCheck, ImageDown, Undo2, Redo2, StickyNote, HelpCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { OwlMark } from '@/features/ai/components/OwlMark'
import { AI_PROVIDER_SETTINGS_PATH } from '@/features/ai/constants'
import type { DiagramNodeType } from '../types'
import type { DFDNotationStyle } from '../types/notation'
import { useCreateNode } from '../hooks/useCreateNode'
import { ExportImageDialog } from './ExportImageDialog'
import type { ExportImageOptions } from '../lib/export-diagram-image'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'

interface DiagramToolbarProps {
  connectionMode: boolean
  onConnectionModeChange: (enabled: boolean) => void
  boundaryMode: boolean
  onBoundaryModeChange: (enabled: boolean) => void
  getCanvasCenterPosition: () => XYPosition
  onOpenTemplates: () => void
  onOpenThreatAnalysis: () => void
  onOpenGenerateDFD?: () => void
  hideTemplates?: boolean
  hideAnalyzeThreats?: boolean
  hideGenerateDFD?: boolean
  notationStyle?: DFDNotationStyle
  onNotationChange?: (notation: DFDNotationStyle) => void
  onExportImage?: (format: 'png' | 'svg', options?: ExportImageOptions) => void | Promise<void>
  onUndo?: () => void
  onRedo?: () => void
  canUndo?: boolean
  canRedo?: boolean
  aiAvailable?: boolean
}

interface ToolbarButtonConfig {
  type: DiagramNodeType
  label: string
  icon: React.ComponentType<{ className?: string }>
  color: string
  description: string
}

const nodeButtons: ToolbarButtonConfig[] = [
  {
    type: 'humanActor',
    label: 'Human Actor',
    icon: User,
    color: 'text-green-600 hover:bg-green-50',
    description: 'External human user: customer, admin, attacker',
  },
  {
    type: 'systemActor',
    label: 'System Actor',
    icon: Server,
    color: 'text-slate-600 hover:bg-slate-50',
    description: 'External system: third-party API, partner system',
  },
  {
    type: 'process',
    label: 'Process',
    icon: Cog,
    color: 'text-blue-600 hover:bg-blue-50',
    description: 'A process, service, or API that handles data',
  },
  {
    type: 'datastore',
    label: 'Data Store',
    icon: Database,
    color: 'text-purple-600 hover:bg-purple-50',
    description: 'Database, file system, or cache that stores data',
  },
  {
    type: 'trustZone',
    label: 'Trust Zone',
    icon: Shield,
    color: 'text-orange-600 hover:bg-orange-50',
    description: 'Security zone with specific trust level (e.g., DMZ, VPC)',
  },
  {
    type: 'systemScope',
    label: 'System Scope',
    icon: Box,
    color: 'text-gray-600 hover:bg-gray-50',
    description: 'Visual grouping for related components (defines analysis scope)',
  },
  {
    type: 'stickyNote',
    label: 'Sticky Note',
    icon: StickyNote,
    color: 'text-amber-700 hover:bg-amber-50',
    description: 'Add a movable note to document design decisions or context',
  },
]

const KEYBOARD_SHORTCUTS = [
  ['Ctrl/Cmd + S', 'Save the diagram'],
  ['Ctrl/Cmd + Z', 'Undo the last change'],
  ['Ctrl/Cmd + Shift + Z or Ctrl/Cmd + Y', 'Redo the last undone change'],
  ['Ctrl/Cmd + A', 'Select all nodes and edges'],
  ['Ctrl/Cmd + C', 'Copy selected nodes'],
  ['Ctrl/Cmd + V', 'Paste copied nodes or clipboard text into a selected node'],
  ['Ctrl/Cmd + D', 'Duplicate selected nodes'],
  ['Delete / Backspace', 'Delete selected nodes or edges'],
  ['Escape', 'Deselect and cancel the active interaction'],
]

export const DiagramToolbar = memo(function DiagramToolbar({
  connectionMode,
  onConnectionModeChange,
  boundaryMode,
  onBoundaryModeChange,
  getCanvasCenterPosition,
  onOpenTemplates,
  onOpenThreatAnalysis,
  onOpenGenerateDFD,
  hideTemplates,
  hideAnalyzeThreats,
  hideGenerateDFD,
  notationStyle = 'dfd3',
  onNotationChange,
  onExportImage,
  aiAvailable = true,
  onUndo,
  onRedo,
  canUndo = false,
  canRedo = false,
}: DiagramToolbarProps) {
  const navigate = useNavigate()
  const { createNode } = useCreateNode(notationStyle)
  const [exportDialogOpen, setExportDialogOpen] = useState(false)
  const [shortcutsOpen, setShortcutsOpen] = useState(false)

  useEffect(() => {
    const handleShortcutHelp = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement
      if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable) return
      if (event.key === '?') {
        event.preventDefault()
        setShortcutsOpen(true)
      }
    }
    window.addEventListener('keydown', handleShortcutHelp)
    return () => window.removeEventListener('keydown', handleShortcutHelp)
  }, [])

  const handleAddNode = useCallback(
    (type: DiagramNodeType) => {
      const center = getCanvasCenterPosition()
      createNode(type, center)
    },
    [createNode, getCanvasCenterPosition]
  )

  const handleDragStart = useCallback(
    (event: React.DragEvent, nodeType: DiagramNodeType) => {
      event.dataTransfer.setData('application/reactflow-node-type', nodeType)
      event.dataTransfer.effectAllowed = 'move'
    },
    []
  )

  return (
    <TooltipProvider delayDuration={300}>
      <div className="flex items-center gap-1 p-2 bg-background border-b">
        {/* Node buttons with Trust Boundary placed after Trust Zone */}
        {nodeButtons.flatMap((button) => {
          const nodeBtn = (
            <Tooltip key={button.type}>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className={cn('gap-2 cursor-grab active:cursor-grabbing', button.color)}
                  onClick={() => handleAddNode(button.type)}
                  draggable
                  onDragStart={(e) => handleDragStart(e, button.type)}
                >
                  <button.icon className="h-4 w-4" />
                  <span className="hidden sm:inline">{button.label}</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-[200px]">
                <p className="font-medium">{button.label}</p>
                <p className="text-xs text-muted-foreground">{button.description}</p>
              </TooltipContent>
            </Tooltip>
          )
          if (button.type === 'trustZone') {
            return [
              nodeBtn,
              <Tooltip key="trustBoundary">
                <TooltipTrigger asChild>
                  <Button
                    variant={boundaryMode ? 'default' : 'ghost'}
                    size="sm"
                    className={cn('gap-2', !boundaryMode && 'text-amber-700 hover:bg-amber-50')}
                    onClick={() => onBoundaryModeChange(!boundaryMode)}
                  >
                    <ShieldCheck className="h-4 w-4" />
                    <span className="hidden sm:inline">Trust Boundary</span>
                  </Button>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p className="font-medium">Trust Boundary</p>
                  <p className="text-xs text-muted-foreground">
                    Click two trust zones to create a security boundary between them
                  </p>
                </TooltipContent>
              </Tooltip>,
            ]
          }
          return [nodeBtn]
        })}

        {(onUndo || onRedo) && (
          <div className="flex items-center gap-0.5 ml-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onUndo} disabled={!canUndo} aria-label="Undo">
                  <Undo2 className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">Undo (Ctrl/Cmd + Z)</TooltipContent>
            </Tooltip>
            <Tooltip>
              <TooltipTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onRedo} disabled={!canRedo} aria-label="Redo">
                  <Redo2 className="h-4 w-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">Redo (Ctrl/Cmd + Shift + Z)</TooltipContent>
            </Tooltip>
          </div>
        )}

        {/* Connection mode toggle */}
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant={connectionMode ? 'default' : 'ghost'}
              size="sm"
              className="gap-2"
              onClick={() => onConnectionModeChange(!connectionMode)}
            >
              <ArrowUp className="h-4 w-4" />
              <span className="hidden sm:inline">Flow</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            <p className="font-medium">Draw Connection</p>
            <p className="text-xs text-muted-foreground">
              Click and drag from one node to another to create a data flow. Press ? for shortcuts.
            </p>
          </TooltipContent>
        </Tooltip>

        {onNotationChange && (
          <>
            <Separator orientation="vertical" className="h-8 mx-2" />
            <Select
              value={notationStyle}
              onValueChange={(value) => onNotationChange(value as DFDNotationStyle)}
            >
              <SelectTrigger className="h-8 w-[140px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="dfd3">DFD3</SelectItem>
                <SelectItem value="yourdon">Yourdon</SelectItem>
              </SelectContent>
            </Select>
          </>
        )}

        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8"
              aria-label="Keyboard shortcuts"
              onClick={() => setShortcutsOpen(true)}
            >
              <HelpCircle className="h-4 w-4" />
            </Button>
          </TooltipTrigger>
          <TooltipContent side="bottom">
            <p className="font-medium">Keyboard shortcuts (?)</p>
            <p className="text-xs text-muted-foreground">Show the DFD editor shortcut reference</p>
          </TooltipContent>
        </Tooltip>

        {!hideTemplates && (
          <>
            <Separator orientation="vertical" className="h-8 mx-2" />

            {/* Templates button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={onOpenTemplates}
                >
                  <LayoutTemplate className="h-4 w-4" />
                  <span className="hidden sm:inline">Templates</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <p className="font-medium">DFD Templates</p>
                <p className="text-xs text-muted-foreground">
                  Browse and insert pre-built diagram templates
                </p>
              </TooltipContent>
            </Tooltip>
          </>
        )}

        {!hideGenerateDFD && onOpenGenerateDFD && (
          <>
            <Separator orientation="vertical" className="h-8 mx-2" />

            {/* AI Generate DFD button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className={cn('gap-2', !aiAvailable && 'text-muted-foreground')}
                  onClick={aiAvailable ? onOpenGenerateDFD : () => navigate(AI_PROVIDER_SETTINGS_PATH)}
                >
                  <OwlMark className="h-4 w-4" />
                  <span className="hidden sm:inline">Generate</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                {aiAvailable ? (
                  <>
                    <p className="font-medium">Generate DFD with AI</p>
                    <p className="text-xs text-muted-foreground">
                      Upload an architecture diagram and let AI build a DFD
                    </p>
                  </>
                ) : (
                  <p>Set up an AI provider to use this</p>
                )}
              </TooltipContent>
            </Tooltip>
          </>
        )}

        {!hideAnalyzeThreats && (
          <>
            <Separator orientation="vertical" className="h-8 mx-2" />

            {/* Threat Analysis button */}
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="default"
                  size="sm"
                  className="gap-2"
                  onClick={onOpenThreatAnalysis}
                >
                  <ShieldAlert className="h-4 w-4" />
                  <span className="hidden sm:inline">Analyze Threats</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">
                <p className="font-medium">Analyze Threats & Countermeasures</p>
                <p className="text-xs text-muted-foreground">
                  Review and manage threats based on your diagram components
                </p>
              </TooltipContent>
            </Tooltip>
          </>
        )}

        {onExportImage && (
          <div className="ml-auto">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-2"
                  onClick={() => setExportDialogOpen(true)}
                >
                  <ImageDown className="h-4 w-4" />
                  <span className="hidden sm:inline">Export Image</span>
                </Button>
              </TooltipTrigger>
              <TooltipContent side="bottom">Download diagram as PNG or SVG</TooltipContent>
            </Tooltip>
            <ExportImageDialog
              open={exportDialogOpen}
              onOpenChange={setExportDialogOpen}
              onExport={onExportImage}
            />
          </div>
        )}
      </div>
      <Dialog open={shortcutsOpen} onOpenChange={setShortcutsOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Keyboard shortcuts</DialogTitle>
            <DialogDescription>Shortcuts are active when the canvas is focused and a form field is not being edited.</DialogDescription>
          </DialogHeader>
          <div className="divide-y rounded-md border">
            {KEYBOARD_SHORTCUTS.map(([shortcut, description]) => (
              <div key={shortcut} className="flex items-center justify-between gap-4 px-3 py-2 text-sm">
                <kbd className="rounded border bg-muted px-2 py-1 font-mono text-xs whitespace-nowrap">{shortcut}</kbd>
                <span className="text-right text-muted-foreground">{description}</span>
              </div>
            ))}
          </div>
        </DialogContent>
      </Dialog>
    </TooltipProvider>
  )
})
