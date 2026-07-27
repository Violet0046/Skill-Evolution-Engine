/**
 * frontend/src/components/DiffMinimapOverlay.tsx
 *
 * 自画 minimap 滚动条 (类似 VS Code 的右侧缩略图).
 *
 * 设计 (按用户 2026-07-27 规则, v2):
 *   - 该组件与 scroller 是 flex sibling, 自己不滚动, 高度 = scroller viewport (= clientHeight)
 *   - 内部三层 (从底到顶):
 *       1) track   — 背景条, 浅灰
 *       2) markers — 同色相邻 +/- 行 merge 成的连续色块, 按 scrollHeight 比例定位
 *                    (markers 画在自己 viewport 内, 所以视觉钉死不滚走)
 *       3) thumb   — 当前视口可视区, 按 scrollTop / (scrollHeight - clientHeight) 算位置,
 *                    z 高于 markers, 鼠标拖动 = 改 scroller.scrollTop
 *   - 即便没有任何 +/- 行, track + thumb 仍然按比例画 (内容短时 thumb 占满),
 *     防止"overlay 消失"或"位置错乱". 视觉永远稳定.
 *
 * 性能:
 *   - markers 用 ResizeObserver + lines 变才重算 (%), 滚动时 thumb 位置用 onScroll 实时算
 *   - 不再依赖 Date.now() 这种伪触发
 */

import { useEffect, useMemo, useRef, useState } from 'react'

export interface MinimapLine {
  kind: 'added' | 'removed' | 'context' | 'placeholder'
  /** 对应 .map 里渲染的 div 元素 (用于 scrollIntoView) */
  rowEl: HTMLDivElement | null
  /** 1-based 行号 (placeholder 行可能没有) */
  lineNo?: number | ''
}

interface Props {
  /** 跟 DiffSide 的 lines[] 顺序完全一致 (左右拼接后传入) */
  lines: MinimapLine[]
  /** 容器 scrollContainer 的元素 (测 scrollHeight / scrollTop / clientHeight 用) */
  scrollContainer: HTMLDivElement | null
}

interface MarkerBlock {
  kind: 'added' | 'removed'
  startPct: number   // % of minimap viewport (== % of scrollContainer clientHeight)
  endPct: number
  /** 跳转到最贴中间的一行 (block center line) */
  targetRow: HTMLDivElement
  lineNo: number | ''
  count: number       // 块内有几行
}

