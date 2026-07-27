/**
 * frontend/src/components/ChangeTable.tsx — 主表 (左侧列表)
 *
 * 每行只展示文件名, 不展示 orig / new / sg 数 / review 事件等旁征列.
 * 用户决策 2026-07-25: review 信息在主/右区展示, 左侧仅为文件清单入口.
 */

import { FileText } from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ChangeListItem } from '@/lib/api'

interface Props {
  items: ChangeListItem[]
  loading: boolean
  selectedId: number | null
  onSelect: (item: ChangeListItem) => void
}

export function ChangeTable({ items, loading, selectedId, onSelect }: Props) {
  if (loading && items.length === 0) {
    return <p className="text-sm text-muted-foreground p-4">加载中...</p>
  }
  if (items.length === 0) {
    return <p className="text-sm text-muted-foreground p-4">该 run 没有 changes.</p>
  }

  return (
    <ul className="divide-y">
      {items.map(item => {
        const selected = selectedId === item.id
        // "需求分析Agent@skills/查询需求信息/SKILL.md" -> "skills/查询需求信息/SKILL.md"
        const fileOnly = item.subject_target.includes('@')
          ? item.subject_target.split('@').slice(1).join('@')
          : item.subject_target
        return (
          <li key={item.id}>
            <button
              type="button"
              onClick={() => onSelect(item)}
              className={cn(
                'w-full text-left px-3 py-2 flex items-start gap-2',
                'transition-colors hover:bg-muted/50',
                selected && 'bg-primary/10 ring-1 ring-primary/40',
              )}
            >
              <FileText className="w-3.5 h-3.5 mt-0.5 shrink-0 text-muted-foreground" />
              <div className="flex-1 min-w-0">
                <div className="text-[11px] font-mono leading-snug break-all">
                  {fileOnly}
                </div>
                <div className="text-[10px] text-muted-foreground/60 font-mono mt-0.5 truncate">
                  {item.subject_target}
                </div>
              </div>
            </button>
          </li>
        )
      })}
    </ul>
  )
}
