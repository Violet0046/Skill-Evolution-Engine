/**
 * frontend/src/components/DecisionForm.tsx — 抽屉底部的 3 按钮 + 备注 + modified_content
 */

import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import type { DecisionIn } from '@/lib/api'

interface Props {
  disabled: boolean          // reviewer 未填时 true
  onSubmit: (body: DecisionIn) => Promise<void> | void
}

export function DecisionForm({ disabled, onSubmit }: Props) {
  const [decision, setDecision] = useState<'approved' | 'modified' | 'rejected' | null>(null)
  const [comment, setComment] = useState('')
  const [modifiedContent, setModifiedContent] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handle = async (kind: 'approved' | 'modified' | 'rejected') => {
    setDecision(kind)
    if (kind === 'modified' && !modifiedContent.trim()) {
      return  // 等用户填好 modified_content
    }
    setSubmitting(true)
    try {
      await onSubmit({
        decision: kind,
        comment: comment || null,
        modified_content: kind === 'modified' ? modifiedContent : null,
        reviewer: '__from_parent__',  // 由调用方覆盖 (reviewer 在 ReviewHome 持有)
      } as DecisionIn)
      // 成功后清空 (除 reviewer 外)
      setComment('')
      setModifiedContent('')
      setDecision(null)
    } finally {
      setSubmitting(false)
    }
  }

  // "modified" 选择时: 显示 modified_content 输入区
  // 这里做一个简易门控: 点击按钮前不显示输入, 点了才显示
  if (decision === 'modified') {
    return (
      <div className="space-y-3">
        <Input
          placeholder="填入修改后的 markdown 内容 (必填)"
          value={modifiedContent}
          onChange={e => setModifiedContent(e.target.value)}
        />
        <Textarea
          placeholder="备注 (可选)"
          rows={3}
          value={comment}
          onChange={e => setComment(e.target.value)}
        />
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => setDecision(null)}>
            取消
          </Button>
          <Button
            onClick={() => handle('modified')}
            disabled={disabled || submitting || !modifiedContent.trim()}
          >
            {submitting ? '提交中...' : '确认 modified'}
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <Textarea
        placeholder="备注 (可选)"
        rows={2}
        value={comment}
        onChange={e => setComment(e.target.value)}
        disabled={disabled}
      />
      <div className="flex justify-end gap-2">
        <Button
          variant="destructive"
          onClick={() => handle('rejected')}
          disabled={disabled || submitting}
        >
          ✕ 拒绝
        </Button>
        <Button
          variant="secondary"
          onClick={() => setDecision('modified')}
          disabled={disabled || submitting}
        >
          ✎ 修改
        </Button>
        <Button
          onClick={() => handle('approved')}
          disabled={disabled || submitting}
        >
          ✓ 通过
        </Button>
      </div>
      {disabled && (
        <p className="text-xs text-destructive text-center">
          请先填写顶部"评审人"再提交
        </p>
      )}
    </div>
  )
}
