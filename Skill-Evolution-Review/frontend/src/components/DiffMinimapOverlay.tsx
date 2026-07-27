/**
 * frontend/src/components/DiffMinimapOverlay.tsx
 *
 * 在 DiffViewer 滚动条轨道上"画"出 +/- 行的鸟瞰分布 (类似 VS Code minimap).
 *
 * 设计:
 *   - 浮层贴 ScrollArea 右贴, width 5px
 *   - 每个 +/- 行按 clientHeight 比例画一个 marker 色块
 *   - 同色相邻标记: useMemo merge 成连续块 (hunk), 不连续分两块 (single)
 *   - 点击 marker -> 该行 scrollIntoView center
 *   - hover -> 原生 title (本期先用, 不做 fancy tooltip)
 *
 * 性能: 实时测 clientHeight 仅在 lines 变化时计算 (useMemo on-lines),
 * 滚动时不重测, 因为 positions 是 % 的.
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
  /** 跟 DiffSide 的 lines[] 顺序完全一致 (linter 仅用 + 没 + placeholder) */
  lines: MinimapLine[]
  /** 容器 ScrollArea 的元素 (测高度用) */
  scrollContainer: HTMLDivElement | null
}

interface MarkerBlock {
  kind: 'added' | 'removed'
  startPct: number   // % from top
  endPct: number
  /** 跳转到最贴中间的一行 (block center line) */
  targetRow: HTMLDivElement
  lineNo: number | ''
  count: number       // 块内有几行
}

export function DiffMinimapOverlay({ lines, scrollContainer }: Props) {
  // 容器高 (px) — 用来算每行百分比
  const [containerHeight, setContainerHeight] = useState(0)
  // 容器 ScrollArea 滚动高 (total content) — 但 % 算的是 (行位置 / content 高度) * 100
  // 而 scrollTop 已经给我们一个 (scrollTop / scrollHeight) 的比例
  // 但 marker 比例是用 行位置 / content 高度
  const [contentHeight, setContentHeight] = useState(0)

  useEffect(() => {
    if (!scrollContainer) return
    const el = scrollContainer
    const sync = () => {
      setContainerHeight(el.clientHeight)
      setContentHeight(el.scrollHeight)
    }
    sync()
    const ro = new ResizeObserver(sync)
    ro.observe(el)
    return () => ro.disconnect()
  }, [scrollContainer])

  // 合并: 同色相邻 + 跳过 placeholder
  const blocks = useMemo<MarkerBlock[]>(() => {
    if (containerHeight <= 0 || contentHeight <= 0) return []
    // 位置 map: 行 idx -> 0..1 比例
    // 我们用 rowEl 的 top/bottom 比例
    const positions: { kind: 'added' | 'removed'; topPct: number; bottomPct: number; targetRow: HTMLDivElement; lineNo: number | '' }[] = []
    for (const ln of lines) {
      if (ln.kind !== 'added' && ln.kind !== 'removed') continue
      if (!ln.rowEl) continue
      const cTop = ln.rowEl.offsetTop      // 距离 ScrollArea 内容顶部
      const cHeight = ln.rowEl.offsetHeight
      if (cHeight === 0) continue
      positions.push({
        kind: ln.kind,
        topPct: (cTop / contentHeight) * 100,
        bottomPct: ((cTop + cHeight) / contentHeight) * 100,
        targetRow: ln.rowEl,
        lineNo: ln.lineNo ?? '',
      })
    }

    // 合并相邻同色
    const merged: MarkerBlock[] = []
    for (const p of positions) {
      const last = merged[merged.length - 1]
      if (
        last &&
        last.kind === p.kind &&
        // 连续 (允许极小缝隙, 这里精确比)
        Math.abs(last.endPct - p.topPct) < 0.5
      ) {
        // 延长末块
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
  }, [lines, containerHeight, contentHeight, /* 定期 re-measure */ Date.now()])

  if (blocks.length === 0) return null

  return (
    <div
      className="pointer-events-none absolute right-0 top-0 bottom-0 w-1.5 z-10"
      aria-hidden="true"
    >
      {blocks.map((b, i) => (
        <button
          key={i}
          type="button"
          className={`pointer-events-auto absolute left-0 right-0 rounded-sm hover:opacity-80 ${
            b.kind === 'added'
              ? 'bg-green-500/60 hover:bg-green-500'
              : 'bg-red-500/60 hover:bg-red-500'
          }`}
          style={{
            top: `${b.startPct}%`,
            height: `${Math.max(0.5, b.endPct - b.startPct)}%`,
          }}
          onClick={() => {
            b.targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' })
          }}
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
    </div>
  )
}
