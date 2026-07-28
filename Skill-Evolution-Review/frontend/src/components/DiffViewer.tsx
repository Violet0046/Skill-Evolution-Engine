/**
 * frontend/src/components/DiffViewer.tsx — git-style 双栏 diff + 自画 minimap + 可编辑右栏
 *
 * 三模式:
 *   - 只读 (默认): 双栏 diff, 红绿背景, 自画 minimap
 *   - editing:    左栏保持原 diff (作为参考, 用户可能想对照原文),
 *                  右栏切换为可编辑 textarea (完整 new_content), 用户直接改
 *   - 还原:       点 [↻ 还原回模型版] 把右栏重置为原 new_content
 *
 * 编辑模式设计要点:
 *   - rightLines 是 diff 视图的右栏内容 (包含 placeholder 行, 来自后端 difflib)
 *   - new_content 是后端返回的完整新文件 (用户编辑器用的就是这个)
 *   - 切到 editing 时: 左栏继续按 linediff.leftLines 渲染 (只读), 右栏换成 textarea
 *   - textarea 的初始值是新文件的全文 new_content
 *   - diff 数字 (added/removed 来自原 linediff) 在 header 仍显示, 但底下补一行
 *     "vs 模型原版: +X -Y =Z", 实时算用户当前 modified 内容相对 originalNewContent 的改动
 */

import React, { useMemo, useRef, useState, useCallback } from 'react'
import { DiffMinimapOverlay, type MinimapLine } from './DiffMinimapOverlay'
import { diffLinesCount, type LineDiffStats } from '@/lib/utils'

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
  /** 完整的新文件内容 (editing 模式初始化 textarea 用) */
  newContent?: string
  /** 是否进入编辑模式 (modified 决策时为 true) */
  editing?: boolean
  /** editing 模式下通知父组件用户当前编辑文本 */
  onModifiedChange?: (text: string) => void
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

