/**
 * Shared types + slug validator for pack icons. Kept in a plain-module
 * file so the React component file has only component exports (needed
 * for `react-refresh/only-export-components`).
 */
import type { CSSProperties } from 'react'

const SLUG_PATTERN = /^[a-z0-9][a-z0-9-]{0,79}$/

export interface PackIconConfig {
  slug: string
  variant?: string
  width?: number | string
  height?: number | string
  fill?: string
  viewBox?: string
  className?: string
  style?: CSSProperties
  ariaLabel?: string
}

export type PackIconValue =
  | string
  | PackIconConfig
  | Record<string, never>
  | null
  | undefined

/** True when the value carries a slug matching the pack-icon shape
 *  (kebab-case ASCII, up to 80 chars). */
export function isValidPackIconSlug(value: string | null | undefined): boolean {
  if (!value) return false
  return SLUG_PATTERN.test(value.trim().toLowerCase())
}

export function normalizePackIcon(icon: PackIconValue): PackIconConfig | null {
  if (!icon) return null
  if (typeof icon === 'string') {
    const slug = icon.trim()
    return slug ? { slug } : null
  }
  if (typeof icon !== 'object') return null
  const slug = (icon as PackIconConfig).slug
  if (typeof slug === 'string' && slug.trim()) {
    return { ...(icon as PackIconConfig), slug: slug.trim() }
  }
  return null
}
