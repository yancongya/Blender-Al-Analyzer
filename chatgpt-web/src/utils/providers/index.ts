import { useSettingStore } from '@/store'

export interface ModelOption {
  label: string
  value: string
}

export interface Provider {
  supportsThinking(): boolean
  supportsWebSearch(): boolean
  checkConnectivity(): Promise<boolean>
  listModels(): Promise<ModelOption[]>
  testThinkingSupport(): Promise<boolean>
  testWebSupport(): Promise<boolean>
}

class DeepSeekProvider implements Provider {
  private apiKey: string
  private url: string
  private model: string
  constructor(apiKey: string, url: string, model: string) {
    this.apiKey = apiKey
    this.url = url
    this.model = model
  }
  supportsThinking(): boolean {
    return true
  }
  supportsWebSearch(): boolean {
    return false
  }
  async testThinkingSupport(): Promise<boolean> {
    if (!this.apiKey || !this.url || !this.model) return false
    try {
      const res = await fetch(`${this.url}/chat/completions`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          model: this.model,
          messages: [{ role: 'user', content: '请输出一个任意的一句话' }],
          stream: false,
          temperature: 0,
          thinking: { type: 'enabled' },
          max_tokens: 64,
        }),
      })
      if (!res.ok) return false
      const j = await res.json()
      const choices = Array.isArray(j?.choices) ? j.choices : []
      const msg = choices[0]?.message
      const rc = msg?.reasoning_content
      return typeof rc === 'string' && rc.length > 0
    } catch {
      return false
    }
  }
  async testWebSupport(): Promise<boolean> {
    return false
  }
  async checkConnectivity(): Promise<boolean> {
    if (!this.apiKey) return false
    try {
      const res = await fetch(`${this.url}/models`, {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
        },
      })
      return res.ok
    } catch {
      return false
    }
  }
  async listModels(): Promise<ModelOption[]> {
    const res = await fetch(`${this.url}/models`, {
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        'Content-Type': 'application/json',
      },
    })
    if (!res.ok) return []
    const data = await res.json()
    if (data && Array.isArray(data.data)) {
      const list: ModelOption[] = data.data.map((m: any) => ({
        label: m.id || m.name || 'Unknown Model',
        value: m.id || m.name || 'unknown',
      }))
      if (list.length > 0 && !list.some(i => i.value === this.model)) {
        this.model = list[0].value
      }
      return list
    }
    return []
  }
}

class OllamaProvider implements Provider {
  private url: string
  private model: string
  constructor(url: string, model: string) {
    this.url = url
    this.model = model
  }
  supportsThinking(): boolean {
    return false
  }
  supportsWebSearch(): boolean {
    return false
  }
  async testThinkingSupport(): Promise<boolean> {
    return false
  }
  async testWebSupport(): Promise<boolean> {
    return false
  }
  async checkConnectivity(): Promise<boolean> {
    try {
      const res = await fetch(`${this.url}/api/tags`, {
        headers: { 'Content-Type': 'application/json' },
      })
      return res.ok
    } catch {
      return false
    }
  }
  async listModels(): Promise<ModelOption[]> {
    const res = await fetch(`${this.url}/api/tags`, {
      headers: { 'Content-Type': 'application/json' },
    })
    if (!res.ok) return []
    const data = await res.json()
    if (data && Array.isArray(data.models)) {
      const list: ModelOption[] = data.models.map((m: any) => ({
        label: m.name || m.id || 'Unknown Model',
        value: m.name || m.id || 'unknown',
      }))
      if (list.length > 0 && !list.some(i => i.value === this.model)) {
        this.model = list[0].value
      }
      return list
    }
    return []
  }
}

class TestProvider implements Provider {
  supportsThinking(): boolean {
    return true
  }
  supportsWebSearch(): boolean {
    return true
  }
  async checkConnectivity(): Promise<boolean> {
    await Promise.resolve()
    return true
  }
  async listModels(): Promise<ModelOption[]> {
    return [
      { label: 'test-model-a', value: 'test-model-a' },
      { label: 'test-model-b', value: 'test-model-b' },
      { label: 'test-model-c', value: 'test-model-c' },
    ]
  }
  async testThinkingSupport(): Promise<boolean> {
    return true
  }
  async testWebSupport(): Promise<boolean> {
    return true
  }
}

class GenericOpenAIProvider implements Provider {
  private apiKey: string
  private baseUrl: string
  constructor(apiKey: string, baseUrl: string) {
    this.apiKey = apiKey
    this.baseUrl = baseUrl
  }
  supportsThinking(): boolean {
    return false
  }
  supportsWebSearch(): boolean {
    return false
  }
  async testThinkingSupport(): Promise<boolean> {
    // Heuristic: detect reasoning-capable model names
    if (!this.baseUrl || !this.apiKey) return false
    try {
      const res = await fetch(`${this.baseUrl.replace(/\/+$/,'')}/models`, {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
        },
      })
      if (!res.ok) return false
      const data = await res.json()
      const arr = Array.isArray(data?.data) ? data.data
        : Array.isArray(data?.models) ? data.models
        : []
      const names = arr.map((m: any) => (m.id || m.name || '') as string)
      const patterns = [/reasoner/i, /reasoning/i, /\br1\b/i, /think/i]
      return names.some((n: string) => patterns.some(p => p.test(n)))
    } catch {
      return false
    }
  }
  async testWebSupport(): Promise<boolean> {
    if (!this.baseUrl || !this.apiKey) return false
    try {
      const res = await fetch(`${this.baseUrl.replace(/\/+$/,'')}/models`, {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
        },
      })
      if (!res.ok) return false
      const data = await res.json()
      const arr = Array.isArray(data?.data) ? data.data
        : Array.isArray(data?.models) ? data.models
        : []
      const names = arr.map((m: any) => (m.id || m.name || '') as string)
      const patterns = [/web/i, /browse/i, /internet/i, /search/i, /online/i, /sonar/i, /perplexity/i]
      return names.some((n: string) => patterns.some(p => p.test(n)))
    } catch {
      return false
    }
  }
  async checkConnectivity(): Promise<boolean> {
    if (!this.baseUrl) return false
    if (!this.apiKey) return false
    try {
      const res = await fetch(`${this.baseUrl.replace(/\/+$/,'')}/models`, {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
        },
      })
      return res.ok
    } catch {
      return false
    }
  }
  async listModels(): Promise<ModelOption[]> {
    if (!this.baseUrl) return []
    try {
      const res = await fetch(`${this.baseUrl.replace(/\/+$/,'')}/models`, {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
        },
      })
      if (!res.ok) return []
      const data = await res.json()
      const arr = Array.isArray(data?.data) ? data.data
        : Array.isArray(data?.models) ? data.models
        : []
      return arr.map((m: any) => ({
        label: m.id || m.name || 'Unknown Model',
        value: m.id || m.name || 'unknown',
      }))
    } catch {
      return []
    }
  }
}

export function createProvider(): Provider {
  const setting = useSettingStore()
  // 处理新的provider结构
  const p = typeof setting.ai?.provider === 'object'
    ? setting.ai.provider.name
    : setting.ai?.provider
  if (p === 'DEEPSEEK') {
    return new DeepSeekProvider(setting.ai.deepseek.api_key, setting.ai.deepseek.url, setting.ai.deepseek.model)
  }
  if (p === 'OLLAMA') {
    return new OllamaProvider(setting.ai.ollama.url, setting.ai.ollama.model)
  }
  const cfg = setting.ai?.provider_configs?.[p || '']
  if (cfg) {
    return new GenericOpenAIProvider(cfg.api_key, cfg.base_url)
  }
  return new TestProvider()
}
