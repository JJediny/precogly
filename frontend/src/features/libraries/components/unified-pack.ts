import type { PackIcon } from '@/features/libraries/types/packs'

// Unified pack type that can represent both source and database packs
export interface UnifiedPack {
  slug: string
  name: string
  description: string
  version: string
  packType: string
  icon?: PackIcon
  tags: string[]
  relativePath: string
  componentCount: number
  threatCount: number
  isInDatabase: boolean
  isImported: boolean
  databaseId: number | null
  dependsOn: Array<{ slug: string; name: string; isImported: boolean }>
}
