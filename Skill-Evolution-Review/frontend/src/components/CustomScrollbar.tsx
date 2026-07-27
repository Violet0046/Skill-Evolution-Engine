/**
 * frontend/src/components/CustomScrollbar.tsx
 *   自画滚动条 + diff +/- marker.
 *
 * 因为浏览器原生 scrollbar 不允许注入 DOM, 完全自画.
 */
import { useEffect, useRef, useState } from 'react'

export interface CustomScrollbarMarker {
  kind: 'added' | 'removed'
  topPct: number
  heightPct: number
  rowEl: HTMLDivElement
  lineNo: number | ''
}

interface Props {
  scrollEl: HTMLElement | null
  markers: CustomScrollbarMarker[]
  children: React.ReactNode
}

export function CustomScrollbar({ scrollEl, markers, children }: Props) {
  const [thumbPct, setThumbPct] = useState(0)
  const [thumbHeightPct, setThumbHeightPct] = useState(0)
  const trackRef = useRef<HTMLDivElement>(null)
  const dragStart = useRef<{ y: number; startScrollPct: number } | null>(null)

  // sync thumb
  useEffect(() => {
    if (!scrollEl) return
    const el = scrollEl
    const sync = () => {
      const ch = el.scrollHeight
      const vh = el.clientHeight
      if (ch <= 0) return
      const visibleRatio = Math.min(1, vh / ch)
      setThumbHeightPct(visibleRatio * 100)
      setThumbPct((el.scrollTop / Math.max(1, ch - vh)) * 100)
    }
    sync()
    const ro = new ResizeObserver(sync)
    ro.observe(el)
    el.addEventListener('scroll', sync, { passive: true })
    return () => {
      ro.disconnect()
      el.removeEventListener('scroll', sync)
    }
  }, [scrollEl])

  // wheel -> scrollTop
  const onWheel = (e: React.WheelEvent) => {
    if (!scrollEl) return
    e.preventDefault()
    scrollEl.scrollTop += e.deltaY
  }

  // click track -> jump
  const onTrackMouseDown = (e: React.MouseEvent) => {
    if (!scrollEl || !trackRef.current) return
    if (e.target !== trackRef.current) return // 只点轨道本身, 不点 thumb
    const trackRect = trackRef.current.getBoundingClientRect()
    const y = e.clientY - trackRect.top
    const ratio = Math.max(0, Math.min(1, y / trackRect.height))
    const ch = scrollEl.scrollHeight
    const vh = scrollEl.clientHeight
    scrollEl.scrollTop = ratio * Math.max(0, ch - vh)
  }

  // drag thumb
  const onThumbMouseDown = (e: React.MouseEvent) => {
    if (!scrollEl) return
    e.preventDefault()
    e.stopPropagation()
    dragStart.current = { y: e.clientY, startScrollPct: thumbPct }
    const onMove = (ev: MouseEvent) => {
      if (!dragStart.current || !trackRef.current || !scrollEl) return
      const trackRect = trackRef.current.getBoundingClientRect()
      const dy = ev.clientY - dragStart.current.y
      const deltaPct = (dy / trackRect.height) * 100
      const ch = scrollEl.scrollHeight
      const vh = scrollEl.clientHeight
      const newPct = Math.max(
        0,
        Math.min(100 - thumbHeightPct, dragStart.current.startScrollPct + deltaPct)
      )
      scrollEl.scrollTop = (newPct / 100) * Math.max(0, ch - vh)
    }
    const onUp = () => {
      dragStart.current = null
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }

  return (
    <div className="flex h-full w-full">
      {/* content area - 用 transform 切 scroll */}
      <div
        ref={el => {
          if (el) (el as any).__scrollEl = el
        }}
        onWheel={onWheel}
        className="flex-1 overflow-hidden"
        style={{ contain: 'strict' }}
      >
        <div style={{ minHeight: '100%' }}>{children}</div>
      </div>
      {/* track */}
      <div
        ref={trackRef}
        onMouseDown={onTrackMouseDown}
        className="relative w-2 h-full bg-slate-200/60 cursor-pointer shrink-0 select-none"
        aria-label="diff 滚动条"
        role="scrollbar"
        aria-valuenow={Math.round(thumbPct)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        {/* markers 在 track 内部, layer 低于 thumb */}
        {markers.map((m, i) => (
          <button
            key={i}
            type="button"
            onClick={() => {
              m.rowEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
            }}
            title={
              m.kind === 'added'
                ? `+ (从 #${m.lineNo})`
                : `- (从 #${m.lineNo})`
            }
            aria-label={m.kind === 'added' ? '跳到新增块' : '跳到删除块'}
            className={
              'absolute left-0 right-0 z-[1] hover:opacity-80 ' +
              (m.kind === 'added'
                ? 'bg-green-500/60 hover:bg-green-500'
                : 'bg-red-500/60 hover:bg-red-500')
            }
            style={{
              top: `${m.topPct}%`,
              height: `${Math.max(0.5, m.heightPct)}%`,
            }}
          />
        ))}
        {/* thumb - 层级最高, 拖动时覆盖 marker */}
        <div
          onMouseDown={onThumbMouseDown}
          className="absolute left-0 right-0 bg-slate-400/80 hover:bg-slate-500 cursor-grab active:cursor-grabbing rounded-sm z-[2]"
          style={{
            top: `${thumbPct}%`,
            height: `${Math.max(2, thumbHeightPct)}%`,
          }}
          aria-hidden="true"
        />
      </div>
    </div>
  )
}

/**
 * 暴露一个工具: 给定行 DOM refs 算 CustomScrollbarMarker[]
 */
export function computeMarkers(
  lines: { kind: 'added' | 'removed' | 'context' | 'placeholder'; rowEl: HTMLDivElement | null; lineNo?: number | '' }[]
): CustomScrollbarMarker[] {
  const out: CustomScrollbarMarker[] = []
  for (const ln of lines) {
    if (ln.kind !== 'added' && ln.kind !== 'removed') continue
    if (!ln.rowEl) continue
    const cTop = ln.rowEl.offsetTop
    const cHeight = ln.rowEl.offsetHeight
    if (cHeight === 0) continue
    const contentEl = ln.rowEl.offsetParent as HTMLElement | null
    if (!contentEl) continue
    const contentHeight = contentEl.scrollHeight
    if (contentHeight <= 0) continue
    out.push({
      kind: ln.kind,
      topPct: (cTop / contentHeight) * 100,
      heightPct: (cHeight / contentHeight) * 100,
      rowEl: ln.rowEl,
      lineNo: ln.lineNo ?? '',
    })
  }
  return out
}
