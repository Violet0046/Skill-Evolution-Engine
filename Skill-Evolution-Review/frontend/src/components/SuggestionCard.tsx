/**
 * frontend/src/components/SuggestionCard.tsx — 单条 Suggestion 的卡片
 *
 * 视觉:
 *   - direction: 黑体加粗 (突出) — 这条建议在干什么 / 怎么改
 *   - rationale: 默认字体, 前景色 80% (与 direction 区分, 但不抢)
 *   - 顶部: sg-编号 + priority + target_skill
 *   - 底部: 显式"查看证据"按钮 (有 N 条时显示, 没有时按钮置 disabled)
 *
 * 交互:
 *   - 卡片本体完全静态 — 文本可被选可被复制, 不会误触
 *   - 点右下 "查看证据 N" 按钮 -> 通知父组件展开 evidence drawer
 *   - active state 通过 button 上的 ring 体现, 不影响整张卡视觉
 */

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import type { Suggestion } from '@/lib/api'

function priorityVariant(p: Suggestion['priority']): 'default' | 'secondary' | 'outline' {
  if (p === 'high') return 'default'
  if (p === 'medium') return 'secondary'
  return 'outline'
}

interface Props {
  sg: Suggestion
  index: number       // 1-based for "sg-001" 编号
  active?: boolean    // 当前抽屉是否在展示这条
  onOpenEvidence?: (sgId: string) => void
}

export function SuggestionCard({ sg, index, active, onOpenEvidence }: Props) {
  const hasEvidence = sg.evidence_uuids.length > 0
  return (
    <div
      className={cn(
        // 不可点击: 文本可选可复制, 不会误触
        'border rounded p-2 space-y-1.5 bg-background',
        // active 不影响整张卡视觉, 仍只是边框高亮一丢
        active && 'border-primary',
      )}
    >
      {/* header row */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <code className="text-[10px] text-muted-foreground font-mono">
          sg-{String(index).padStart(3, '0')}
        </code>
        <Badge variant={priorityVariant(sg.priority)} className="text-[10px]">
          {sg.priority}
        </Badge>
        {sg.target_skill && (
          <Badge variant="outline" className="text-[10px]">
            {sg.target_skill}
          </Badge>
        )}
      </div>

      {/* direction: 黑体加粗, sm 级, 不被灰 */}
      <p className="text-sm font-semibold leading-snug text-foreground">
        {sg.direction}
      </p>

      {/* rationale: 常规字体, 前景色 80% */}
      <p className="text-xs leading-relaxed text-foreground/80">
        {sg.rationale}
      </p>

      {/* 显式 evidence 触发按钮 — 不与卡片其它区重叠, 用户点它才打开 */}
      <div className="pt-1 flex justify-end">
        <button
          type="button"
          onClick={() => onOpenEvidence?.(sg.id)}
          disabled={!hasEvidence || !onOpenEvidence}
          aria-label={hasEvidence ? `查看 ${sg.evidence_uuids.length} 条证据` : '无证据可查'}
          className={cn(
            'text-[10px] px-2 py-0.5 rounded border inline-flex items-center gap-1',
            'transition-colors',
            hasEvidence
              ? 'bg-background hover:bg-muted hover:border-primary/50 cursor-pointer text-foreground'
              : 'bg-muted/30 text-muted-foreground cursor-not-allowed',
            active && 'ring-2 ring-primary/60 border-primary',
          )}
        >
          <span aria-hidden="true">📎</span>
          {hasEvidence ? `查看证据 ${sg.evidence_uuids.length}` : '无证据'}
        </button>
      </div>
    </div>
  )
}
