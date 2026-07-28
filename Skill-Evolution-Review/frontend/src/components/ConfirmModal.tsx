/**
 * frontend/src/components/ConfirmModal.tsx — 通用二次确认弹窗 (shadcn-style)
 *
 * 设计:
 *   - 浮在整页之上的 modal (fixed 全屏背景遮罩 + 居中卡片)
 *   - 标题 + 可选描述 + 可变 k-v 内容列表 + 底部按钮 (取消 / 主按钮)
 *   - Escape = 取消; Enter = 确认 (textarea/input 中按 Enter 不触发)
 *   - 主按钮样式: primary (蓝) 或 danger (红)
 *   - submitting 时按钮 disable + 显示 "处理中..."
 *
 * 使用场景:
 *   - 提交评审 (WriteConfirmModal)
 *   - 取消编辑模式 (DecisionForm)
 *   - 还原回模型版 (DiffViewer)
 *   - 任何需要"是/否"的二次确认
 */

import { useEffect, useRef } from 'react'

export interface ConfirmItem {
  k: string
  v: React.ReactNode
}

interface Props {
  open: boolean
  /** 标题 (大字号, 顶部) */
  title: string
  /** 标签形式附加在标题右侧 (如 "[通过]" / "[取消编辑]") */
  titleTag?: { text: string; colorClass?: string }
  /** 描述 — 顶部标题下方一行说明 (可选) */
  description?: string
  /** 中间 k-v 列表 */
  items: ConfirmItem[]
  /** 主按钮文本, 默认 "确认" */
  primaryLabel?: string
  /** 主按钮 variant: 'primary' (默认) 或 'danger' */
  primaryVariant?: 'primary' | 'danger'
  /** 取消按钮文本, 默认 "取消" */
  cancelLabel?: string
  /** 主按钮禁用 + 显示 "处理中..." */
  submitting?: boolean
  onCancel: () => void
  onConfirm: () => void
}

const PRIMARY_VARIANT_CLASS: Record<NonNullable<Props['primaryVariant']>, string> = {
  primary: 'bg-primary text-primary-foreground hover:bg-primary/90',
  danger: 'bg-red-600 text-white hover:bg-red-700',
}

export function ConfirmModal({
  open,
  title,
  titleTag,
  description,
  items,
  primaryLabel = '确认',
  primaryVariant = 'primary',
  cancelLabel = '取消',
  submitting,
  onCancel,
  onConfirm,
}: Props) {
  // 防止 useEffect deps 在父组件没传 stable callback 时反复 add/remove 监听
  // —— 把 callback ref 起来, useEffect 用 ref
  const onCancelRef = useRef(onCancel)
  const onConfirmRef = useRef(onConfirm)
  onCancelRef.current = onCancel
  onConfirmRef.current = onConfirm

  // Escape 关闭 / Enter 确认
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        if (!submitting) onCancelRef.current()
      } else if (e.key === 'Enter' && !submitting) {
        // textarea / input 中的 Enter 不应触发 (用户在打备注)
        const tag = (e.target as HTMLElement | null)?.tagName ?? ''
        if (tag === 'TEXTAREA' || tag === 'INPUT') return
        e.preventDefault()
        onConfirmRef.current()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, submitting])

  if (!open) return null

  return (
    <div
      className="fixed inset-0 z-50 bg-black/40 flex items-center justify-center p-4"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget && !submitting) onCancel()
      }}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-modal-title"
        className="bg-background border rounded-lg shadow-xl max-w-lg w-full p-5 space-y-4"
      >
        {/* title row */}
        <div className="flex items-center gap-2 flex-wrap">
          <h2 id="confirm-modal-title" className="text-base font-semibold">
            {title}
          </h2>
          {titleTag && (
            <span className={`text-sm font-semibold ${titleTag.colorClass ?? 'text-foreground'}`}>
              [{titleTag.text}]
            </span>
          )}
        </div>

        {description && (
          <p className="text-sm text-muted-foreground">{description}</p>
        )}

        {/* items table */}
        <div className="space-y-1.5 text-sm">
          {items.map((it, i) => (
            <Row key={i} k={it.k} v={it.v} />
          ))}
        </div>

        {/* buttons */}
        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={submitting}
            className="px-3 py-1.5 text-sm rounded border bg-background hover:bg-muted disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={submitting}
            className={`px-3 py-1.5 text-sm rounded disabled:opacity-50 ${PRIMARY_VARIANT_CLASS[primaryVariant]}`}
          >
            {submitting ? '处理中...' : primaryLabel}
          </button>
        </div>

        <p className="text-[10px] text-muted-foreground">
          按 <kbd className="border rounded px-1">Enter</kbd> 确认 / <kbd className="border rounded px-1">Esc</kbd> 取消
        </p>
      </div>
    </div>
  )
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex gap-2">
      <span className="w-24 shrink-0 text-muted-foreground">{k}</span>
      <span className="flex-1 min-w-0">{v}</span>
    </div>
  )
}