export function DiffMinimapOverlay({ lines, scrollContainer }: Props) {
  // viewport (= scrollContainer.clientHeight) — minimap 自身的高度
  const [viewportH, setViewportH] = useState(0)
  // scrollHeight — 全部内容的高度, 用于算 marker 在 minimap 内的位置%
  const [contentH, setContentH] = useState(0)
  // 当前 thumb 位置 (rAF 节流过的 0..1 比例)
  const [thumbPct, setThumbPct] = useState(0)
  const [thumbHeightPct, setThumbHeightPct] = useState(1)

  const trackRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!scrollContainer) return
    const el = scrollContainer
    const sync = () => {
      const vh = el.clientHeight
      const ch = el.scrollHeight
      const range = Math.max(0, ch - vh)
      setViewportH(vh)
      setContentH(ch)
      setThumbHeightPct(range === 0 ? 1 : Math.min(1, vh / ch))
      setThumbPct(range === 0 ? 0 : Math.min(1, el.scrollTop / range))
    }
    sync()
    const ro = new ResizeObserver(sync)
    ro.observe(el)
    // 内容 child 尺寸变 → scrollHeight 变 → 也要 sync
    // ResizeObserver 默认会观察所有后代元素, 但要看它在 el 还是 child. el 就够,
    // 因为 scrollHeight 是 layout 触发, 内容尺寸变会同步触发 el 的尺寸可能不变,
    // 所以也观察 content (这里用 first child, 即 .grid).
    const grid = el.firstElementChild as HTMLElement | null
    if (grid) ro.observe(grid)
    return () => ro.disconnect()
  }, [scrollContainer])

  // 监听 scroll: 实时同步 thumb (rAF 节流)
  useEffect(() => {
    if (!scrollContainer) return
    let raf = 0
    const onScroll = () => {
      if (raf) return
      raf = requestAnimationFrame(() => {
        raf = 0
        const ch = scrollContainer.scrollHeight
        const vh = scrollContainer.clientHeight
        const range = Math.max(0, ch - vh)
        setThumbPct(range === 0 ? 0 : Math.min(1, scrollContainer.scrollTop / range))
        setThumbHeightPct(range === 0 ? 1 : Math.min(1, vh / ch))
      })
    }
    scrollContainer.addEventListener('scroll', onScroll, { passive: true })
    return () => {
      if (raf) cancelAnimationFrame(raf)
      scrollContainer.removeEventListener('scroll', onScroll)
    }
  }, [scrollContainer])

  // 合并: 同色相邻 +/- 行 → 连续块 (markers 用 scrollHeight 算 %)
  // marker 的 top% = row.offsetTop / scrollHeight * 100
  const blocks = useMemo<MarkerBlock[]>(() => {
    if (viewportH <= 0 || contentH <= 0) return []
    const positions: { kind: 'added' | 'removed'; topPct: number; bottomPct: number; targetRow: HTMLDivElement; lineNo: number | '' }[] = []
    for (const ln of lines) {
      if (ln.kind !== 'added' && ln.kind !== 'removed') continue
      if (!ln.rowEl) continue
      const cTop = ln.rowEl.offsetTop
      const cHeight = ln.rowEl.offsetHeight
      if (cHeight === 0) continue
      positions.push({
        kind: ln.kind,
        topPct: (cTop / contentH) * 100,
        bottomPct: ((cTop + cHeight) / contentH) * 100,
        targetRow: ln.rowEl,
        lineNo: ln.lineNo ?? '',
      })
    }
    const merged: MarkerBlock[] = []
    for (const p of positions) {
      const last = merged[merged.length - 1]
      if (
        last &&
        last.kind === p.kind &&
        // 连续 (允许极小缝隙, 这里精确比)
        Math.abs(last.endPct - p.topPct) < 0.5
      ) {
        last.endPct = p.bottomPct
        last.count += 1
      } else {
        merged.push({
          kind: p.kind,
          startPct: p.topPct,
          endPct: p.bottomPct,
          targetRow: p.targetRow,
          lineNo: p.lineNo,
          count: 1,
        })
      }
    }
    return merged
  }, [lines, viewportH, contentH])

  // 拖动 thumb: pointer events, onPointerDown 在 thumb 上开始, 移动时改 scrollContainer.scrollTop
  const onThumbPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    e.preventDefault()
    e.stopPropagation()
    if (!scrollContainer) return
    const el = scrollContainer
    const trackEl = trackRef.current
    if (!trackEl) return
    trackEl.setPointerCapture(e.pointerId)
    const rect = trackEl.getBoundingClientRect()
    const range = Math.max(1, el.scrollHeight - el.clientHeight)
    const apply = (clientY: number) => {
      const ratio = Math.min(1, Math.max(0, (clientY - rect.top) / rect.height))
      el.scrollTop = ratio * range
    }
    apply(e.clientY)
    const onMove = (ev: PointerEvent) => apply(ev.clientY)
    const onUp = () => {
      trackEl.releasePointerCapture(e.pointerId)
      trackEl.removeEventListener('pointermove', onMove)
      trackEl.removeEventListener('pointerup', onUp)
      trackEl.removeEventListener('pointercancel', onUp)
    }
    trackEl.addEventListener('pointermove', onMove)
    trackEl.addEventListener('pointerup', onUp)
    trackEl.addEventListener('pointercancel', onUp)
  }

  // 没有 scrollContainer: 给一个占位条 (透明 + 宽度 6px), 保留 DOM shape 不抖动
  if (!scrollContainer) {
    return <div className="w-1.5 shrink-0 bg-slate-100/50" aria-hidden="true" />
  }

  return (
    <div
      ref={trackRef}
      // 关键: 不参与 flex flow 之外的滚动, 因 sibling 关系本身就是静态位置
      // 内部 markers / thumb 全部 absolute 在这个 track 内,
      // track 高度 = scrollContainer.clientHeight (sub px, 跟着同步的)
      className="relative w-1.5 shrink-0 bg-slate-100 select-none cursor-pointer"
      style={{ height: viewportH > 0 ? viewportH : undefined }}
      role="scrollbar"
      aria-orientation="vertical"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(thumbPct * 100)}
      onPointerDown={(e) => {
        // 点击空白 track: 也跳到对应位置 (类似 macOS 点击滚动条空白)
        if (e.target === trackRef.current || (e.target as HTMLElement).dataset?.trackBg) {
          const rect = trackRef.current!.getBoundingClientRect()
          const range = Math.max(1, scrollContainer.scrollHeight - scrollContainer.clientHeight)
          const ratio = Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height))
          scrollContainer.scrollTop = ratio * range
        }
      }}
    >
      {/* 背景层: 让点击事件落到 track 上 (markers / thumb 都拦冒泡到 track) */}
      <div data-track-bg className="absolute inset-0" />

      {/* markers: 按 contentH% 在 viewport (==track) 内定位, viewport 自己不滚 => markers 不滚 */}
      {blocks.map((b, i) => (
        <button
          key={i}
          type="button"
          className={`absolute left-0 right-0 rounded-sm hover:opacity-90 transition-opacity ${
            b.kind === 'added'
              ? 'bg-green-500/60 hover:bg-green-500'
              : 'bg-red-500/60 hover:bg-red-500'
          }`}
          style={{
            top: `${b.startPct}%`,
            height: `${Math.max(0.6, b.endPct - b.startPct)}%`,
          }}
          onClick={(e) => {
            e.stopPropagation()
            b.targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' })
          }}
          onPointerDown={(e) => e.stopPropagation()}
          title={
            b.kind === 'added'
              ? `+ ${b.count} 行 (从 #${b.lineNo})`
              : `- ${b.count} 行 (从 #${b.lineNo})`
          }
          aria-label={
            b.kind === 'added'
              ? `跳转到新增块 (${b.count} 行)`
              : `跳转到删除块 (${b.count} 行)`
          }
        />
      ))}

      {/* thumb: 最上层, 同步 scrollTop, 可拖动. 颜色比 track 深. */}
      <div
        className="absolute left-0 right-0 bg-slate-500/70 hover:bg-slate-600 rounded-sm cursor-grab active:cursor-grabbing"
        style={{
          top: `${thumbPct * (1 - thumbHeightPct) * 100}%`,
          height: `${thumbHeightPct * 100}%`,
          minHeight: '8px',
        }}
        onPointerDown={onThumbPointerDown}
      />
    </div>
  )
}
