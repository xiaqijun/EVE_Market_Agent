import { describe, it, expect, beforeEach } from 'vitest'
import { useMarketStore } from '../marketStore'

describe('marketStore', () => {
  beforeEach(() => {
    useMarketStore.setState({ opportunities: [] })
  })

  it('starts with empty opportunities', () => {
    expect(useMarketStore.getState().opportunities).toHaveLength(0)
  })

  it('setOpportunities replaces list', () => {
    const { setOpportunities } = useMarketStore.getState()
    const items = [
      { id: '1', type: 'arbitrage', item: '三钛合金', profit: '+8%', score: 9, risk: 'low' },
      { id: '2', type: 'investment', item: '伊甸币', profit: '+15%', score: 8, risk: 'medium' },
    ]
    setOpportunities(items)
    expect(useMarketStore.getState().opportunities).toHaveLength(2)
    expect(useMarketStore.getState().opportunities[0].item).toBe('三钛合金')
  })
})
