import { describe, it, expect, beforeEach } from 'vitest'
import { useSdeStore } from '../sdeStore'

describe('sdeStore', () => {
  beforeEach(() => {
    useSdeStore.setState({ names: {}, fetching: new Set() })
  })

  it('starts with empty names', () => {
    expect(Object.keys(useSdeStore.getState().names)).toHaveLength(0)
  })

  it('setNames adds items to cache', () => {
    const { setNames } = useSdeStore.getState()
    setNames({ 34: '三钛合金', 35: '类晶体胶矿' })
    expect(useSdeStore.getState().names[34]).toBe('三钛合金')
    expect(useSdeStore.getState().names[35]).toBe('类晶体胶矿')
  })

  it('setNames merges with existing', () => {
    const { setNames } = useSdeStore.getState()
    setNames({ 34: '三钛合金' })
    setNames({ 35: '类晶体胶矿' })
    expect(useSdeStore.getState().names[34]).toBe('三钛合金')
    expect(useSdeStore.getState().names[35]).toBe('类晶体胶矿')
  })

  it('addFetching tracks fetching IDs', () => {
    const { addFetching } = useSdeStore.getState()
    addFetching([34, 35])
    expect(useSdeStore.getState().fetching.has(34)).toBe(true)
    expect(useSdeStore.getState().fetching.has(35)).toBe(true)
  })

  it('setNames does not overwrite with undefined', () => {
    const { setNames } = useSdeStore.getState()
    setNames({ 34: '三钛合金' })
    setNames({ 35: '类晶体胶矿' })
    expect(useSdeStore.getState().names[34]).toBe('三钛合金')
  })
})
