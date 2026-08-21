/**
 * PackIcon renders a brand/logo icon for a library pack.
 *
 * Icons are sourced from `@thesvg/react`, which exposes ~6,500 brand
 * components as tree-shakeable ES modules. The pack's YAML/DB `icon`
 * field is now a full config object (see `PackIconConfig`), so pack
 * authors can declare defaults for width/height/variant/className/etc.
 * The UI can still override any prop at render time (props win).
 *
 * To add a new pack icon:
 *   1. Find the slug at https://thesvg.org (kebab-case, e.g. "aws").
 *   2. Import the component from `@thesvg/react/<slug>` (or the barrel).
 *   3. Register it in `PACK_ICON_REGISTRY` below.
 *   4. Set `icon: { slug: <slug>, ... }` (or just `icon: <slug>`) in
 *      the pack's `pack.yaml`.
 */
import { forwardRef } from 'react'
import type { ComponentType, CSSProperties, Ref, SVGProps } from 'react'
import { Package } from 'lucide-react'

import Aws from '@thesvg/react/aws'
import AzureIcon from '@thesvg/react/azure'
import Gcp from '@thesvg/react/google-cloud'
import Owasp from '@thesvg/react/owasp'
import EuropeanUnion from '@thesvg/react/european-union'
import AwsLambda from '@thesvg/react/aws-aws-lambda'
import AwsWaf from '@thesvg/react/aws-aws-waf'
import AwsApiGateway from '@thesvg/react/aws-amazon-api-gateway'
import AwsS3 from '@thesvg/react/aws-amazon-simple-storage-service'
import AwsSqs from '@thesvg/react/aws-amazon-simple-queue-service'
import AwsDynamoDb from '@thesvg/react/aws-amazon-dynamodb'
import AwsBedrock from '@thesvg/react/aws-amazon-bedrock'
import AwsOpenSearch from '@thesvg/react/aws-amazon-opensearch-service'
import AwsCognito from '@thesvg/react/aws-amazon-cognito'
import AwsCloudWatch from '@thesvg/react/aws-amazon-cloudwatch'

type SvgComponent = ComponentType<SVGProps<SVGSVGElement> & { variant?: string }>

// Each `@thesvg/react` icon narrows `variant` to a per-icon union. We
// erase that narrowing at the registry boundary since our config passes
// a plain string; the underlying component silently falls back to its
// default variant when the value is unrecognized.
const asSvg = (c: unknown) => c as SvgComponent

export const PACK_ICON_REGISTRY: Record<string, SvgComponent> = {
  aws: asSvg(Aws),
  'aws-logo': asSvg(Aws),
  azure: asSvg(AzureIcon),
  'azure-logo': asSvg(AzureIcon),
  'google-cloud': asSvg(Gcp),
  gcp: asSvg(Gcp),
  'gcp-logo': asSvg(Gcp),
  owasp: asSvg(Owasp),
  'owasp-logo': asSvg(Owasp),
  'european-union': asSvg(EuropeanUnion),
  eu: asSvg(EuropeanUnion),
  'eu-logo': asSvg(EuropeanUnion),
  // AWS service brand marks (used by per-component icon overrides).
  'aws-lambda': asSvg(AwsLambda),
  'aws-waf': asSvg(AwsWaf),
  'aws-api-gateway': asSvg(AwsApiGateway),
  'aws-s3': asSvg(AwsS3),
  'aws-sqs': asSvg(AwsSqs),
  'aws-dynamodb': asSvg(AwsDynamoDb),
  'aws-bedrock': asSvg(AwsBedrock),
  'aws-opensearch': asSvg(AwsOpenSearch),
  'aws-cognito': asSvg(AwsCognito),
  'aws-cloudwatch': asSvg(AwsCloudWatch),
}

/**
 * Config declared in `pack.yaml -> icon:` (either a bare slug string or
 * this object). Matches the JSONField shape stored on `LibraryPack.icon`.
 */
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

export type PackIconValue = string | PackIconConfig | Record<string, never> | null | undefined

/** Runtime props for `<PackIcon>` — anything passed here overrides the
 *  YAML-declared config (props win). */
export interface PackIconProps extends Omit<SVGProps<SVGSVGElement>, 'ref'> {
  /** Icon config from the pack (dict) or a bare slug string. */
  icon?: PackIconValue
  /** Optional slug override (wins over `icon.slug`). */
  slug?: string | null
  /** `@thesvg/react` icon variant, e.g. "mono", "wordmark". */
  variant?: string
  /** Rendered when slug is missing or unknown. Defaults to lucide Package. */
  fallback?: SvgComponent
  ref?: Ref<SVGSVGElement>
}

function normalizeConfig(icon: PackIconValue): PackIconConfig | null {
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

export const PackIcon = forwardRef<SVGSVGElement, PackIconProps>(function PackIcon(
  { icon, slug, variant, fallback, className, style, ...rest },
  ref,
) {
  const config = normalizeConfig(icon)
  const effectiveSlug = (slug ?? config?.slug ?? '').trim().toLowerCase()
  const Registered = effectiveSlug ? PACK_ICON_REGISTRY[effectiveSlug] : undefined
  const Fallback = fallback ?? (Package as unknown as SvgComponent)
  const IconComponent = Registered ?? Fallback

  // Compose YAML defaults + prop overrides. `rest` (raw SVG props from the
  // caller) always wins, so the UI can override any pack-declared value.
  const merged: SVGProps<SVGSVGElement> & { variant?: string } = {
    width: config?.width,
    height: config?.height,
    fill: config?.fill,
    viewBox: config?.viewBox,
    className: [config?.className, className].filter(Boolean).join(' ') || undefined,
    style: config?.style || style ? { ...(config?.style ?? {}), ...(style ?? {}) } : undefined,
    'aria-label': config?.ariaLabel,
    ...rest,
  }
  if (variant ?? config?.variant) {
    merged.variant = variant ?? config?.variant
  }

  return <IconComponent ref={ref} {...merged} />
})

export function resolvePackIcon(icon: PackIconValue): PackIconConfig | null {
  return normalizeConfig(icon)
}

export function hasPackIcon(icon: PackIconValue): boolean {
  const config = normalizeConfig(icon)
  if (!config) return false
  return Boolean(PACK_ICON_REGISTRY[config.slug.toLowerCase()])
}
