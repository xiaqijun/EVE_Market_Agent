import { create } from 'zustand'

interface Settings { llm_provider?: string; risk_level?: string; min_profit_margin?: number; max_position_pct?: number }

interface SettingsState { settings: Settings; setSettings: (s: Settings) => void }

export const useSettingsStore = create<SettingsState>((set) => ({
  settings: { risk_level: 'moderate', min_profit_margin: 5, max_position_pct: 10 },
  setSettings: (s) => set({ settings: s }),
}))
