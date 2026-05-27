import { describe, it, expect, beforeEach } from 'vitest'
import { useSettingsStore } from '../settingsStore'

describe('settingsStore', () => {
  beforeEach(() => {
    useSettingsStore.setState({
      settings: { risk_level: 'moderate', min_profit_margin: 5, max_position_pct: 10 }
    })
  })

  it('starts with default settings', () => {
    const { settings } = useSettingsStore.getState()
    expect(settings.risk_level).toBe('moderate')
    expect(settings.min_profit_margin).toBe(5)
    expect(settings.max_position_pct).toBe(10)
  })

  it('setSettings updates settings', () => {
    const { setSettings } = useSettingsStore.getState()
    setSettings({ risk_level: 'aggressive', min_profit_margin: 10 })
    expect(useSettingsStore.getState().settings.risk_level).toBe('aggressive')
    expect(useSettingsStore.getState().settings.min_profit_margin).toBe(10)
  })
})
