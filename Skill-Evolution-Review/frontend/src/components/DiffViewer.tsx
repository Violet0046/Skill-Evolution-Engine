/**
 * frontend/src/components/DiffViewer.tsx — git-style 双栏 diff + 自画 minimap 滚动条
 *
 * 设计 (按用户 2026-07-27 规则):
 *   - Diff 容器强制 own scroll: overflow-y-scroll + min-h-0
 *   - 隐藏原生滚动条 (scrollbar-width:none + webkit display:none)
 *   - 右侧预留 6px gutter 给自画滚动条
 *   - 自画滚动条 = track(背景) + markers(绿红色块,absolute,按 content% 定位) + thumb(滑块)
 *   - thumb z 高于 markers, click marker 跳转到对应行, 拖 thumb 改 scrollTop
 *   - 关键: markers 画在 track 背景层内. track 容器不滚 => markers 不滚.
 *     哪怕 diff 内容只有几行也会自画 scrollbar 留 gutter, 防止 "外层 page 滚走 overlay" 的问题.
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
    // 左: 滚动内容区 (hidden scrollbar) | 右: 自画 minimap (不参与滚动, 永远钉在 viewport)
    // 这个布局是核心: minimap 不在滚动容器内, 而在滚动容器的兄弟位,
    // 所以无论怎么滚动内容, minimap 容器自身不动, 内含的 markers 也跟着不动.
    // markers 高度按 scrollHeight 比例画在自己容器 (== viewport 高度) 内,
    // thumb 位置按 scrollTop 比例同步.
    <div className="flex-1 min-h-0 flex">
      <div
        ref={el => setScrollEl(el)}
        // 强制 own scroll: 内容没超也强制出滚动条轨道, 避免被外层 page-scroll 拖走 overlay
        // hide native scrollbar (webkit + ff), 把 6px 让给右侧兄弟 minimap 接管滚动感
        className="diff-scroller flex-1 min-w-0 min-h-0 overflow-y-scroll overflow-x-hidden
                   font-mono text-[11px] leading-5"
      >
        <div className="grid grid-cols-2 divide-x divide-slate-200">
          <DiffSide lines={linediff.leftLines} getRowRef={setLeftRef} />
          <DiffSide lines={linediff.rightLines} getRowRef={setRightRef} />
        </div>
      </div>

      {/* minimap 容器: 与滚动容器并排 (flex sibling), 它自己不滚动,
          markers / thumb 都是它内部的 absolute 元素,
          它们永远停留在 viewport (viewport 本身不滚, 只有左侧 scrollContainer 内部在滚). */}
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
