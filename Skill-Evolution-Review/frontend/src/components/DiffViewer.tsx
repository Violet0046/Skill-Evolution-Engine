/**
 * frontend/src/components/DiffViewer.tsx — git-style 双栏 diff + +/- 行 marker
 *
 * 设计 (按用户 2026-07-25 规则):
 *   - 隐藏原生滚动条 (Tailwind: overflow-y-scroll + 自定义 w-1.5 滚动条)
 *   - 在 w-1.5 自画滚动条上画 +/- 行色块 marker
 *   - marker 按内容行比例 (top: %) 固定, 不随滚动消失
 *   - 点击 marker -> 该行 scrollIntoView center
 *   - thumb (滚动滑块) 层级 > marker
 *
 * 注: 浏览器原生 scrollbar 我们隐藏, 完全用 1.5px 宽自画滚动条 + 上下挪 thumb.
 *     这是 "全自画" 妥协方案, 但 100% 满足"marker 在滚动条内部 + 滑块 > marker" 要求.
 */

import { useRef, useState } from 'react'
import { DiffMinimapOverlay, type MinimapLine } from './DiffMinimapOverlay'

export interface DiffLine {
  // lineNo: '' 表示占位, 对侧无对应行
  lineNo: number | ''
  text: string
  kind: 'context' | 'removed' | 'added' | 'placeholder'
}

export interface LinediffFormat {
  leftLines: DiffLine[]
  rightLines: DiffLine[]
  added: number
  removed: number
}

interface Props {
  linediff: LinediffFormat | null | undefined
  originalSummary?: string
  newSummary?: string
}

const KIND_CLASS: Record<DiffLine['kind'], string> = {
  context: 'bg-white text-slate-700',
  removed: 'bg-red-50 text-red-900',
  added: 'bg-green-50 text-green-900',
  placeholder: 'bg-slate-50',
}

const KIND_PREFIX: Record<DiffLine['kind'], string> = {
  context: ' ',
  removed: '-',
  added: '+',
  placeholder: ' ',
}

export function DiffViewer({ linediff, originalSummary, newSummary }: Props) {
  return (
    <div className="h-full flex flex-col">
      {/* header */}
      <div className="px-3 py-2 border-b bg-muted/30 flex items-center justify-between shrink-0">
        <span className="text-sm font-semibold">Diff</span>
        {linediff && (
          <span className="text-xs font-mono">
            <span className="text-green-700">+{linediff.added}</span>
            {' '}
            <span className="text-red-700">-{linediff.removed}</span>
          </span>
        )}
      </div>

      {(originalSummary || newSummary) && (
        <div className="px-3 py-1 bg-muted/10 border-b text-[10px] font-mono text-muted-foreground flex justify-between shrink-0">
          <span>{originalSummary || '← original'}</span>
          <span>{newSummary || 'new →'}</span>
        </div>
      )}

      {!linediff ? (
        <div className="flex-1 overflow-auto font-mono text-[11px] leading-5">
          <div className="p-6 text-xs text-muted-foreground text-center">
            <p>diff 还未上线</p>
            <p className="text-[10px] mt-1">
              (或 change 还没有 evolving 文件)
            </p>
          </div>
        </div>
      ) : (
        <DiffBody linediff={linediff} />
      )}
    </div>
  )
}

function DiffBody({ linediff }: { linediff: LinediffFormat }) {
  const [scrollEl, setScrollEl] = useState<HTMLDivElement | null>(null)
  const leftRefs = useRef<(HTMLDivElement | null)[]>([])
  const rightRefs = useRef<(HTMLDivElement | null)[]>([])

  // 拼 minimap lines (按行)
  const lines: MinimapLine[] = []
  linediff.leftLines.forEach((l, i) =>
    lines.push({ kind: l.kind, rowEl: leftRefs.current[i] ?? null, lineNo: l.lineNo })
  )
  linediff.rightLines.forEach((l, i) =>
    lines.push({ kind: l.kind, rowEl: rightRefs.current[i] ?? null, lineNo: l.lineNo })
  )

  const setLeftRef = (i: number) => (el: HTMLDivElement | null) => {
    leftRefs.current[i] = el
  }
  const setRightRef = (i: number) => (el: HTMLDivElement | null) => {
    rightRefs.current[i] = el
  }

  return (
    <div
      ref={el => setScrollEl(el)}
      className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden font-mono text-[11px] leading-5 relative
                 [&::-webkit-scrollbar]:w-1.5
                 [&::-webkit-scrollbar-track]:bg-slate-100
                 [&::-webkit-scrollbar-thumb]:bg-slate-400
                 [&::-webkit-scrollbar-thumb]:rounded-full
                 hover:[&::-webkit-scrollbar-thumb]:bg-slate-500"
    >
      <div className="grid grid-cols-2 divide-x divide-slate-200">
        <DiffSide lines={linediff.leftLines} getRowRef={setLeftRef} />
        <DiffSide lines={linediff.rightLines} getRowRef={setRightRef} />
      </div>
      <DiffMinimapOverlay lines={lines} scrollContainer={scrollEl} />
    </div>
  )
}

function DiffSide({
  lines,
  getRowRef,
}: {
  lines: DiffLine[]
  getRowRef: (i: number) => (el: HTMLDivElement | null) => void
}) {
  return (
    <div>
      {lines.map((l, i) => (
        <div
          key={i}
          ref={getRowRef(i)}
          className={`flex ${KIND_CLASS[l.kind]}`}
        >
          <span
            className="w-12 shrink-0 text-right pr-2 select-none text-muted-foreground/70 border-r border-slate-200/50"
          >
            {l.lineNo === '' ? '' : l.lineNo}
          </span>
          <span
            className="w-4 shrink-0 text-center select-none text-muted-foreground/70"
          >
            {KIND_PREFIX[l.kind]}
          </span>
          <pre className="flex-1 whitespace-pre-wrap break-words pl-1 pr-2">
            {l.text || ' '}
          </pre>
        </div>
      ))}
    </div>
  )
}
