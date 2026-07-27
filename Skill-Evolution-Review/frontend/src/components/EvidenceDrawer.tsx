/**
 * frontend/src/components/EvidenceDrawer.tsx — Suggestion 的 evidence 下钻浮层 (全屏自由)
 *
 * 设计 (按用户 2026-07-27 决定):
 *   - 通过 createPortal 把自己挂到 document.body, 跟 ReviewHome 树脱耦
 *   - position: fixed, top/left 是 viewport 相对坐标
 *   - 拖动 pointermove 监听挂在 window (这样抽屉跑到屏幕任意位置都能响应)
 *   - clamp 边界 = viewport 尺寸 (window.innerWidth/Height)
 *   - 监听 window resize 重新 clamp, 避免抽屉被窗口缩小截掉一半
 *   - localStorage key = see.evidenceDrawer.pos, 存 {x, y} viewport 坐标
 *   - 默认位置贴 viewport 右下角 (跟旧版一致)
 *
 * 视觉:
 *   ┌────────────────────────────────────────────────┐
 *   │ [拖把] sg-001 / ReviewAgent            [✕ 关闭]│
 *   ├────────────────────────────────────────────────┤
 *   │ uuid 命中 (点击切换)                            │
 *   ├──────────────────┬─────────────────────────────┤
 *   │ evidence_uuids   │  detail_json 5 字段面板     │
 *   │ (左, scroll)     │  (右, scroll)               │
 *   │ 437d64d4...      │  session_id / uuid          │
 *   │ b15b9fc9...      │  tool_name / reasoning_*    │
 *   │ 593f0bcd...      │  input_params / error       │
 *   │ ...              │                              │
 *   └──────────────────┴─────────────────────────────┘
 *
 * 位置持久化: 按用户决策 2026-07-27, 用 localStorage 而非后端,
 *   key 与 useReviewer 的 see.reviewer 同前缀 (see.*)
 *   切换 sg / 关闭再开 = 复用同一位置
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { getEvidence } from '@/lib/api'
import type { EvidenceOut } from '@/lib/api'
import { parseSessionIdFromSuggestionId, cn } from '@/lib/utils'
import type { Suggestion } from '@/lib/api'

interface Props {
  sg: Suggestion             // 当前 active 的建议
  index: number              // 1-based for "sg-NNN"
  onClose?: () => void
}

interface LoadState {
  status: 'idle' | 'loading' | 'ok' | 'notfound' | 'error'
  data?: EvidenceOut
  errorMsg?: string
}

interface DrawerPos {
  x: number   // 距 viewport 左边 px
  y: number   // 距 viewport 上边 px
}

const POS_KEY = 'see.evidenceDrawer.pos'
const DEFAULT_DRAWER_W = 520
const DEFAULT_DRAWER_H = 360
const DEFAULT_DRAWER_MARGIN = 16
const MIN_DRAWER_W = 320
const MIN_DRAWER_H = 200

function loadSavedPos(): DrawerPos | null {
  try {
    const raw = localStorage.getItem(POS_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (
      typeof parsed === 'object' && parsed !== null &&
      typeof parsed.x === 'number' && Number.isFinite(parsed.x) &&
      typeof parsed.y === 'number' && Number.isFinite(parsed.y)
    ) {
      return { x: parsed.x, y: parsed.y }
    }
  } catch { /* ignore */ }
  return null
}

function savePos(p: DrawerPos) {
  try {
    localStorage.setItem(POS_KEY, JSON.stringify(p))
  } catch { /* ignore quota / privacy mode */ }
}

function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n))
}

