import { useState } from 'react'
import { LayoutGrid, Plus, Info } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import type { Diagram } from '@/types'

interface DFDCarouselProps {
  diagrams: Diagram[]
  selectedDiagramId: string | null // null means "All DFDs"
  onSelectDiagram: (diagramId: string | null) => void
  onEditDiagram: (diagramId: string) => void
  onCreateDiagram: () => void
  isCreating?: boolean
}

export function DFDCarousel({
  diagrams,
  selectedDiagramId,
  onSelectDiagram,
  onEditDiagram,
  onCreateDiagram,
  isCreating = false,
}: DFDCarouselProps) {
  const [showReferenceDialog, setShowReferenceDialog] = useState(false)

  const hasPrimaryDfd = diagrams.some((d) => d.isPrimary)

  const handleNewDfdClick = () => {
    if (hasPrimaryDfd) {
      setShowReferenceDialog(true)
    } else {
      onCreateDiagram()
    }
  }

  if (diagrams.length === 0) {
    return null
  }

  return (
    <>
      <div className="flex items-center justify-between gap-4 py-3 px-4 bg-muted/30 rounded-lg">
        {/* Left side: Carousel */}
        <div className="flex items-center gap-2 flex-1 overflow-hidden">
          {/* All DFDs option */}
          <button
            onClick={() => onSelectDiagram(null)}
            className={cn(
              'flex flex-col items-center gap-1 px-3 py-2 rounded-md transition-colors min-w-[100px]',
              selectedDiagramId === null
                ? 'bg-primary text-primary-foreground'
                : 'hover:bg-muted'
            )}
          >
            <div
              className={cn(
                'w-16 h-12 rounded border flex items-center justify-center',
                selectedDiagramId === null
                  ? 'bg-primary-foreground/20 border-primary-foreground/30'
                  : 'bg-background border-border'
              )}
            >
              <LayoutGrid className="h-5 w-5 opacity-50" />
            </div>
            <span className="text-xs font-medium">All DFDs</span>
          </button>

          {/* DFD thumbnails */}
          <div className="flex gap-2 overflow-x-auto">
            {diagrams.map((diagram) => {
              const isSelected = selectedDiagramId === diagram.id
              const canvasData = diagram.canvasData
              const nodeCount = canvasData?.nodes?.length || 0

              return (
                <button
                  key={diagram.id}
                  onClick={() => onEditDiagram(diagram.id)}
                  className={cn(
                    'flex flex-col items-center gap-1 px-3 py-2 rounded-md transition-colors min-w-[100px] cursor-pointer',
                    isSelected
                      ? 'bg-primary text-primary-foreground'
                      : 'hover:bg-muted'
                  )}
                  title={`Open ${diagram.name}`}
                >
                  <div
                    className={cn(
                      'w-16 h-12 rounded border flex items-center justify-center text-xs relative',
                      isSelected
                        ? 'bg-primary-foreground/20 border-primary-foreground/30'
                        : 'bg-background border-border'
                    )}
                  >
                    {diagram.isPrimary && (
                      <span className="absolute -top-1.5 -right-1.5 bg-green-500 text-white text-[8px] font-bold px-1 rounded">
                        P
                      </span>
                    )}
                    <div className="text-center">
                      <div className="font-medium">{nodeCount}</div>
                      <div className="text-[10px] opacity-70">
                        {nodeCount === 1 ? 'node' : 'nodes'}
                      </div>
                    </div>
                  </div>
                  <span className="text-xs font-medium truncate max-w-[90px]">
                    {diagram.name}
                  </span>
                  {!diagram.isPrimary && diagrams.length > 1 && (
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span className="text-[10px] text-muted-foreground flex items-center gap-0.5">
                            Reference
                            <Info className="h-2.5 w-2.5" />
                          </span>
                        </TooltipTrigger>
                        <TooltipContent side="bottom">
                          <p className="text-xs max-w-[200px]">
                            Reference diagrams are not synced to threat analysis.
                            Only the primary DFD generates threats.
                          </p>
                        </TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                  )}
                </button>
              )
            })}
          </div>
        </div>

        {/* Right side: New DFD button */}
        <Button
          onClick={handleNewDfdClick}
          disabled={isCreating}
          className="gap-2 flex-shrink-0"
        >
          <Plus className="h-4 w-4" />
          {isCreating ? 'Creating...' : 'New DFD'}
        </Button>
      </div>

      <AlertDialog open={showReferenceDialog} onOpenChange={setShowReferenceDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Create Reference Diagram</AlertDialogTitle>
            <AlertDialogDescription>
              This threat model already has a primary DFD. The new diagram will be a
              <strong> reference diagram</strong> only. Its components will not be
              synced to threat analysis.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setShowReferenceDialog(false)
                onCreateDiagram()
              }}
            >
              Create Reference DFD
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
