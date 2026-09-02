import { useState, useEffect } from 'react'
import { Plus, Check, Info } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
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
import { Checkbox } from '@/components/ui/checkbox'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useGuestEditor } from '../context/GuestEditorContext'
import { GUEST_CONTROL_FUNCTIONS, GUEST_CONTROL_NATURES } from '../types'
import type { GuestCountermeasure, ControlFunction, ControlNature } from '../types'

interface GuestCountermeasureDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  threatId: string
  threatName: string
  editCountermeasure?: GuestCountermeasure
}

export function GuestCountermeasureDialog({
  open,
  onOpenChange,
  threatId,
  threatName,
  editCountermeasure,
}: GuestCountermeasureDialogProps) {
  const guestEditor = useGuestEditor()
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [controlFunction, setControlFunction] = useState<ControlFunction[]>(['preventive'])
  const [controlNature, setControlNature] = useState<ControlNature>('technical')

  const isEditMode = !!editCountermeasure

  useEffect(() => {
    if (open) {
      if (editCountermeasure) {
        setName(editCountermeasure.name)
        setDescription(editCountermeasure.description)
        setControlFunction(editCountermeasure.controlFunction)
        setControlNature(editCountermeasure.controlNature)
      } else {
        setName('')
        setDescription('')
        setControlFunction(['preventive'])
        setControlNature('technical')
      }
    }
  }, [open, editCountermeasure])

  const handleToggleFunction = (value: ControlFunction) => {
    setControlFunction((prev) => {
      if (prev.includes(value)) {
        // Don't allow deselecting the last one
        if (prev.length === 1) return prev
        return prev.filter((f) => f !== value)
      }
      return [...prev, value]
    })
  }

  const handleSubmit = () => {
    if (!name.trim() || !guestEditor || controlFunction.length === 0) return

    if (isEditMode) {
      guestEditor.updateCountermeasure(editCountermeasure.id, {
        name: name.trim(),
        description: description.trim(),
        controlFunction,
        controlNature,
      })
    } else {
      guestEditor.addCountermeasure(threatId, name.trim(), description.trim(), controlFunction, controlNature)
    }
    onOpenChange(false)
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle>
            {isEditMode ? 'Edit Countermeasure' : 'Add Countermeasure'}
          </DialogTitle>
          <DialogDescription>
            {isEditMode
              ? `Editing countermeasure for "${threatName}"`
              : `Add a countermeasure for "${threatName}"`}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="countermeasure-name">Name *</Label>
            <Input
              id="countermeasure-name"
              placeholder="Enter countermeasure name..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && name.trim()) handleSubmit()
              }}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="countermeasure-description">Description</Label>
            <Textarea
              id="countermeasure-description"
              placeholder="Describe the countermeasure..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>

          <div className="space-y-2">
            <Label>Control Function *</Label>
            <p className="text-xs text-muted-foreground">What the control does — select one or more.</p>
            <div className="space-y-1.5 rounded-md border p-3">
              {GUEST_CONTROL_FUNCTIONS.map((opt) => (
                <div key={opt.value} className="flex items-start gap-2">
                  <Checkbox
                    id={`fn-${opt.value}`}
                    checked={controlFunction.includes(opt.value)}
                    onCheckedChange={() => handleToggleFunction(opt.value)}
                    className="mt-0.5"
                  />
                  <label
                    htmlFor={`fn-${opt.value}`}
                    className="flex-1 text-sm leading-tight cursor-pointer select-none"
                  >
                    <span className="font-medium">{opt.label}</span>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Info className="inline-block h-3 w-3 ml-1 text-muted-foreground align-text-top" />
                      </TooltipTrigger>
                      <TooltipContent side="right" className="max-w-[260px]">
                        <p className="text-xs">{opt.description}</p>
                      </TooltipContent>
                    </Tooltip>
                  </label>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="countermeasure-control-nature">Control Nature *</Label>
            <p className="text-xs text-muted-foreground">How the control is implemented.</p>
            <Select
              value={controlNature}
              onValueChange={(v) => setControlNature(v as ControlNature)}
            >
              <SelectTrigger id="countermeasure-control-nature">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {GUEST_CONTROL_NATURES.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>
                    <div className="flex items-center gap-1.5">
                      <span>{opt.label}</span>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Info className="h-3 w-3 text-muted-foreground shrink-0" />
                        </TooltipTrigger>
                        <TooltipContent side="right" className="max-w-[260px]">
                          <p className="text-xs">{opt.description}</p>
                        </TooltipContent>
                      </Tooltip>
                    </div>
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!name.trim() || controlFunction.length === 0}>
            {isEditMode ? (
              <>
                <Check className="h-4 w-4 mr-2" />
                Save
              </>
            ) : (
              <>
                <Plus className="h-4 w-4 mr-2" />
                Add
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
