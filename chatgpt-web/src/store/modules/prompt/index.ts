import { defineStore } from 'pinia'
import type { PromptStore, PromptItem } from './helper'
import { getLocalPromptList, setLocalPromptList, exportPromptList, importPromptList } from './helper'
import { savePromptTemplates } from '@/api'

export const usePromptStore = defineStore('prompt-store', {
  state: (): PromptStore => getLocalPromptList(),

  actions: {
    updatePromptList(promptList: PromptItem[]) {
      this.$patch({ promptList: promptList as any })
      setLocalPromptList({ promptList })
    },
    getPromptList() {
      return this.$state
    },
    // 添加新的提示词
    async addPrompt(prompt: PromptItem) {
      this.promptList.push(prompt)
      setLocalPromptList({ promptList: this.promptList as any })
      // 同时保存到后端
      await savePromptTemplates(this.promptList)
    },
    // 删除提示词
    async removePrompt(key: string) {
      this.promptList = this.promptList.filter(item => item.key !== key)
      setLocalPromptList({ promptList: this.promptList as any })
      // 同时保存到后端
      await savePromptTemplates(this.promptList)
    },
    // 更新提示词
    async updatePrompt(key: string, updatedPrompt: PromptItem) {
      const index = this.promptList.findIndex(item => item.key === key)
      if (index !== -1) {
        this.promptList[index] = updatedPrompt
        setLocalPromptList({ promptList: this.promptList as any })
        // 同时保存到后端
        await savePromptTemplates(this.promptList)
      }
    },
    // 导出提示词
    exportPromptList() {
      exportPromptList()
    },
    // 导入提示词
    async importPromptList(file: File) {
      await importPromptList(file)
      // 重新加载状态
      const updatedStore = getLocalPromptList()
      this.$patch({ promptList: updatedStore.promptList as any })
      // 同时保存到后端
      await savePromptTemplates(updatedStore.promptList)
    },
    // 重置提示词（清空并恢复默认预设）
    async resetPromptList(defaultPrompts: PromptItem[] = []) {
      this.promptList = defaultPrompts
      setLocalPromptList({ promptList: defaultPrompts as any })
      // 同时保存到后端
      await savePromptTemplates(defaultPrompts)
    }
  },
})
