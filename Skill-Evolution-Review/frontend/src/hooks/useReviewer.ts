/**
 * frontend/src/hooks/useReviewer.ts — 全局 reviewer 名字 + 必填联动
 *
 * 持久化到 localStorage, 刷新页面不丢. 多个组件共享同一个 reviewer state.
 */

import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'review-system:reviewer'

function loadInitial(): string {
  try {
    return localStorage.getItem(STORAGE_KEY) ?? ''
  } catch {
    return ''
  }
}

let listeners: Array<(v: string) => void> = []
let cachedValue: string | null = null

function getValue(): string {
  if (cachedValue === null) cachedValue = loadInitial()
  return cachedValue
}

function setValue(v: string) {
  cachedValue = v
  try { localStorage.setItem(STORAGE_KEY, v) } catch { /* ignore */ }
  listeners.forEach(l => l(v))
}

export function useReviewer() {
  const [value, setLocal] = useState<string>(getValue)

  useEffect(() => {
    const cb = (v: string) => setLocal(v)
    listeners.push(cb)
    return () => {
      listeners = listeners.filter(l => l !== cb)
    }
  }, [])

  const update = useCallback((v: string) => setValue(v), [])

  return {
    reviewer: value,
    setReviewer: update,
    /** 给 disabled 联动用: 没填 reviewer 时按钮全禁 */
    isReady: value.trim().length > 0,
  }
}
