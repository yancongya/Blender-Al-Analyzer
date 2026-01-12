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
            const providerName = aiSettings.provider
            let modelName = 'deepseek-chat'
            // 优先使用传入的 aiSettings 中的模型名称
            if (providerName === 'DEEPSEEK') modelName = aiSettings.deepseek?.model || this.$state.ai.deepseek?.model || 'deepseek-chat'
            else if (providerName === 'OLLAMA') modelName = aiSettings.ollama?.model || this.$state.ai.ollama?.model || 'gemma3:4b-it-qat'
            else if (providerName === 'BIGMODEL') modelName = aiSettings.bigmodel?.model || this.$state.ai.bigmodel?.model || 'glm-4.5-air'
            aiSettings.provider = {
              name: providerName,
              model: modelName
            }
          } else if (typeof aiSettings.provider === 'object' && aiSettings.provider.name) {
            // 如果已经是对象格式，确保它包含model
            const providerName = aiSettings.provider.name
            let modelName = aiSettings.provider.model
            if (!modelName) {
              // 优先使用传入的 aiSettings 中的模型名称
              if (providerName === 'DEEPSEEK') modelName = aiSettings.deepseek?.model || this.$state.ai.deepseek?.model || 'deepseek-chat'
              else if (providerName === 'OLLAMA') modelName = aiSettings.ollama?.model || this.$state.ai.ollama?.model || 'gemma3:4b-it-qat'
              else if (providerName === 'BIGMODEL') modelName = aiSettings.bigmodel?.model || this.$state.ai.bigmodel?.model || 'glm-4.5-air'
              else modelName = 'deepseek-chat'
            }
            aiSettings.provider = {
              name: providerName,
              model: modelName
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
