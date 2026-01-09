import { defineStore } from 'pinia'
import type { SettingsState } from './helper'
import { defaultSetting, getLocalState, removeLocalState, setLocalState } from './helper'

export const useSettingStore = defineStore('setting-store', {
  state: (): SettingsState => getLocalState(),
  actions: {
    updateSetting(settings: Partial<SettingsState>) {
      if (settings.ai) {
        // 处理provider兼容性
        const aiSettings = { ...settings.ai }
        if (aiSettings.provider) {
          // 如果provider是字符串，转换为对象格式
          if (typeof aiSettings.provider === 'string') {
            aiSettings.provider = {
              name: aiSettings.provider,
              model: (typeof this.$state.ai.provider === 'object' ? this.$state.ai.provider?.model : undefined) || this.$state.ai.deepseek?.model || 'deepseek-chat'
            }
          } else if (typeof aiSettings.provider === 'object' && aiSettings.provider.name) {
            // 如果已经是对象格式，确保它包含model
            aiSettings.provider = {
              name: aiSettings.provider.name,
              model: aiSettings.provider.model || (typeof this.$state.ai.provider === 'object' ? this.$state.ai.provider?.model : undefined) || this.$state.ai.deepseek?.model || 'deepseek-chat'
            }
          }
        }

        this.$state.ai = { ...this.$state.ai, ...aiSettings }
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
