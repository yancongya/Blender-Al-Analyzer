import { ss } from '@/utils/storage'

const LOCAL_NAME = 'settingsStorage'

export interface SettingsState {
  systemMessage: string
  systemMessagePresets?: { label: string; value: string }[]
  defaultQuestionPresets?: { label: string; value: string }[]
  outputDetailLevel: 'simple' | 'medium' | 'detailed'
  outputDetailPresets: {
    simple: string
    medium: string
    detailed: string
  }
  temperature: number
  top_p: number
  assistantAvatar?: string
  ai: {
    provider: string | { name: string; model: string }  // 支持新旧两种格式
    // 兼容旧字段：仍保留以避免现有逻辑破坏
    deepseek: { api_key: string; model: string; url: string; models: string[] }
    ollama: { url: string; model: string; models: string[] }
    bigmodel: { api_key: string; model: string; url: string; models: string[] }
    // 新增：通用多服务商配置
    provider_configs: Record<string, { base_url: string; api_key: string; default_model?: string; models: string[] }>
    web_search: { enabled: boolean; provider: string; tavily_api_key: string }
    thinking: { enabled: boolean }
    networking: { enabled: boolean }
    memory: { enabled: boolean; target_k: number }
    system_prompt: string
  }
}

export function defaultSetting(): SettingsState {
  return {
    systemMessage: 'You are ChatGPT, a large language model trained by OpenAI. Follow the user\'s instructions carefully. Respond using markdown.',
    systemMessagePresets: [
      { label: 'Default', value: 'You are ChatGPT, a large language model trained by OpenAI. Follow the user\'s instructions carefully. Respond using markdown.' },
      { label: 'Blender Expert', value: 'You are an expert in Blender nodes. Analyze the following node structure and provide insights, optimizations, or explanations.' },
      { label: 'Python Coder', value: 'You are an expert Python developer specialized in Blender API (bpy).' },
    ],
    defaultQuestionPresets: [
      { label: 'Analyze Nodes', value: 'Please analyze the function of these nodes and suggestions for optimization' },
      { label: 'Explain Nodes', value: 'Explain what these nodes do in simple terms.' },
    ],
    outputDetailLevel: 'medium',
    outputDetailPresets: {
      simple: '请简要说明，不需要使用markdown格式，简单描述即可。',
      medium: '请按常规方式回答，使用适当的markdown格式来组织内容。',
      detailed: '请详细说明，使用图表、列表、代码块等markdown格式来清晰地表达内容。'
    },
    temperature: 0.8,
    top_p: 1,
    ai: {
      provider: { name: 'DEEPSEEK', model: 'deepseek-chat' }, // 使用新的provider结构
      deepseek: { api_key: '', model: 'deepseek-chat', url: 'https://api.deepseek.com', models: [] },
      ollama: { url: 'http://localhost:11434', model: 'llama2', models: [] },
      bigmodel: { api_key: '', model: 'glm-4', url: 'https://open.bigmodel.cn/api/paas/v4', models: [] },
      provider_configs: {
        DEEPSEEK: { base_url: 'https://api.deepseek.com', api_key: '', default_model: '', models: [] },
        OLLAMA: { base_url: 'http://localhost:11434', api_key: '', default_model: '', models: [] },
        BIGMODEL: { base_url: 'https://open.bigmodel.cn/api/paas/v4', api_key: '', default_model: '', models: [] },
      },
      web_search: { enabled: false, provider: 'tavily', tavily_api_key: '' },
      thinking: { enabled: false },
      networking: { enabled: true },
      memory: { enabled: true, target_k: 4 },
      system_prompt: 'You are an expert in Blender nodes.',
    },
  }
}

export function getLocalState(): SettingsState {
  const localSetting: SettingsState | undefined = ss.get(LOCAL_NAME)
  return { ...defaultSetting(), ...localSetting }
}

export function setLocalState(setting: SettingsState): void {
  ss.set(LOCAL_NAME, setting)
}

export function removeLocalState() {
  ss.remove(LOCAL_NAME)
}
