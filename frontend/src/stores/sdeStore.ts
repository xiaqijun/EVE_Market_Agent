import { create } from 'zustand'

interface SdeState {
  names: Record<number, string>
  fetching: Set<number>
  setNames: (items: Record<number, string>) => void
  addFetching: (ids: number[]) => void
}

export const useSdeStore = create<SdeState>((set) => ({
  names: {},
  fetching: new Set(),
  setNames: (items) => set((s) => ({ names: { ...s.names, ...items } })),
  addFetching: (ids) => set((s) => {
    const next = new Set(s.fetching)
    ids.forEach(id => next.add(id))
    return { fetching: next }
  }),
}))
