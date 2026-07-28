/**
 * frontend/src/components/WriteConfirmModal.tsx — 提交评审决策的二次确认
 *
 * 是 ConfirmModal 的薄包装.
 *
 * 调用方: DecisionForm 任意决策按钮 → 弹 modal → 确认后才真发请求.
 */

import { ConfirmModal, type ConfirmItem } from './ConfirmModal'

export type DecisionKind = 'approved' | 'modified' | 'rejected'

interface Props {
  open: boolean
  reviewer: string
  decision: DecisionKind
  comment: string
  modifiedContent?: string | null
  /** 与原 new_content 的改动统计 (added/removed/changed) */
  diffStats?: { added: number; removed: number; changed: number; identical: boolean }
  submitting?: boolean
  onCancel: () => void
  onConfirm: () => void
}

const DECISION_LABEL: Record<DecisionKind, { verb: string; colorClass: string }> = {
  approved:  { verb: '通过', colorClass: 'text-green-700' },
  modified:  { verb: '修改', colorClass: 'text-amber-700' },
  rejected:  { verb: '拒绝', colorClass: 'text-red-700' },
}

/** modified_content 第一段 / 第一行 (前 80 字) 预览 */
function firstLinePreview(modifiedContent: string | null | undefined): string | null {
  if (!modifiedContent) return null
  const lines = modifiedContent.split('\n')
  let i = 0
  while (i < lines.length && lines[i].trim().length === 0) i++
  const head = lines[i] ?? ''
  return head.length > 80 ? head.slice(0, 80) + '...' : head
}

export function WriteConfirmModal({
  open,
  reviewer,
  decision,
  comment,
  modifiedContent,
  diffStats,
  submitting,
  onCancel,
  onConfirm,
}: Props) {
  const label = DECISION_LABEL[decision]
  const showModified = decision === 'modified'

  const items: ConfirmItem[] = [
    { k: '评审人', v: reviewer || <em className="text-muted-foreground">(空)</em> },
    {
      k: 'decision',
      v: <span className={`font-mono font-semibold ${label.colorClass}`}>{decision}</span>,
    },
    {
      k: 'comment',
      v: (
        <span className="break-all">
          {comment || <em className="text-destructive">⚠ 空 (不符合规则)</em>}
        </span>
      ),
    },
  ]

  if (showModified) {
    items.push({
      k: 'modified 字数',
      v: <span className="font-mono">{modifiedContent?.length ?? 0} 字</span>,
    })
    if (diffStats) {
      items.push({
        k: 'vs 模型原版',
        v: diffStats.identical ? (
          <span className="text-muted-foreground">(与模型原版一致, 没改)</span>
        ) : (
          <span className="font-mono">
            {diffStats.added   > 0 && <span className="text-green-700">+{diffStats.added}</span>}{' '}
            {diffStats.removed > 0 && <span className="text-red-700">-{diffStats.removed}</span>}{' '}
            {diffStats.changed > 0 && <span className="text-amber-700">≈{diffStats.changed}</span>}{' '}
            <span className="text-muted-foreground">(行)</span>
          </span>
        ),
      })
    }
    const preview = firstLinePreview(modifiedContent)
    if (preview) {
      items.push({
        k: '首行预览',
        v: (
          <code className="text-[11px] font-mono bg-muted px-1 py-0.5 rounded">
            {preview}
          </code>
        ),
      })
    }
  }

  return (
    <ConfirmModal
      open={open}
      title="确认提交评审?"
      titleTag={{ text: label.verb, colorClass: label.colorClass }}
      items={items}
      primaryLabel="确认提交"
      cancelLabel="取消"
      submitting={submitting}
      onCancel={onCancel}
      onConfirm={onConfirm}
    />
  )
}
