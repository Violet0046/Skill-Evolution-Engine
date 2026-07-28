/**
 * frontend/src/pages/ReviewHome.tsx — 主页 (三栏可拖拽布局)
 *
 * 结构:
 *   ┌──────────────────────────────────────────────────────────────────┐
 *   │ Header (reviewer + run)                                         │
 *   ├──────────────┬─────────────────────────────┬──────────────────────┤
 *   │ Changes      │ Diff (中 55%)                │ Suggestions (右 25%) │
 *   │ (左 20%)     │  ├ DiffViewer (自带自画滚动)│  ├ suggestions list │
 *   │              │  └ EvidenceDrawer (浮层)     │  └ decision sticky  │
 *   │              │     ↑ 可拖拽, 位置记 local  │                      │
 *   └──────────────┴─────────────────────────────┴──────────────────────┘
 *
 * 交互 (按用户决策 2026-07-27):
 *   - 点左侧某行 -> Diff + Suggestions 切换
 *   - 右栏 SuggestionCard 不再整面板可点;
 *     而是右下角一个明显 "📎 查看证据 N" 按钮 → 触发 EvidenceDrawer 浮层
 *   - EvidenceDrawer 覆盖在 Diff 栏之上 (浮层, 默认右下角)
 *   - 标题栏左半部可拖 (cursor: grab), 右半部 [✕] 关闭按钮独立点击区
 *   - 拖动结束 (pointerup) 把位置 {x, y} 写到 localStorage
 *   - 同一浏览器下次进应用 / 切 sg, 位置从 localStorage 还原
 */

import { useCallback, useEffect, useState } from 'react'
import {
  Group,
  Panel,
  Separator,
} from 'react-resizable-panels'
import {
  listRuns,
  listChanges,
  getChange,
  type ChangeListItem,
  type ChangeOut,
} from '@/lib/api'
import { ChangeTable } from '@/components/ChangeTable'
import { DiffViewer } from '@/components/DiffViewer'
import { ReviewerInput } from '@/components/ReviewerInput'
import { DecisionForm } from '@/components/DecisionForm'
import { SuggestionCard } from '@/components/SuggestionCard'
import { EvidenceDrawer } from '@/components/EvidenceDrawer'
import { useReviewer } from '@/hooks/useReviewer'
import { postDecision } from '@/lib/api'

