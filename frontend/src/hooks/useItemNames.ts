import { useEffect, useRef } from 'react'
import { useSdeStore } from '../stores/sdeStore'
import { useAuthStore } from '../stores/authStore'

const API = '/api/v1'

const BATCH_INTERVAL = 200
const MAX_BATCH = 100

export function useItemNames(typeIds: (number | null | undefined)[]) {
  const token = useAuthStore(s => s.token)
  const { names, fetching, setNames, addFetching } = useSdeStore()
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const pendingRef = useRef<Set<number>>(new Set())

  useEffect(() => {
    if (!token) return
    const missing = typeIds.filter((id): id is number =>
      id != null && !names[id] && !fetching.has(id)
    )
    if (!missing.length) return

    missing.forEach(id => pendingRef.current.add(id))
    addFetching(missing)

    if (timerRef.current) clearTimeout(timerRef.current)
    timerRef.current = setTimeout(async () => {
      const ids = Array.from(pendingRef.current).slice(0, MAX_BATCH)
      pendingRef.current.clear()
      if (!ids.length) return

      try {
        const url = `${API}/market/items/batch?ids=${ids.join(',')}`
        const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
        if (!res.ok) return
        const data = await res.json()
        if (data.items) {
          const names: Record<number, string> = {}
          Object.entries(data.items).forEach(([id, item]: [string, any]) => {
            names[Number(id)] = item.name ?? String(id)
          })
          setNames(names)
        }
      } catch {}
    }, BATCH_INTERVAL)

    return () => { if (timerRef.current) clearTimeout(timerRef.current) }
  }, [typeIds.join(','), token])

  return (typeId: number | null | undefined): string => {
    if (typeId == null) return '—'
    const item = names[typeId]
    return item || `#${typeId}`
  }
}
