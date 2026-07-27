/**
 * frontend/src/pages/ReviewHome.tsx — 主页 (三栏可拖拽布局, 无抽屉)
 *
 * 结构:
 *   ┌──────────────────────────────────────────────────────────────────┐
 *   │ Header (reviewer + run)                                         │
 *   ├──────────────┬────────────────────────────────┬─────────────────┤
 *   │ Changes      │ Diff                          │ Suggestions     │
 *   │ (左 20%)     │ (中 55%)                       │ (右 25%)        │
 *   │              │                                │                 │
 *   │              │                                │ ──────────       │
 *   │              │                                │ DecisionForm    │
 *   │              │                                │ (右栏底 sticky)│
 *   └──────────────┴────────────────────────────────┴─────────────────┘
 *
 * 点击列表某行 -> 中 + 右 同时切数据. 左侧始终可见.
 */

import { useEffect, useState } from 'react'
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
import { useReviewer } from '@/hooks/useReviewer'
import { postDecision, type Suggestion } from '@/lib/api'
import { Badge } from '@/components/ui/badge'

function priorityVariant(p: Suggestion['priority']): 'default' | 'secondary' | 'outline' {
  if (p === 'high') return 'default'
  if (p === 'medium') return 'secondary'
  return 'outline'
}

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

  const handleSelect = async (item: ChangeListItem) => {
    setSelectedId(item.id)
    setSelectedDetail(null)
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
    // 决策后刷新列表 (评审计数会变)
    setRefreshTick(t => t + 1)
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
                  newSummary="new →"
                />
              ) : isLoadingDetail ? (
                <p className="p-6 text-sm text-muted-foreground">加载中…</p>
              ) : (
                <Empty
                  title="Diff"
                  hint="← 选择左侧一条 change 后, 这里显示 git-style 双栏 diff"
                />
              )}
            </div>
          </Panel>
          <Separator className="w-1 bg-border hover:bg-primary/30 transition-colors" />

          {/* 右: suggestions + 底部 sticky 决策 */}
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
              <div className="flex-1 overflow-auto p-2 space-y-2">
                {selectedDetail ? (
                  suggestions.length === 0 ? (
                    <p className="text-xs text-muted-foreground text-center p-3">
                      无建议
                    </p>
                  ) : (
                    suggestions.map((sg, idx) => (
                      <div
                        key={sg.id}
                        className="border rounded p-2 space-y-1 bg-background"
                      >
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <code className="text-[10px] text-muted-foreground font-mono">
                            sg-{String(idx + 1).padStart(3, '0')}
                          </code>
                          <Badge
                            variant={priorityVariant(sg.priority)}
                            className="text-[10px]"
                          >
                            {sg.priority}
                          </Badge>
                          {sg.target_skill && (
                            <Badge variant="outline" className="text-[10px]">
                              {sg.target_skill}
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs leading-snug">{sg.direction}</p>
                        <p className="text-[10px] text-muted-foreground leading-snug">
                          {sg.rationale}
                        </p>
                        {sg.evidence_uuids.length > 0 && (
                          <p className="text-[10px] text-muted-foreground">
                            证据 {sg.evidence_uuids.length} 条
                          </p>
                        )}
                      </div>
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
              {/* 底部 sticky: DecisionForm */}
              {selectedDetail && (
                <div className="border-t p-3 bg-muted/20 shrink-0">
                  <DecisionForm
                    disabled={!isReady}
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