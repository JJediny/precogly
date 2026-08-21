/**
 * TechnologyIcon renders the icon for a diagram technology.
 *
 * Rendering:
 *   • When both a service-specific icon and a vendor logo resolve, they
 *     render side-by-side (vendor logo first, then service icon) so the
 *     brand context stays visible next to the specific service glyph.
 *   • Otherwise a single icon is used. A slot is skipped when its slug
 *     is missing or unknown to `@thesvg/react`, so an out-of-date
 *     component override never blocks the pack/vendor icon.
 *
 * Icon resolution:
 *   • Service icon (specific): `technology.componentIcon` → `technology.packIcon`
 *   • Vendor icon (brand):     AWS/Azure/GCP logo from `technology.vendor`
 *   • Fallback: `fallback` prop (usually a lucide category icon).
 */
import type { ComponentType, SVGProps } from 'react'
import { PackIcon, isKnownPackIconSlug } from '@/features/libraries/components/PackIcon'
import type { PackIconConfig } from '@/features/libraries/components/pack-icon-types'
import { cn } from '@/lib/utils'
import type { Technology } from '../../lib/technology-registry'

type SvgComponent = ComponentType<SVGProps<SVGSVGElement>>

const VENDOR_TO_ICON_SLUG: Record<NonNullable<Technology['vendor']>, string | undefined> = {
  aws: 'aws',
  azure: 'azure',
  gcp: 'google-cloud',
  generic: undefined,
}

interface TechnologyIconProps extends SVGProps<SVGSVGElement> {
  technology: Technology | null | undefined
  fallback: SvgComponent
}

function resolveServiceIcon(
  technology: Technology,
): PackIconConfig | undefined {
  const component = technology.componentIcon
  if (component?.slug && isKnownPackIconSlug(component.slug)) return component
  const pack = technology.packIcon
  if (pack?.slug && isKnownPackIconSlug(pack.slug)) return pack
  return undefined
}

function resolveVendorSlug(technology: Technology): string | undefined {
  const slug = technology.vendor ? VENDOR_TO_ICON_SLUG[technology.vendor] : undefined
  return slug && isKnownPackIconSlug(slug) ? slug : undefined
}

export function TechnologyIcon({ technology, fallback, ...rest }: TechnologyIconProps) {
  if (!technology) {
    const Fallback = fallback
    return <Fallback {...rest} />
  }

  const service = resolveServiceIcon(technology)
  const vendorSlug = resolveVendorSlug(technology)

  // Avoid duplicating the vendor logo when the service resolver already
  // returned it (e.g. pack-level icon "aws" and vendor "aws").
  const vendorIsService = service?.slug === vendorSlug

  if (service && vendorSlug && !vendorIsService) {
    const { className, ...svgRest } = rest
    return (
      <span className={cn('inline-flex items-center gap-0.5', className)}>
        <PackIcon slug={vendorSlug} fallback={fallback as never} {...svgRest} />
        <PackIcon icon={service} fallback={fallback as never} {...svgRest} />
      </span>
    )
  }

  if (service) {
    return <PackIcon icon={service} fallback={fallback as never} {...rest} />
  }

  if (vendorSlug) {
    return <PackIcon slug={vendorSlug} fallback={fallback as never} {...rest} />
  }

  const Fallback = fallback
  return <Fallback {...rest} />
}
