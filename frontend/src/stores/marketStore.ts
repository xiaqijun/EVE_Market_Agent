import { create } from 'zustand'

interface Opportunity { id: string; type: string; item: string; profit: string; score: number; risk: string }

interface MarketState {
  opportunities: Opportunity[]
  setOpportunities: (items: Opportunity[]) => void
}

export const useMarketStore = create<MarketState>((set) => ({
  opportunities: [],
  setOpportunities: (items) => set({ opportunities: items }),
}))