export function EvidenceDrawer({ sg, index, onClose }: Props) {
  const sessionId = useMemo(() => parseSessionIdFromSuggestionId(sg.id), [sg.id])

  // 当前 suggestion 内的 uuid 命中缓存: key = uuid, value = EvidenceOut | '__notfound__'
  const [hitCache, setHitCache] = useState<Record<string, EvidenceOut | '__notfound__'>>({})
  const [activeUuid, setActiveUuid] = useState<string | null>(sg.evidence_uuids[0] ?? null)
  const [state, setState] = useState<LoadState>({ status: 'idle' })
  const abortRef = useRef<AbortController | null>(null)

  // 拖拽 / 位置状态
  const drawerRef = useRef<HTMLDivElement | null>(null)
  const [pos, setPos] = useState<DrawerPos | null>(null)   // null = 未初始化
  const [size, setSize] = useState({ w: DEFAULT_DRAWER_W, h: DEFAULT_DRAWER_H })
  const [dragging, setDragging] = useState(false)
  const dragStateRef = useRef<{
    startX: number; startY: number; origX: number; origY: number
  } | null>(null)

  // 首次挂载: 读 localStorage 或默认 viewport 右下角
  useEffect(() => {
    const vw = window.innerWidth
    const vh = window.innerHeight
    const w = Math.min(DEFAULT_DRAWER_W, Math.max(MIN_DRAWER_W, vw * 0.6))
    const h = Math.min(DEFAULT_DRAWER_H, Math.max(MIN_DRAWER_H, vh * 0.5))
    setSize({ w, h })
    const saved = loadSavedPos()
    if (saved) {
      // 立刻用 (后续 resize effect 会再 clamp)
      setPos({ x: saved.x, y: saved.y })
    } else {
      // 默认右下角 + 16px margin
      setPos({
        x: Math.max(0, vw - w - DEFAULT_DRAWER_MARGIN),
        y: Math.max(0, vh - h - DEFAULT_DRAWER_MARGIN),
      })
    }
  }, [])

  // 监听 window resize: 重新 clamp, 不让抽屉被截掉
  useEffect(() => {
    const onResize = () => {
      const vw = window.innerWidth
      const vh = window.innerHeight
      setSize(prev => {
        const w = Math.min(DEFAULT_DRAWER_W, Math.max(MIN_DRAWER_W, vw * 0.6))
        const h = Math.min(DEFAULT_DRAWER_H, Math.max(MIN_DRAWER_H, vh * 0.5))
        return { w, h }
      })
      setPos(prev => {
        if (!prev) return prev
        // 读取最新 size (用 setState 回调读不到, 但我们同期 setSize 会触发, 边 clamp 边用更新后的尺寸)
        const w = Math.min(DEFAULT_DRAWER_W, Math.max(MIN_DRAWER_W, vw * 0.6))
        const h = Math.min(DEFAULT_DRAWER_H, Math.max(MIN_DRAWER_H, vh * 0.5))
        return {
          x: clamp(prev.x, 0, Math.max(0, vw - w)),
          y: clamp(prev.y, 0, Math.max(0, vh - h)),
        }
      })
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  // 切换 suggestion 时重置 uuid cache + 默认选中第一个 + 触发 fetch
  useEffect(() => {
    if (abortRef.current) abortRef.current.abort()
    setHitCache({})
    const firstUuid = sg.evidence_uuids[0] ?? null
    setActiveUuid(firstUuid)
    setState({ status: 'idle' })
    if (firstUuid && sessionId) void fetchOne(sessionId, firstUuid)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sg.id, sessionId])

  // 切换 uuid 时: 若有 cache 直接用, 否则 fetch
  useEffect(() => {
    if (!activeUuid || !sessionId) return
    const cached = hitCache[activeUuid]
    if (cached === '__notfound__') {
      setState({ status: 'notfound' })
    } else if (cached) {
      setState({ status: 'ok', data: cached })
    } else {
      void fetchOne(sessionId, activeUuid)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeUuid])

  async function fetchOne(sid: string, uuid: string) {
    if (abortRef.current) abortRef.current.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setState({ status: 'loading' })
    try {
      const out = await getEvidence(sid, uuid)
      if (ctrl.signal.aborted) return
      if (out == null) {
        setHitCache(prev => ({ ...prev, [uuid]: '__notfound__' }))
        setState({ status: 'notfound' })
      } else {
        setHitCache(prev => ({ ...prev, [uuid]: out }))
        setState({ status: 'ok', data: out })
      }
    } catch (err) {
      if ((err as { name?: string })?.name === 'AbortError') return
      const status = (err as { status?: number })?.status
      if (status === 404) {
        setHitCache(prev => ({ ...prev, [uuid]: '__notfound__' }))
        setState({ status: 'notfound' })
      } else {
        setState({
          status: 'error',
          errorMsg: err instanceof Error ? err.message : String(err),
        })
      }
    }
  }

  // 拖拽: pointermove 挂在 window (抽屉可以跑出 diff 栏)
  const onGripPointerDown = useCallback((e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return
    e.preventDefault()
    if (pos == null) return
    dragStateRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      origX: pos.x,
      origY: pos.y,
    }
    setDragging(true)

    const onMove = (ev: PointerEvent) => {
      const ds = dragStateRef.current
      if (!ds) return
      const dx = ev.clientX - ds.startX
      const dy = ev.clientY - ds.startY
      const drawer = drawerRef.current
      const dw = drawer ? drawer.getBoundingClientRect().width : DEFAULT_DRAWER_W
      const dh = drawer ? drawer.getBoundingClientRect().height : DEFAULT_DRAWER_H
      const vw = window.innerWidth
      const vh = window.innerHeight
      setPos({
        x: clamp(ds.origX + dx, 0, Math.max(0, vw - dw)),
        y: clamp(ds.origY + dy, 0, Math.max(0, vh - dh)),
      })
    }

    const onUp = (ev: PointerEvent) => {
      const ds = dragStateRef.current
      if (ds) {
        // 保存最终位置
        const dx = ev.clientX - ds.startX
        const dy = ev.clientY - ds.startY
        const drawer = drawerRef.current
        const dw = drawer ? drawer.getBoundingClientRect().width : DEFAULT_DRAWER_W
        const dh = drawer ? drawer.getBoundingClientRect().height : DEFAULT_DRAWER_H
        const vw = window.innerWidth
        const vh = window.innerHeight
        const finalPos = {
          x: clamp(ds.origX + dx, 0, Math.max(0, vw - dw)),
          y: clamp(ds.origY + dy, 0, Math.max(0, vh - dh)),
        }
        savePos(finalPos)
      }
      dragStateRef.current = null
      setDragging(false)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerup', onUp)
      window.removeEventListener('pointercancel', onUp)
    }
    window.addEventListener('pointermove', onMove)
    window.addEventListener('pointerup', onUp)
    window.addEventListener('pointercancel', onUp)
  }, [pos])

  // portal target — SSR / 早期测试时 document.body 可能还没就绪, 兜底 null
  if (typeof document === 'undefined') return null
  if (pos == null) return null

  const title = `sg-${String(index).padStart(3, '0')} 证据`
  const subtitle = sg.target_skill
  const sessionShort = sessionId ? shortUuid(sessionId) : null

  const drawerBody = (
    <div
      ref={el => { drawerRef.current = el }}
      className={cn(
        // 固定到 viewport, 全屏自由. z 高于面板, 低于未来 modal
        'fixed z-30 bg-background border rounded-md shadow-lg flex flex-col overflow-hidden',
        dragging ? 'shadow-2xl' : 'shadow-lg',
      )}
      style={{
        left: `${pos.x}px`,
        top: `${pos.y}px`,
        width: `${size.w}px`,
        height: `${size.h}px`,
      }}
      onPointerDown={(e) => e.stopPropagation()}
    >
      {/* header: 左 = 拖把+标题, 右 = session+✕ */}
      <div className="px-2 py-1 flex items-center gap-2 border-b bg-muted/60 shrink-0 select-none h-8">
        <div
          className="flex items-center gap-1.5 flex-1 min-w-0 cursor-grab active:cursor-grabbing"
          onPointerDown={onGripPointerDown}
        >
          <span aria-hidden="true" className="text-muted-foreground text-xs leading-none">⋮⋮</span>
          <span className="text-xs font-semibold truncate">{title}</span>
          {subtitle && (
            <span className="text-[10px] text-muted-foreground font-mono truncate">{subtitle}</span>
          )}
          {sessionShort && (
            <span className="ml-auto text-[10px] text-muted-foreground/80 font-mono shrink-0">
              session {sessionShort}
            </span>
          )}
        </div>
        {onClose && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation()
              onClose()
            }}
            onPointerDown={(e) => e.stopPropagation()}
            className="text-xs px-2 py-0.5 rounded hover:bg-muted text-muted-foreground shrink-0"
            aria-label="关闭证据面板"
          >
            ✕
          </button>
        )}
      </div>

      {/* body */}
      <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
        {!sessionId && (
          <div className="p-3 text-xs text-muted-foreground">
            suggestion id 解析不出 session_id（{sg.id}），无法定位证据。
          </div>
        )}
        {sessionId && sg.evidence_uuids.length === 0 && (
          <div className="p-3 text-xs text-muted-foreground">
            该建议没有 evidence_uuids。
          </div>
        )}
        {sessionId && sg.evidence_uuids.length > 0 && (
          <div className="flex-1 min-h-0 flex overflow-hidden">
            {/* 左: uuid 列表 */}
            <ul className="w-40 shrink-0 overflow-auto border-r bg-background/60">
              {sg.evidence_uuids.map(uuid => {
                const cached = hitCache[uuid]
                const isActive = uuid === activeUuid
                return (
                  <li key={uuid}>
                    <button
                      type="button"
                      onClick={() => setActiveUuid(uuid)}
                      onPointerDown={(e) => e.stopPropagation()}
                      className={cn(
                        'w-full text-left px-2 py-1.5 text-[10px] font-mono break-all border-b border-border/40 hover:bg-muted/40',
                        isActive && 'bg-primary/10 font-semibold',
                      )}
                      title={uuid}
                    >
                      <span className="block truncate">
                        {cached === '__notfound__'
                          ? <span className="text-red-600">未命中 {shortUuid(uuid)}</span>
                          : shortUuid(uuid)}
                      </span>
                    </button>
                  </li>
                )
              })}
            </ul>

            {/* 右: detail 面板 */}
            <div className="flex-1 min-w-0 overflow-auto p-2 text-xs font-mono">
              {state.status === 'loading' && (
                <p className="text-muted-foreground">加载中…</p>
              )}
              {state.status === 'notfound' && (
                <p className="text-red-600">evidence 未命中 (404)。可能该 uuid 还没入库，或 (session_id, uuid) 配错。</p>
              )}
              {state.status === 'error' && (
                <p className="text-red-600">拉取失败: {state.errorMsg}</p>
              )}
              {state.status === 'ok' && state.data && (
                <DetailView ev={state.data} />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )

  return createPortal(drawerBody, document.body)
}

function DetailView({ ev }: { ev: EvidenceOut }) {
  const d = ev.detail_json
  return (
    <div className="space-y-2">
      <Field label="session_id" value={ev.session_id} mono />
      <Field label="uuid" value={ev.uuid} mono />
      <Field label="tool_name" value={d?.tool_name} />
      <Field label="reasoning_before" value={d?.reasoning_before} multiline />
      <Field label="reasoning_after" value={d?.reasoning_after} multiline />
      <Field label="input_params" value={d?.input_params ? JSON.stringify(d.input_params, null, 2) : null} mono multiline />
      <Field label="error_output" value={d?.error_output} multiline />
    </div>
  )
}

function Field({
  label,
  value,
  mono,
  multiline,
}: {
  label: string
  value: string | null | undefined
  mono?: boolean
  multiline?: boolean
}) {
  const display = value == null || value === '' ? '—' : value
  return (
    <div>
      <p className="text-[10px] font-sans font-semibold text-muted-foreground uppercase tracking-wide">
        {label}
      </p>
      <pre
        className={cn(
          'text-xs mt-0.5 whitespace-pre-wrap break-words',
          mono ? 'font-mono' : 'font-sans',
          display === '—' && 'text-muted-foreground/60 italic',
        )}
      >
        {display}
      </pre>
    </div>
  )
}

function shortUuid(u: string): string {
  if (!u) return ''
  return u.slice(0, 8)
}
