/**
 * TechnologyIcon renders the icon for a diagram technology.
 *
 * Resolution order (first match wins):
 *   1. `technology.componentIcon` — icon declared on the component itself
 *      (per-service override, e.g. an AWS Lambda component that opts into a
 *      lambda-specific glyph instead of the generic AWS logo).
 *   2. `technology.packIcon` — icon inherited from the source pack.
 *   3. Vendor default — AWS/Azure/GCP brand logo based on `technology.vendor`.
 *   4. `fallback` prop (typically a lucide category icon).
 */
import type { ComponentType, SVGProps } from 'react'
import { PackIcon } from '@/features/libraries/components/PackIcon'
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

export function TechnologyIcon({ technology, fallback, ...rest }: TechnologyIconProps) {
  if (!technology) {
    const Fallback = fallback
    return <Fallback {...rest} />
  }

  if (technology.componentIcon?.slug) {
    return <PackIcon icon={technology.componentIcon} fallback={fallback as never} {...rest} />
  }

  if (technology.packIcon?.slug) {
    return <PackIcon icon={technology.packIcon} fallback={fallback as never} {...rest} />
  }

  const vendorSlug = technology.vendor ? VENDOR_TO_ICON_SLUG[technology.vendor] : undefined
  if (vendorSlug) {
    return <PackIcon slug={vendorSlug} fallback={fallback as never} {...rest} />
  }

  const Fallback = fallback
  return <Fallback {...rest} />
}
