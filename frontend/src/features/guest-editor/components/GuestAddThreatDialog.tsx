import { useState, useEffect } from 'react'
import { Plus, Check, AlertTriangle } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useGuestEditor } from '../context/GuestEditorContext'
import type { GuestThreat, ThreatStatus } from '../types'
import { GUEST_THREAT_STATUS_OPTIONS, RATIONALE_REQUIRED_STATUSES } from '../types'
import { STRIDE_CATEGORIES, type STRIDECategory } from '@/types/domain'

const SEVERITY_OPTIONS = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'critical', label: 'Critical' },
]

interface GuestThreatDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  targetId: string
  targetType: GuestThreat['targetType']
  targetName: string
  /** When provided, the dialog operates in edit mode */
  editThreat?: GuestThreat
}

export function GuestThreatDialog({
  open,
  onOpenChange,
  targetId,
  targetType,
  targetName,
  editThreat,
}: GuestThreatDialogProps) {
  const guestEditor = useGuestEditor()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [severity, setSeverity] = useState<GuestThreat['severity']>('medium')
  const [category, setCategory] = useState('')
  const [status, setStatus] = useState<ThreatStatus>('open')
  const [decisionRationale, setDecisionRationale] = useState('')

  const [confirmMessage, setConfirmMessage] = useState<string | null>(null)

  const isEditMode = !!editThreat
  const rationaleRequired = RATIONALE_REQUIRED_STATUSES.includes(status)
  const showRationaleWarning = rationaleRequired && !decisionRationale.trim()

  // Pre-fill fields when editing or reset when adding
  useEffect(() => {
    if (open) {
      if (editThreat) {
        setName(editThreat.name)
        setDescription(editThreat.description)
        setSeverity(editThreat.severity)
        setCategory(editThreat.category || '')
        setStatus(editThreat.status || 'open')
        setDecisionRationale(editThreat.decisionRationale || '')
      } else {
        setName('')
        setDescription('')
        setSeverity('medium')
        setCategory('')
        setStatus('open')
        setDecisionRationale('')
      }
    }
  }, [open, editThreat])

  const handleSubmit = () => {
    if (!name.trim() || !guestEditor) return

    // If rationale is required but empty, show confirmation dialog
    if (showRationaleWarning) {
      const statusLabel = GUEST_THREAT_STATUS_OPTIONS.find((o) => o.value === status)?.label ?? status
      setConfirmMessage(
        `A decision rationale is recommended for "${statusLabel}" status. Are you sure you want to proceed without one?`
      )
      return
    }

    // If status is "mitigate", warn about countermeasures
    if (status === 'mitigate') {
      const countermeasureCount = isEditMode
        ? guestEditor.getCountermeasureCount(editThreat.id)
        : 0
      if (countermeasureCount === 0) {
        setConfirmMessage(
          isEditMode
            ? 'This threat has no countermeasures yet. At least one countermeasure is expected for "Mitigate" status. You can add countermeasures in the Threat Analysis view.'
            : 'At least one countermeasure is expected for "Mitigate" status. You can add countermeasures in the Threat Analysis view after saving.'
        )
        return
      }
    }

    commitThreat()
  }

  const commitThreat = () => {
    if (!name.trim() || !guestEditor) return

    if (isEditMode) {
      guestEditor.updateThreat(editThreat.id, {
        name: name.trim(),
        description: description.trim(),
        severity,
        category: (category as STRIDECategory) || undefined,
        status,
        decisionRationale: decisionRationale.trim() || undefined,
      })
    } else {
      guestEditor.addThreat(
        targetId,
        targetType,
        name.trim(),
        description.trim(),
        severity,
        (category as STRIDECategory) || undefined,
        status,
        decisionRationale.trim() || undefined
      )
    }
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{isEditMode ? 'Edit Threat' : 'Add Threat'}</DialogTitle>
          <DialogDescription>
            {isEditMode ? `Editing threat on ${targetName}` : `Add a threat to ${targetName}`}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="threat-name">Threat Name *</Label>
            <Input
              id="threat-name"
              placeholder="Enter threat name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && name.trim()) handleSubmit()
              }}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="threat-description">Description</Label>
            <Textarea
              id="threat-description"
              placeholder="Describe the threat..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="threat-severity">Severity *</Label>
            <Select value={severity} onValueChange={(v) => setSeverity(v as GuestThreat['severity'])}>
              <SelectTrigger id="threat-severity">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {SEVERITY_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="threat-category">STRIDE Category</Label>
            <Select
              value={category || 'none'}
              onValueChange={(value) => setCategory(value === 'none' ? '' : value)}
            >
              <SelectTrigger id="threat-category">
                <SelectValue placeholder="Select a category..." />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">None</SelectItem>
                {STRIDE_CATEGORIES.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="threat-status">Status *</Label>
            <Select value={status} onValueChange={(v) => setStatus(v as ThreatStatus)}>
              <SelectTrigger id="threat-status">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {GUEST_THREAT_STATUS_OPTIONS.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    <div>
                      <span>{opt.label}</span>
                      <span className="ml-2 text-muted-foreground text-xs">{opt.description}</span>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {status !== 'open' && (
            <div className="space-y-2">
              <Label htmlFor="threat-rationale">
                Decision Rationale {rationaleRequired ? '*' : '(optional)'}
              </Label>
              <Textarea
                id="threat-rationale"
                placeholder="Explain the rationale for this decision..."
                value={decisionRationale}
                onChange={(e) => setDecisionRationale(e.target.value)}
                rows={2}
              />
              {showRationaleWarning && (
                <div className="flex items-center gap-1.5 text-amber-600 text-xs">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                  <span>Rationale is recommended for &ldquo;{status}&rdquo; status</span>
                </div>
              )}
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!name.trim()}>
            {isEditMode ? (
              <>
                <Check className="h-4 w-4 mr-2" />
                Save
              </>
            ) : (
              <>
                <Plus className="h-4 w-4 mr-2" />
                Add Threat
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>

      <AlertDialog open={confirmMessage !== null} onOpenChange={(open) => { if (!open) setConfirmMessage(null) }}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {showRationaleWarning ? 'Missing Decision Rationale' : 'Countermeasures Required'}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirmMessage}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Go Back</AlertDialogCancel>
            <AlertDialogAction onClick={commitThreat}>
              {showRationaleWarning ? 'Proceed Anyway' : 'Proceed'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Dialog>
  )
}
