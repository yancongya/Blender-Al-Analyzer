import { defineStore } from 'pinia'
import type { SettingsState } from './helper'
import { defaultSetting, getLocalState, removeLocalState, setLocalState } from './helper'

export const useSettingStore = defineStore('setting-store', {
  state: (): SettingsState => getLocalState(),
  actions: {
    updateSetting(settings: Partial<SettingsState>) {
      if (settings.ai) {
        this.$state.ai = { ...this.$state.ai, ...settings.ai }
        const { ai, ...rest } = settings
        this.$state = { ...this.$state, ...rest }
      }
      else {
        this.$state = { ...this.$state, ...settings }
      }
      this.recordState()
    },

    addSystemMessagePreset(preset: { label: string; value: string }) {
      if (!this.$state.systemMessagePresets) {
        this.$state.systemMessagePresets = []
      }
      this.$state.systemMessagePresets.push(preset)
      this.recordState()
    },

    addDefaultQuestionPreset(preset: { label: string; value: string }) {
      if (!this.$state.defaultQuestionPresets) {
        this.$state.defaultQuestionPresets = []
      }
      this.$state.defaultQuestionPresets.push(preset)
      this.recordState()
    },

    resetSetting() {
      this.$state = defaultSetting()
      removeLocalState()
    },

    recordState() {
      setLocalState(this.$state)
    },
  },
})
