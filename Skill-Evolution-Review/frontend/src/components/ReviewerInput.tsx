/**
 * frontend/src/components/ReviewerInput.tsx — 顶部必填 reviewer 输入
 */

import { Input } from '@/components/ui/input'

interface Props {
  value: string
  onChange: (v: string) => void
}

export function ReviewerInput({ value, onChange }: Props) {
  const empty = value.trim().length === 0
  return (
    <div className="flex items-center gap-2">
      <label htmlFor="reviewer" className="text-sm font-medium whitespace-nowrap">
        评审人 <span className="text-destructive">*</span>
      </label>
      <Input
        id="reviewer"
        placeholder="请输入你的名字"
        value={value}
        onChange={e => onChange(e.target.value)}
        className={empty ? 'border-destructive' : ''}
        maxLength={64}
      />
      {empty && (
        <span className="text-xs text-destructive">必填, 不填不能提交评审</span>
      )}
    </div>
  )
}
