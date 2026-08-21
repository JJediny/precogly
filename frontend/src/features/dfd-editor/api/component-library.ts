/**
 * API hooks for fetching component library (technologies) from installed packs.
 */

import { useQuery } from '@tanstack/react-query'
import { api, getAccessToken } from '@/lib/api'
import type { PackIconConfig } from '@/features/libraries/components/PackIcon'
import type { Technology, TechnologyCategory } from '../lib/technology-registry'

// Backend response type (camelCase from djangorestframework-camel-case middleware)
interface ComponentLibraryItem {
  id: number
  slug: string
  qualifiedSlug: string | null
  name: string
  category: 'process' | 'datastore' | 'external_human_actor' | 'external_system_actor'  // Node type category
  componentType: string  // Technology category (database, compute, etc.)
  provider: string
  icon: PackIconConfig | Record<string, never> | null
  sourcePack: number | null
  sourcePackName: string | null
  sourcePackSlug: string | null
  sourcePackIcon: PackIconConfig | Record<string, never> | null
}

// Map backend provider to frontend vendor
function mapProviderToVendor(provider: string): Technology['vendor'] {
  const providerLower = provider.toLowerCase()
  if (providerLower === 'aws' || providerLower === 'amazon') return 'aws'
  if (providerLower === 'azure' || providerLower === 'microsoft') return 'azure'
  if (providerLower === 'gcp' || providerLower === 'google') return 'gcp'
  return 'generic'
}

// Map backend component_type to frontend TechnologyCategory
function mapComponentTypeToCategory(componentType: string): TechnologyCategory {
  const type = componentType.toLowerCase()

  // Exact matches first
  const exactMap: Record<string, TechnologyCategory> = {
    database: 'database',
    storage: 'storage',
    cache: 'cache',
    compute: 'compute',
    backend: 'backend',
    frontend: 'frontend',
    messaging: 'messaging',
    networking: 'networking',
    security: 'security',
    auth: 'auth',
    monitoring: 'monitoring',
    infrastructure: 'infrastructure',
  }

  if (exactMap[type]) {
    return exactMap[type]
  }

  // Partial matches for descriptive backend values
  if (type.includes('database')) return 'database'
  if (type.includes('storage')) return 'storage'
  if (type.includes('cache')) return 'cache'
  if (type.includes('queue') || type.includes('messaging') || type.includes('event')) return 'messaging'
  if (type.includes('function') || type.includes('lambda') || type.includes('compute') || type.includes('container')) return 'compute'
  if (type.includes('api') || type.includes('gateway') || type.includes('backend') || type.includes('server')) return 'backend'
  if (type.includes('network') || type.includes('vpc') || type.includes('load balancer') || type.includes('cdn')) return 'networking'
  if (type.includes('auth') || type.includes('identity') || type.includes('iam')) return 'auth'
  if (type.includes('security') || type.includes('firewall') || type.includes('waf')) return 'security'
  if (type.includes('monitor') || type.includes('logging') || type.includes('metric')) return 'monitoring'

  return 'other'
}

// Transform backend item to frontend Technology format
function transformToTechnology(item: ComponentLibraryItem): Technology {
  const rawPackIcon = item.sourcePackIcon
  const packIcon =
    rawPackIcon && typeof rawPackIcon === 'object' && 'slug' in rawPackIcon
      ? (rawPackIcon as PackIconConfig)
      : undefined
  const rawComponentIcon = item.icon
  const componentIcon =
    rawComponentIcon && typeof rawComponentIcon === 'object' && 'slug' in rawComponentIcon
      ? (rawComponentIcon as PackIconConfig)
      : undefined
  return {
    id: item.slug || item.qualifiedSlug || String(item.id),
    name: item.name,
    category: mapComponentTypeToCategory(item.componentType),
    vendor: mapProviderToVendor(item.provider),
    description: item.sourcePackName ? `From ${item.sourcePackName}` : undefined,
    componentIcon,
    packIcon,
    sourcePackSlug: item.sourcePackSlug ?? undefined,
  }
}

/**
 * Fetch all available technologies from the component library API.
 * Returns technologies from installed packs for the user's organization.
 * Optionally filtered by a threat model's connected packs.
 */
export function useComponentLibrary(threatModelId?: string, options?: { enabled?: boolean }) {
  return useQuery({
    queryKey: ['component-library', threatModelId],
    queryFn: async () => {
      const params = threatModelId ? `?threat_model=${threatModelId}` : ''
      const items = await api.get<ComponentLibraryItem[]>(`/component-library/${params}`)
      return items.map(transformToTechnology)
    },
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    enabled: options?.enabled ?? true,
  })
}

/**
 * Hook that provides technologies with fallback to empty array if no packs installed.
 * Use this in the TechnologyCombobox component.
 */
export function useTechnologies(threatModelId?: string, options?: { enabled?: boolean }) {
  const { data: technologies = [], isLoading, error } = useComponentLibrary(threatModelId, options)

  return {
    technologies,
    isLoading,
    error,
    isEmpty: !isLoading && technologies.length === 0,
  }
}

/**
 * Resolve a technology value (slug or legacy display name) to its display name.
 * Returns the original value as fallback if no match is found (custom entries).
 * Skips the API fetch when no auth token is present (e.g., guest editor).
 */
export function useTechnologyDisplayName(value: string | undefined): string {
  const hasAuth = !!getAccessToken()
  const { technologies } = useTechnologies(undefined, { enabled: hasAuth })

  if (!value) return ''

  const match = technologies.find(
    (t) => t.id === value || t.name.toLowerCase() === value.toLowerCase()
  )
  return match?.name ?? value
}

/**
 * Resolve a technology value to its full record so callers can access
 * derived data (icon config, vendor, source pack). Returns null when
 * the technology can't be found (e.g. guest editor, custom entries).
 */
export function useTechnologyEntry(value: string | undefined): Technology | null {
  const hasAuth = !!getAccessToken()
  const { technologies } = useTechnologies(undefined, { enabled: hasAuth })

  if (!value) return null

  const match = technologies.find(
    (t) => t.id === value || t.name.toLowerCase() === value.toLowerCase()
  )
  return match ?? null
}
