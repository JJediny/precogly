/**
 * PackIcon renders a brand/logo icon from `@thesvg/react` by slug.
 *
 * Pass-through resolution — no middleware registry. The `icon` field in
 * `pack.yaml` / `component.icon` is either a bare slug string or a
 * config object. Runtime props override YAML.
 *
 * Look up slugs at https://thesvg.org (kebab-case, e.g. `aws-aws-lambda`).
 * Slugs are shape-validated before the lookup; unknown or malformed slugs
 * render the fallback and warn once in dev.
 *
 * Implementation note: we use `import.meta.glob('/node_modules/@thesvg/react/dist/*.js')`
 * to have Vite pre-index every icon module as a lazy loader. This works
 * for both dev and production because Vite statically analyzes the glob,
 * unlike a bare-specifier dynamic import which fails at runtime in dev.
 */
import { forwardRef, Suspense, use, useMemo, createElement } from 'react'
import type { ComponentType, Ref, SVGProps } from 'react'
import { Package } from 'lucide-react'

import {
  isValidPackIconSlug,
  normalizePackIcon,
  type PackIconValue,
} from './pack-icon-types'

type SvgComponent = ComponentType<SVGProps<SVGSVGElement> & { variant?: string }>

// Vite discovers every icon module at build time. `import: 'default'`
// unwraps the default export so the loader resolves to the component
// directly, without a `.then(m => m.default)` step at call time.
const iconLoaders = import.meta.glob<SvgComponent>(
  '/node_modules/@thesvg/react/dist/*.js',
  { import: 'default' },
)

const iconCache = new Map<string, Promise<SvgComponent>>()
const warned = new Set<string>()

/** Sync: does `@thesvg/react` ship a module for this slug?
 *  Lets callers (e.g. TechnologyIcon) skip an override and try the
 *  next resolver instead of committing to a slug that will fall back. */
export function isKnownPackIconSlug(slug: string | null | undefined): boolean {
  if (!slug) return false
  const normalized = slug.trim().toLowerCase()
  if (!isValidPackIconSlug(normalized)) return false
  return `/node_modules/@thesvg/react/dist/${normalized}.js` in iconLoaders
}

function iconPromise(slug: string): Promise<SvgComponent> {
  const cached = iconCache.get(slug)
  if (cached) return cached
  const loader = iconLoaders[`/node_modules/@thesvg/react/dist/${slug}.js`]
  if (!loader) {
    if (import.meta.env.DEV && !warned.has(slug)) {
      warned.add(slug)
      console.warn(`[PackIcon] Unknown @thesvg/react slug: "${slug}"`)
    }
    const p = Promise.resolve(Package as unknown as SvgComponent)
    iconCache.set(slug, p)
    return p
  }
  const p = loader().catch((err: unknown) => {
    if (import.meta.env.DEV && !warned.has(slug)) {
      warned.add(slug)
      console.warn(`[PackIcon] Failed to load @thesvg/react slug: "${slug}"`, err)
    }
    return Package as unknown as SvgComponent
  })
  iconCache.set(slug, p)
  return p
}

export interface PackIconProps extends Omit<SVGProps<SVGSVGElement>, 'ref'> {
  icon?: PackIconValue
  slug?: string | null
  variant?: string
  fallback?: SvgComponent
  ref?: Ref<SVGSVGElement>
}

/** Inner: assumes slug is validated. Suspends via React.use() until loaded. */
type PackIconInnerProps = Omit<SVGProps<SVGSVGElement>, 'ref'> & {
  effectiveSlug: string
  variant?: string
}

const PackIconInner = forwardRef<SVGSVGElement, PackIconInnerProps>(
  function PackIconInner({ effectiveSlug, ...svgProps }, ref) {
    const Component = use(iconPromise(effectiveSlug))
    return createElement(Component, { ref, ...svgProps })
  },
)

export const PackIcon = forwardRef<SVGSVGElement, PackIconProps>(function PackIcon(
  { icon, slug, variant, fallback, className, style, ...rest },
  ref,
) {
  const config = useMemo(() => normalizePackIcon(icon), [icon])
  const effectiveSlug = (slug ?? config?.slug ?? '').trim().toLowerCase()
  const Fallback = fallback ?? (Package as unknown as SvgComponent)

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

  if (!isValidPackIconSlug(effectiveSlug)) {
    return <Fallback ref={ref} {...merged} />
  }

  return (
    <Suspense fallback={<Fallback ref={ref} {...merged} />}>
      <PackIconInner ref={ref} effectiveSlug={effectiveSlug} {...merged} />
    </Suspense>
  )
})
