import { toPng, toSvg } from 'html-to-image'
import { getViewportForBounds } from '@xyflow/react'
import type { Node, Rect, Viewport } from '@xyflow/react'

const PADDING = 50
const IMAGE_SCALE = 2 // 2x resolution for crisp output

export interface ExportImageOptions {
  /** Solid background color; omitted = transparent background. */
  backgroundColor?: string
  /** Node/edge ids to leave out of the capture (bounds and DOM). */
  excludeIds?: Set<string>
}

/** Filter that excludes React Flow UI overlays from image capture. */
function overlayFilter(node: HTMLElement): boolean {
  if (!node.classList) return true
  return (
    !node.classList.contains('react-flow__minimap') &&
    !node.classList.contains('react-flow__controls') &&
    !node.classList.contains('react-flow__panel') &&
    !node.classList.contains('react-flow__attribution') &&
    !node.classList.contains('react-flow__background')
  )
}

/**
 * Shared helper: reposition viewport to frame the diagram, call the
 * provided capture callback, then restore the original viewport.
 */
async function withExportViewport<T>(
  wrapperElement: HTMLElement,
  nodes: Node[],
  getViewport: () => Viewport,
  setViewport: (viewport: Viewport, options?: { duration?: number }) => void,
  getNodesBounds: (nodes: Node[]) => Rect,
  capture: (reactFlowElement: HTMLElement, paddedBounds: { width: number; height: number }) => Promise<T>,
): Promise<T> {
  if (nodes.length === 0) {
    throw new Error('No nodes to export')
  }

  const reactFlowElement = wrapperElement.querySelector<HTMLElement>('.react-flow')
  if (!reactFlowElement) {
    throw new Error('Could not find React Flow container')
  }

  const nodeBounds = getNodesBounds(nodes)

  const paddedBounds = {
    x: nodeBounds.x - PADDING,
    y: nodeBounds.y - PADDING,
    width: nodeBounds.width + PADDING * 2,
    height: nodeBounds.height + PADDING * 2,
  }

  const exportViewport = getViewportForBounds(
    paddedBounds,
    paddedBounds.width,
    paddedBounds.height,
    0.5,
    2,
    0,
  )

  const originalViewport = getViewport()
  setViewport(exportViewport)

  // Wait for the viewport transform to apply
  await new Promise((resolve) => requestAnimationFrame(resolve))

  try {
    return await capture(reactFlowElement, paddedBounds)
  } finally {
    setViewport(originalViewport)
  }
}

/**
 * Exports the React Flow diagram as a PNG or SVG image and triggers a download.
 */
export async function exportDiagramImage(
  format: 'png' | 'svg',
  filename: string,
  wrapperElement: HTMLElement,
  nodes: Node[],
  getViewport: () => Viewport,
  setViewport: (viewport: Viewport, options?: { duration?: number }) => void,
  getNodesBounds: (nodes: Node[]) => Rect,
  options?: ExportImageOptions,
): Promise<void> {
  const excludeIds = options?.excludeIds
  const exportNodes = excludeIds ? nodes.filter((node) => !excludeIds.has(node.id)) : nodes
  const filter = excludeIds
    ? (node: HTMLElement) => overlayFilter(node) && !excludeIds.has(node.getAttribute?.('data-id') ?? '')
    : overlayFilter

  await withExportViewport(wrapperElement, exportNodes, getViewport, setViewport, getNodesBounds, async (reactFlowElement, paddedBounds) => {
    const convertFn = format === 'png' ? toPng : toSvg
    const dataUrl = await convertFn(reactFlowElement, {
      width: paddedBounds.width,
      height: paddedBounds.height,
      pixelRatio: IMAGE_SCALE, // ignored by toSvg
      backgroundColor: options?.backgroundColor,
      style: {
        width: `${paddedBounds.width}px`,
        height: `${paddedBounds.height}px`,
      },
      filter,
    })

    const extension = format === 'png' ? 'png' : 'svg'
    const anchor = document.createElement('a')
    anchor.href = dataUrl
    anchor.download = `${filename}.${extension}`
    document.body.appendChild(anchor)
    anchor.click()
    document.body.removeChild(anchor)
  })
}

/**
 * Captures the React Flow diagram as a PNG and returns the raw bytes.
 * Used for embedding the diagram image into Word documents.
 */
export async function captureDiagramImage(
  wrapperElement: HTMLElement,
  nodes: Node[],
  getViewport: () => Viewport,
  setViewport: (viewport: Viewport, options?: { duration?: number }) => void,
  getNodesBounds: (nodes: Node[]) => Rect,
): Promise<Uint8Array> {
  return withExportViewport(wrapperElement, nodes, getViewport, setViewport, getNodesBounds, async (reactFlowElement, paddedBounds) => {
    const dataUrl = await toPng(reactFlowElement, {
      width: paddedBounds.width,
      height: paddedBounds.height,
      pixelRatio: IMAGE_SCALE,
      style: {
        width: `${paddedBounds.width}px`,
        height: `${paddedBounds.height}px`,
      },
      filter: overlayFilter,
    })

    // Convert data URL to Uint8Array
    const base64 = dataUrl.split(',')[1]
    const binaryString = atob(base64)
    const bytes = new Uint8Array(binaryString.length)
    for (let i = 0; i < binaryString.length; i++) {
      bytes[i] = binaryString.charCodeAt(i)
    }
    return bytes
  })
}
