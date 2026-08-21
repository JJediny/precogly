/**
 * Card component for displaying a library pack.
 */

import { Check, Eye } from 'lucide-react'
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { LibraryPackListItem } from '@/features/libraries/types/packs'
import { packTypeColors } from '../constants'
import { PackIcon } from './PackIcon'

interface PackCardProps {
  pack: LibraryPackListItem
  onImport: (pack: LibraryPackListItem) => void
  onPreview?: (pack: LibraryPackListItem) => void
  importing?: boolean
}

export function PackCard({ pack, onImport, onPreview, importing }: PackCardProps) {
  return (
    <Card className="flex flex-col h-full">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2">
            <div className="p-2 bg-muted rounded-lg">
              <PackIcon
                icon={pack.icon}
                className="h-5 w-5 text-muted-foreground"
                aria-label={pack.icon ? `${pack.name} icon` : undefined}
              />
            </div>
            <div className="min-w-0">
              <h3 className="font-semibold text-sm truncate">{pack.name}</h3>
              <Badge
                variant="secondary"
                className={`text-xs ${packTypeColors[pack.packType] || ''}`}
              >
                {pack.packType}
              </Badge>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex-1 pb-3">
        <p className="text-sm text-muted-foreground line-clamp-3 mb-3">
          {pack.description}
        </p>
        <div className="flex flex-wrap gap-1">
          {pack.tags.map((tag) => (
            <Badge key={tag} variant="outline" className="text-xs">
              {tag}
            </Badge>
          ))}
        </div>
      </CardContent>
      <CardFooter className="pt-3 border-t flex items-center justify-end">
        <div className="flex items-center gap-1">
          {onPreview && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => onPreview(pack)}
              title="Preview pack contents"
            >
              <Eye className="h-4 w-4" />
            </Button>
          )}
          {pack.isImported ? (
            <Button size="sm" variant="ghost" disabled>
              <Check className="h-4 w-4 mr-1" />
              Imported
            </Button>
          ) : (
            <Button
              size="sm"
              onClick={() => onImport(pack)}
              disabled={importing}
            >
              Import
            </Button>
          )}
        </div>
      </CardFooter>
    </Card>
  )
}