export function DiffViewer({
  linediff,
  originalSummary,
  newSummary,
  newContent,
  editing,
  onModifiedChange,
}: Props) {
  return (
    <div className="h-full flex flex-col">
      {/* header */}
      <div className="px-3 py-2 border-b bg-muted/30 flex items-center justify-between shrink-0">
        <span className="text-sm font-semibold">
          {editing ? 'Diff (编辑模式)' : 'Diff'}
        </span>
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
      ) : editing && typeof newContent === 'string' ? (
        <EditBody
          linediff={linediff}
          initialContent={newContent}
          onModifiedChange={onModifiedChange}
        />
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

/**
 * EditBody — 进入 modified 模式时:
 *   左栏: original_content 的只读 diff (用户参考原文)
 *   右栏: 完整 new_content 全文, 可编辑 textarea
 *
 * 注意: linediff.rightLines 是 difflib 的"右侧行", 是不完整的 (省略了部分
 * unchanged 行, 用 placeholder 占位对齐). 我们用 new_content 全文替换之, 因为
 * 用户编辑时想要的是完整的可编辑视图.
 */
function EditBody({
  linediff,
  initialContent,
  onModifiedChange,
}: {
  linediff: LinediffFormat
  initialContent: string
  onModifiedChange?: (text: string) => void
  // 注意: 已删除 onRestore prop.
  //   "还原回模型版" 按钮**只在 EditBody 内部处理**:
  //     - 把 textarea 内容刷成模型原版 (通过 key={restoreKey} 强制重 mount)
  //     - stats 重置为 identical
  //     - 用户仍**留在编辑模式**, 可以继续改
  //   退出编辑模式是另一个独立动作 — "取消编辑", 由 DecisionForm 处理.
  //   修复前这里错误地把 onRestore 透传到父 -> 父关闭编辑模式 -> 等同"取消".
}) {
  const [restoreKey, setRestoreKey] = useState(0)
  const [stats, setStats] = useState<LineDiffStats>({ added: 0, removed: 0, changed: 0, identical: true })
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  const handleChange = useCallback(() => {
    const ta = textareaRef.current
    if (!ta) return
    const text = ta.value
    const s = diffLinesCount(initialContent, text)
    setStats(s)
    onModifiedChange?.(text)
  }, [initialContent, onModifiedChange])

  const handleRestore = useCallback(() => {
    // 关键: 不通知父组件, 仅 EditBody 内部逻辑:
    //   1. 刷新 key — 让 uncontrolled textarea 重新 mount, defaultValue 重新生效
    //   2. stats 重置为 identical
    //   3. 用户留在编辑模式, 然后可以重新编辑
    setRestoreKey(k => k + 1)
    setStats({ added: 0, removed: 0, changed: 0, identical: true })
  }, [])

  return (
    <div className="flex-1 min-h-0 flex flex-col">
      <EditStatusStrip
        stats={stats}
        onRestore={handleRestore}
      />

      <div className="flex-1 min-h-0 flex">
        {/* 左: 只读 diff, React.memo 包裹, linediff reference 不变就不 rerender */}
        <LeftDiffPanel linediff={linediff} />

        {/* 右: uncontrolled textarea; 用 key={restoreKey} 强制重 mount 实现 "还原" */}
        <textarea
          key={restoreKey}
          ref={textareaRef}
          defaultValue={initialContent}
          onChange={handleChange}
          spellCheck={false}
          className="flex-1 min-w-0 min-h-0 font-mono text-[11px] leading-5 px-2 py-1
                     bg-amber-50/30 border-l border-amber-200/60 resize-none
                     focus:outline-none focus:ring-1 focus:ring-amber-300"
          aria-label="修改后的 markdown 内容"
          placeholder="在这里编辑文件内容..."
        />
      </div>
    </div>
  )
}

/**
 * LeftDiffPanel — 左侧 diff 视图, 静态. 用 React.memo + 仅依赖 linediff reference.
 *
 * 关键: 这个组件**只在 mount 时渲染一次**. linediff 是后端算好的, 切 change / 还原
 * 时不会变; 只有切 change 时 linediff 整个换对象才会 rerender. 这彻底隔离了
 * "打字 -> 父 rerender -> 左栏重排" 的链.
 *
 * 它内部还有 minimap, 但 minimap 已经 useMemo 了, 在 linediff 不变的情况下
 * minimap 自身不会重算.
 */
const LeftDiffPanel = React.memo(function LeftDiffPanel({ linediff }: { linediff: LinediffFormat }) {
  const [scrollEl, setScrollEl] = useState<HTMLDivElement | null>(null)
  const leftRefs = useRef<(HTMLDivElement | null)[]>([])

  const lines: MinimapLine[] = useMemo(
    () => linediff.leftLines.map((l, i) => ({
      kind: l.kind,
      rowEl: leftRefs.current[i] ?? null,
      lineNo: l.lineNo,
    })),
    // lines 每次 render 是新数组, 但因为 React.memo 包了,
    // 只有 linediff reference 变了才会走这一步
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [linediff]
  )

  const setLeftRef = useCallback((i: number) => (el: HTMLDivElement | null) => {
    leftRefs.current[i] = el
  }, [])

  return (
    <div className="flex flex-1 min-w-0 min-h-0 relative">
      <div
        ref={el => setScrollEl(el)}
        className="diff-scroller flex-1 min-w-0 min-h-0 overflow-y-scroll overflow-x-hidden
                   font-mono text-[11px] leading-5"
      >
        <div className="divide-y divide-transparent">
          <DiffSide lines={linediff.leftLines} getRowRef={setLeftRef} />
        </div>
      </div>
      <DiffMinimapOverlay lines={lines} scrollContainer={scrollEl} />
    </div>
  )
})

/**
 * EditStatusStrip — 顶部状态条. 它只在 stats 变化时 rerender, 不参与
 * textarea 输入路径的 DOM. 用 React.memo 包 props.stats.
 */
const EditStatusStrip = React.memo(function EditStatusStrip({
  stats,
  onRestore,
}: {
  stats: LineDiffStats
  onRestore?: () => void
}) {
  return (
    <div className="px-3 py-1 bg-amber-50 border-b border-amber-200/60 text-[11px] flex items-center gap-2 shrink-0">
      <span className="font-semibold text-amber-900">📝 编辑模式</span>
      <span className="font-mono text-amber-800">
        {stats.identical
          ? '(与模型原版一致)'
          : <span>
              vs 模型原版:
              {stats.added   > 0 && <span className="ml-1 text-green-700">+{stats.added}</span>}
              {stats.removed > 0 && <span className="ml-1 text-red-700">-{stats.removed}</span>}
              {stats.changed > 0 && <span className="ml-1 text-amber-700">≈{stats.changed}</span>}
              {' '}
              <span className="text-muted-foreground">(行)</span>
            </span>}
      </span>
      <span className="ml-auto" />
      {onRestore && (
        <button
          type="button"
          onClick={onRestore}
          disabled={stats.identical}
          className="text-[11px] px-2 py-0.5 rounded border bg-background hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
          title="撤销所有修改, 回到模型给的新文件"
        >
          ↻ 还原回模型版
        </button>
      )}
    </div>
  )
})
