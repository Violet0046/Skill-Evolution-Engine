/**
 * frontend/src/components/DecisionForm.tsx — 评审决策表单 (改后版)
 *
 * 改动 (按用户决策 2026-07-27):
 *   - comment 必填 (trim 后非空即可, 无最少字数要求)
 *   - modified 决策: 改为"切换编辑模式"按钮, 不再让用户手动填整个 md
 *     真正的编辑在 DiffViewer 右栏 textarea, 这里只负责"打开编辑"按钮
 *   - 三种决策都点后弹 WriteConfirmModal 二次确认
 *   - 父组件负责把 editedContent 传进来 (作为 modified_content 提交)
 *   - 提交成功后清空 comment 和 confirmModal 状态
 *
 * Props:
 *   - disabled: reviewer 未填时为 true
 *   - isEditing: 当前是否在 modified 编辑模式 (DiffViewer 已经显示了 textarea)
 *   - canSubmitModified: 父组件判定 modified 是否可提交 (已编辑 + 跟原版不同; 由父组件算)
 *   - editedContent: 当前编辑内容 (用于确认 modal 预览 + 提交)
 *   - originalNewContent: 模型给的原始新文件, 用于还原按钮 + diff 统计
 *   - onStartEdit: 点 "✎ 修改" 按钮 -> 通知父组件开编辑模式
 *   - onCancelEdit: 取消编辑 (关闭 DiffViewer textarea)
 *   - onSubmit: 弹 modal -> 确认后真的提交
 */

import { useState } from 'react'
import { Textarea } from '@/components/ui/textarea'
import type { DecisionIn } from '@/lib/api'
import {
  WriteConfirmModal,
  type DecisionKind,
} from '@/components/WriteConfirmModal'
import { ConfirmModal } from '@/components/ConfirmModal'

interface Props {
  disabled: boolean
  /** 当前是否在 modified 编辑模式 (DiffViewer textarea 已显示) */
  isEditing: boolean
  /** 用于 modified 决策的 modified_content (用户编辑后的全文) */
  editedContent?: string | null
  /** 模型给的原始 new_content, 用于"还原"按钮 + 比对统计 (Optional, 不传则 isEditing 控制不显示 status) */
  originalNewContent?: string | null
  /** reviewer 名 (用于 modal 预览) */
  reviewer: string
  onStartEdit?: () => void
  onCancelEdit?: () => void
  /** comment 必填 trim 后非空 */
  onSubmit: (body: DecisionIn) => Promise<void> | void
}