export function ReviewHome() {
  const { reviewer, setReviewer, isReady } = useReviewer()

  const [runs, setRuns] = useState<string[]>([])
  const [selectedRun, setSelectedRun] = useState<string>('')
  const [runsLoading, setRunsLoading] = useState(false)

  const [changes, setChanges] = useState<ChangeListItem[]>([])
  const [changesLoading, setChangesLoading] = useState(false)

  // selected change (主区 + 右区共用)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [selectedDetail, setSelectedDetail] = useState<ChangeOut | null>(null)
  const [isLoadingDetail, setIsLoadingDetail] = useState(false)

  // rerun trigger after a decision submission so the list refreshes (counts)
  const [refreshTick, setRefreshTick] = useState(0)

  // 当前右栏展开查看的 suggestion (null 表示没展开)
  const [activeSuggestionId, setActiveSuggestionId] = useState<string | null>(null)

  // modified 模式: 编辑状态 + 当前 edited 文本
  // null 走只读 diff; string (即使 == new_content) 表示正在编辑 (textarea 启动了)
  const [editedContent, setEditedContent] = useState<string | null>(null)

  useEffect(() => {
    setRunsLoading(true)
    listRuns()
      .then(rs => {
        setRuns(rs)
        if (rs.length > 0 && !selectedRun) setSelectedRun(rs[0])
      })
      .catch((err: unknown) => console.error('listRuns failed:', err))
      .finally(() => setRunsLoading(false))
  }, [])

  useEffect(() => {
    if (!selectedRun) {
      setChanges([])
      return
    }
    setChangesLoading(true)
    listChanges(selectedRun)
      .then(cs => setChanges(cs))
      .catch((err: unknown) => console.error('listChanges failed:', err))
      .finally(() => setChangesLoading(false))
  }, [selectedRun, refreshTick])

  // 把所有传给子组件的 callback 用 useCallback 稳定 reference,
  // 避免每次 ReviewHome rerender 时把 DiffViewer/DecisionForm/EditBody 一起触发 rerender.
  // 这是修 textarea 闪烁的关键 —— 之前每次输入新字符都新建闭包.
  const handleStartEdit = useCallback(() => {
    setEditedContent(selectedDetail?.new_content ?? '')
  }, [selectedDetail])

  const handleCancelEdit = useCallback(() => {
    setEditedContent(null)
  }, [])

  const handleModifiedChange = useCallback((t: string) => {
    setEditedContent(t)
  }, [])

  const handleSelect = async (item: ChangeListItem) => {
    setSelectedId(item.id)
    setSelectedDetail(null)
    // 切 change 时关闭 evidence 抽屉 + 编辑模式, 不让旧的 sg / 旧编辑残留
    setActiveSuggestionId(null)
    setEditedContent(null)
    setIsLoadingDetail(true)
    try {
      const detail = await getChange(item.id)
      setSelectedDetail(detail)
    } catch (err) {
      console.error('getChange failed:', err)
    } finally {
      setIsLoadingDetail(false)
    }
  }

  const handleDecision = async (body: Parameters<typeof postDecision>[1]) => {
    if (!selectedDetail) return
    await postDecision(selectedDetail.id, { ...body, reviewer })
    // 决策后:
    //   1. 刷新列表 (评审计数会变)
    //   2. 清掉编辑模式 (避免 "确认提交后还停留在原 textarea")
    setRefreshTick(t => t + 1)
    setEditedContent(null)
  }

  // ---- 子组件内联 (右栏 suggestions) ----
  const suggestions = selectedDetail?.suggestions_json ?? []

  return (
    <div className="h-screen bg-muted/20 flex flex-col">
      {/* Header */}
      <header className="border-b bg-background px-6 py-3 flex items-center justify-between flex-wrap gap-4 shrink-0">
        <div>
          <h1 className="text-xl font-bold">SEE评审系统</h1>
        </div>
        <ReviewerInput value={reviewer} onChange={setReviewer} />
      </header>

      {/* 三栏主区: 整体三栏各自滚 — 根 h-screen 把视口高度锁住,
         min-h-0 防止 flex item min-height: auto 撑大父级 */}
      <main className="flex-1 min-h-0 overflow-hidden">
        <Group orientation="horizontal" className="h-full">
          {/* 左: run 选择 + 文件目录 (一改就是一个文件) */}
          <Panel defaultSize={20} minSize={15}>
            <div className="h-full flex flex-col bg-background border-r overflow-hidden">
              {/* 选 run */}
              <div className="px-3 py-2 border-b shrink-0">
                <select
                  value={selectedRun}
                  onChange={e => setSelectedRun(e.target.value)}
                  className="w-full border rounded px-2 py-1.5 text-sm bg-background"
                  disabled={runsLoading || runs.length === 0}
                  aria-label="选择 run"
                >
                  {runsLoading && <option>加载 run...</option>}
                  {!runsLoading && runs.length === 0 && (
                    <option value="">（暂无 run）</option>
                  )}
                  {runs.map(r => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </select>
                {selectedRun && (
                  <p className="text-[10px] text-muted-foreground mt-1 font-mono truncate">
                    {changes.length} 个改动
                  </p>
                )}
              </div>
              {/* 文件清单 */}
              <div className="flex-1 overflow-auto">
                <ChangeTable
                  items={changes}
                  loading={changesLoading}
                  selectedId={selectedId}
                  onSelect={handleSelect}
                />
              </div>
            </div>
          </Panel>
          <Separator className="w-1 bg-border hover:bg-primary/30 transition-colors" />
          <Panel defaultSize={55} minSize={30}>
            <div className="h-full bg-background border-r overflow-hidden">
              {selectedDetail ? (
                <DiffViewer
                  linediff={selectedDetail.linediff ?? null}
                  originalSummary={`← ${selectedDetail.subject_target}`}
                  newSummary={editedContent !== null ? '编辑中... (提交用 modified 决策)' : 'new →'}
                  newContent={selectedDetail.new_content}
                  editing={editedContent !== null}
                  onModifiedChange={handleModifiedChange}
                />
              ) : isLoadingDetail ? (
                <p className="p-6 text-sm text-muted-foreground">加载中…</p>
              ) : (
                <Empty
                  title="Diff"
                  hint="← 选择左侧一条 change 后, 这里显示 git-style 双栏 diff"
                />
              )}

              {/* 证据浮层 (portal 到 body, position:fixed 全屏自由).
                  这里只是触发 mount; 实际 DOM 会被 createPortal 拎到 <body> 末尾. */}
              {selectedDetail && activeSuggestionId && (() => {
                const idx = suggestions.findIndex(s => s.id === activeSuggestionId)
                if (idx < 0) return null
                return (
                  <EvidenceDrawer
                    sg={suggestions[idx]}
                    index={idx + 1}
                    onClose={() => setActiveSuggestionId(null)}
                  />
                )
              })()}
            </div>
          </Panel>
          <Separator className="w-1 bg-border hover:bg-primary/30 transition-colors" />

          {/* 右: suggestions + 证据抽屉 + 底部 sticky 决策 */}
          <Panel defaultSize={25} minSize={20}>
            <div className="h-full flex flex-col bg-background overflow-hidden">
              <div className="px-3 py-2 border-b bg-muted/30 flex items-center justify-between shrink-0">
                <span className="text-sm font-semibold">
                  Suggestions {selectedDetail && `(${suggestions.length})`}
                </span>
                {selectedDetail && (
                  <span className="text-[10px] text-muted-foreground font-mono truncate ml-2">
                    #{selectedDetail.id}
                  </span>
                )}
              </div>

              {/* suggestions list + evidence drawer 同一滚动容器 */}
              <div className="flex-1 overflow-auto p-2 space-y-2">
                {selectedDetail ? (
                  suggestions.length === 0 ? (
                    <p className="text-xs text-muted-foreground text-center p-3">
                      无建议
                    </p>
                  ) : (
                    suggestions.map((sg, idx) => (
                      <SuggestionCard
                        key={sg.id}
                        sg={sg}
                        index={idx + 1}
                        active={sg.id === activeSuggestionId}
                        onOpenEvidence={() => {
                          // 显式按钮触发: 设置 active suggestion
                          // (再次点同一个会切换为 null, 由 EvidenceDrawer 内 [✕] 完成)
                          setActiveSuggestionId(sg.id)
                        }}
                      />
                    ))
                  )
                ) : isLoadingDetail ? (
                  <p className="text-xs text-muted-foreground text-center p-3">加载中…</p>
                ) : (
                  <Empty
                    title="Suggestions"
                    hint="← 选择左侧一条 change 后, 这里显示该 change 的建议"
                  />
                )}
              </div>

              {/* 底部 sticky: DecisionForm (始终贴底) */}
              {selectedDetail && (
                <div className="border-t p-3 bg-muted/20 shrink-0">
                  <DecisionForm
                    disabled={!isReady}
                    isEditing={editedContent !== null}
                    editedContent={editedContent}
                    originalNewContent={selectedDetail.new_content}
                    reviewer={reviewer}
                    onStartEdit={handleStartEdit}
                    onCancelEdit={handleCancelEdit}
                    onSubmit={handleDecision}
                  />
                </div>
              )}
            </div>
          </Panel>
        </Group>
      </main>
    </div>
  )
}

function Empty({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="h-full flex flex-col items-center justify-center text-center p-6 text-muted-foreground">
      <p className="text-lg font-semibold mb-1">{title}</p>
      <p className="text-sm">{hint}</p>
    </div>
  )
}