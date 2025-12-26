import { ss } from '@/utils/storage'

const LOCAL_NAME = 'promptStore'

export interface PromptItem {
  key: string
  value: string
  desc?: string
  createdAt: number
}

export type PromptList = PromptItem[]

export interface PromptStore {
  promptList: PromptList
}

export function getLocalPromptList(): PromptStore {
  const promptStore: PromptStore | undefined = ss.get(LOCAL_NAME)
  // 确保返回的数据符合PromptItem类型
  const storedData = promptStore ?? { promptList: [] }
  // 为没有createdAt字段的旧数据添加默认值
  const processedPromptList = storedData.promptList.map(item => ({
    ...item,
    createdAt: item.createdAt || Date.now()
  }))
  return { promptList: processedPromptList }
}

export function setLocalPromptList(promptStore: PromptStore): void {
  ss.set(LOCAL_NAME, promptStore)
}

// 导出提示词为JSON文件
export function exportPromptList(): void {
  const promptStore = getLocalPromptList()
  const dataStr = JSON.stringify(promptStore, null, 2)
  const dataUri = 'data:application/json;charset=utf-8,' + encodeURIComponent(dataStr)

  const exportFileDefaultName = `prompt-store-${new Date().toISOString().slice(0, 19)}.json`

  const linkElement = document.createElement('a')
  linkElement.setAttribute('href', dataUri)
  linkElement.setAttribute('download', exportFileDefaultName)
  linkElement.click()
}

// 从JSON文件导入提示词
export function importPromptList(file: File): Promise<void> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => {
      try {
        const content = e.target?.result as string
        const importedData: PromptStore = JSON.parse(content)

        if (importedData && Array.isArray(importedData.promptList)) {
          // 验证导入的数据格式
          const validPrompts = importedData.promptList.filter(item =>
            typeof item.key === 'string' && typeof item.value === 'string'
          )

          // 合并现有提示词和导入的提示词，避免重复
          const currentStore = getLocalPromptList()
          const currentKeys = new Set(currentStore.promptList.map(item => item.key))

          const uniqueImportedPrompts = validPrompts.filter(item => !currentKeys.has(item.key))

          const mergedPrompts = [...currentStore.promptList, ...uniqueImportedPrompts]

          setLocalPromptList({ promptList: mergedPrompts })
          resolve()
        } else {
          reject(new Error('Invalid prompt store format'))
        }
      } catch (error) {
        reject(new Error('Failed to parse imported file'))
      }
    }
    reader.onerror = () => reject(new Error('Failed to read file'))
    reader.readAsText(file)
  })
}