export function DecisionForm({
  disabled,
  isEditing,
  editedContent,
  originalNewContent,
  reviewer,
  onStartEdit,
  onCancelEdit,
  onSubmit,
}: Props) {
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  // 二次确认 modal state (决策提交)
  const [pending, setPending] = useState<DecisionKind | null>(null)
  // 取消编辑的二次确认 — 单独的 state (避免和"提交决策" modal 冲突)
  const [confirmingCancelEdit, setConfirmingCancelEdit] = useState(false)

  const trimmedComment = comment.trim()
  const commentValid = trimmedComment.length > 0
  // modified 决策的"可以走确认": 编辑过 / 内容跟原 new_content 不一样
  const modifiedReady =
    isEditing && editedContent !== undefined && editedContent !== null

  const handleClickDecision = (kind: DecisionKind) => {
    if (disabled) return
    if (!commentValid) {
      // comment 必填 — form 上层按钮 disabled 已经处理
      return
    }
    setPending(kind)
  }

  const handleConfirmSubmit = async () => {
    if (!pending) return
    const body: DecisionIn = {
      decision: pending,
      comment: trimmedComment,
      modified_content: pending === 'modified' ? editedContent ?? null : null,
      reviewer,
    } as DecisionIn
    setSubmitting(true)
    try {
      await onSubmit(body)
      setPending(null)
      setComment('')
      // 编辑模式 onCancelEdit 也由父组件自己关 (传 editedContent=null)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="space-y-2">
      {/* 编辑模式提示 + 取消编辑按钮 (按 确认 才清, 否则不动) */}
      {isEditing && (
        <div className="flex items-center justify-between rounded border border-amber-300 bg-amber-50 px-2 py-1 text-[11px]">
          <span className="text-amber-900">
            📝 编辑模式已开启, 在中间右侧 textarea 修改
          </span>
          {onCancelEdit && (
            <button
              type="button"
              onClick={() => {
                if (submitting) return
                // 弹统一的 ConfirmModal (与提交评审对话框同款样式)
                setConfirmingCancelEdit(true)
              }}
              disabled={submitting}
              className="text-amber-900 hover:underline disabled:opacity-50"
              title="退出编辑模式 (你的修改不会保留)"
            >
              取消编辑
            </button>
          )}
        </div>
      )}

      {/* comment 必填 */}
      <div className="space-y-1">
        <label className="text-[11px] text-muted-foreground flex items-center gap-1">
          评审理由 <span className="text-destructive">*</span>
          <span className="text-muted-foreground/60">(必填, 不少于 1 个字)</span>
        </label>
        <Textarea
          placeholder="例如: 同意, 因为..."
          rows={2}
          value={comment}
          onChange={e => setComment(e.target.value)}
          disabled={disabled || submitting}
          className={!commentValid && comment.length > 0 ? 'border-destructive' : ''}
        />
        {!commentValid && (
          <p className="text-[10px] text-destructive">请填写评审理由</p>
        )}
      </div>

      {/* 三个决策按钮 */}
      <div className="flex justify-end gap-2 pt-1">
        <button
          type="button"
          onClick={() => handleClickDecision('rejected')}
          disabled={disabled || submitting || !commentValid}
          className="px-3 py-1.5 text-sm rounded border border-red-300 bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          ✕ 拒绝
        </button>
        <button
          type="button"
          onClick={onStartEdit}
          disabled={disabled || submitting || isEditing}
          className="px-3 py-1.5 text-sm rounded border border-amber-300 bg-amber-50 text-amber-700 hover:bg-amber-100 disabled:opacity-50 disabled:cursor-not-allowed"
          title={isEditing ? '已在编辑模式' : '点击开启编辑模式, 在 DiffViewer 右栏修改文件'}
        >
          {isEditing ? '编辑中...' : '✎ 修改'}
        </button>
        <button
          type="button"
          onClick={() => handleClickDecision('approved')}
          disabled={disabled || submitting || !commentValid}
          className="px-3 py-1.5 text-sm rounded bg-green-600 text-white hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          ✓ 通过
        </button>
      </div>

      {/* 提交 modified 时: 一个独立的"提交修改" 按钮 (在右栏文本已编辑 + 跟原版不同后才 enable)
          它点开 modal, modal 预览包含 modified 摘要.
          注意: ✎ 修改 按钮只切换"编辑模式开关" (开关本身, 不提交). 真提交靠这个独立按钮. */}
      {isEditing && (
        <button
          type="button"
          onClick={() => handleClickDecision('modified')}
          disabled={
            disabled ||
            submitting ||
            !commentValid ||
            !modifiedReady ||
            // 如果用户改了又还原成原模型版本, 不让提交 modified (没有意义)
            editedContent === originalNewContent
          }
          className="w-full px-3 py-1.5 text-sm rounded border border-amber-300 bg-amber-100 text-amber-900 hover:bg-amber-200 disabled:opacity-50 disabled:cursor-not-allowed"
          title="把右侧 textarea 当前内容作为 modified_content 提交"
        >
          提交修改 (modified)
        </button>
      )}

      {/* 二次确认 modal */}
      <WriteConfirmModal
        open={pending !== null}
        reviewer={reviewer}
        decision={pending ?? 'approved'}
        comment={trimmedComment}
        modifiedContent={pending === 'modified' ? editedContent ?? null : null}
        submitting={submitting}
        onCancel={() => !submitting && setPending(null)}
        onConfirm={handleConfirmSubmit}
      />

      {/* 取消编辑的二次确认 (与提交评审对话框同款样式) */}
      <ConfirmModal
        open={confirmingCancelEdit}
        title="退出编辑模式?"
        titleTag={{ text: '取消编辑', colorClass: 'text-amber-700' }}
        description="当前右侧 textarea 里的修改不会被保留, 你确定要退出编辑模式吗?"
        items={[
          {
            k: '当前改动',
            v: editedContent !== null && editedContent !== undefined ? (
              <span className="font-mono text-xs break-all">
                {editedContent.length > 80
                  ? `${editedContent.slice(0, 80)}...` + ` (${editedContent.length} 字)`
                  : editedContent || <em className="text-muted-foreground">(空)</em>}
              </span>
            ) : (
              <em className="text-muted-foreground">(未编辑)</em>
            ),
          },
        ]}
        primaryLabel="退出编辑"
        primaryVariant="danger"
        cancelLabel="保留并继续编辑"
        onCancel={() => setConfirmingCancelEdit(false)}
        onConfirm={() => {
          setConfirmingCancelEdit(false)
          onCancelEdit?.()
        }}
      />

      {disabled && (
        <p className="text-xs text-destructive text-center">
          请先填写顶部"评审人"再提交
        </p>
      )}
    </div>
  )
}
