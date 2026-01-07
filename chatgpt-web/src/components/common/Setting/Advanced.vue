<script lang="ts" setup>
import { ref, computed, watch, onMounted } from 'vue'
import { NButton, NInput, NSlider, NSelect, NSwitch, useMessage, NModal, NTag } from 'naive-ui'
import { useSettingStore } from '@/store'
import type { SettingsState } from '@/store/modules/settings/helper'
import { t } from '@/locales'
import { updateSettings as apiUpdateSettings } from '@/api'
import { createProvider } from '@/utils/providers'

const settingStore = useSettingStore()

const ms = useMessage()

const temperature = ref(settingStore.temperature ?? 0.5)

const top_p = ref(settingStore.top_p ?? 1)

const ai = ref(settingStore.ai)

// 角色与默认问题迁移到 Prompt 标签页


// 确保DeepSeek有默认URL
if (!ai.value.deepseek.url) {
  ai.value.deepseek.url = 'https://api.deepseek.com'
}

// 重置DeepSeek URL为默认值
function resetDeepSeekUrl() {
  ai.value.deepseek.url = 'https://api.deepseek.com'
  updateAiSettings()
}

// 定义模型选项类型
interface ModelOption {
  label: string
  value: string
}

const deepseekModels = ref<ModelOption[]>([])
const ollamaModels = ref<ModelOption[]>([])
const genericModels = ref<ModelOption[]>([])
const deepseekCustomName = ref('')
const ollamaCustomName = ref('')
const genericCustomName = ref('')
const showAddCustomModelModal = ref(false)
const customModelId = ref('')
const customModelProvider = ref('')
const showDeleteModelModal = ref(false)
const connectivity = ref(false)
const supportsThinking = ref(false)
const supportsModelFetch = ref(false)
const networkingCapable = ref(false)
const testingConn = ref(false)
const testingThink = ref(false)
const testingWeb = ref(false)
const testingModel = ref(false)
const loadingModels = ref(false)

async function fetchDeepSeekModels() {
  loadingModels.value = true
  if (!ai.value.deepseek.api_key) {
    ms.error('请先输入API密钥')
    loadingModels.value = false
    return
  }
  try {
    const response = await fetch(`${ai.value.deepseek.url}/models`, {
      headers: {
        'Authorization': `Bearer ${ai.value.deepseek.api_key}`,
        'Content-Type': 'application/json'
      }
    })
    if (!response.ok) {
      throw new Error(`获取模型列表失败: ${response.status} ${response.statusText}`)
    }
    const data = await response.json()
    if (data && data.data && Array.isArray(data.data)) {
      deepseekModels.value = data.data.map((model: any) => ({
        label: model.id || model.name || 'Unknown Model',
        value: model.id || model.name || 'unknown'
      }))
      const extras = (ai.value.provider_configs?.DEEPSEEK?.models || [])
        .filter(m => !deepseekModels.value.some(o => o.value === m))
        .map(m => ({ label: m, value: m }))
      deepseekModels.value = [...deepseekModels.value, ...extras]
      if (deepseekModels.value.length > 0 &&
          !deepseekModels.value.some(m => m.value === ai.value.deepseek.model)) {
        ai.value.deepseek.model = deepseekModels.value[0].value
      }
    } else {
      ms.error('获取模型列表格式错误')
    }
  } catch (error) {
    console.error('获取模型列表失败:', error)
    ms.error('获取模型列表失败: ' + (error as Error).message)
  } finally {
    loadingModels.value = false
  }
}

async function fetchOllamaModels() {
  loadingModels.value = true
  try {
    const response = await fetch(`${ai.value.ollama.url}/api/tags`, {
      headers: {
        'Content-Type': 'application/json'
      }
    })
    if (!response.ok) {
      throw new Error(`获取模型列表失败: ${response.status} ${response.statusText}`)
    }
    const data = await response.json()
    if (data && data.models && Array.isArray(data.models)) {
      ollamaModels.value = data.models.map((model: any) => ({
        label: model.name || model.id || 'Unknown Model',
        value: model.name || model.id || 'unknown'
      }))
      const extras = (ai.value.provider_configs?.OLLAMA?.models || [])
        .filter(m => !ollamaModels.value.some(o => o.value === m))
        .map(m => ({ label: m, value: m }))
      ollamaModels.value = [...ollamaModels.value, ...extras]
      if (ollamaModels.value.length > 0 &&
          !ollamaModels.value.some(m => m.value === ai.value.ollama.model)) {
        ai.value.ollama.model = ollamaModels.value[0].value
      }
    } else {
      ms.error('获取模型列表格式错误')
    }
  } catch (error) {
    console.error('获取Ollama模型列表失败:', error)
    ms.error('获取Ollama模型列表失败: ' + (error as Error).message)
  } finally {
    loadingModels.value = false
  }
}

const providerLabelMap: Record<string, string> = {
  DEEPSEEK: 'DeepSeek',
  OLLAMA: 'Ollama',
}
const providerOptions = computed(() => {
  const cfgs = ai.value.provider_configs || {}
  const keys = Object.keys(cfgs)
  return keys.map(v => ({ label: providerLabelMap[v] || v, value: v }))
})

// 自定义服务商入口移除
const defaultBaseUrls: Record<string, string> = {
  DEEPSEEK: 'https://api.deepseek.com',
  OLLAMA: 'http://localhost:11434',
}

const currentProviderKey = computed(() => ai.value.provider)
function updateCurrentProviderConfig(partial: { base_url?: string; api_key?: string; default_model?: string }) {
  const key = currentProviderKey.value
  const base = (ai.value.provider_configs || {})[key] || { base_url: '', api_key: '', default_model: '', models: [] }
  ai.value.provider_configs = {
    ...(ai.value.provider_configs || {}),
    [key]: { ...base, ...partial },
  }
  updateAiSettings()
}

function resetGenericUrl() {
  const key = ai.value.provider
  const def = defaultBaseUrls[key] || ''
  updateCurrentProviderConfig({ base_url: def })
}

  onMounted(() => {
    if (ai.value.provider === 'DEEPSEEK') {
      fetchDeepSeekModels()
    } else if (ai.value.provider === 'OLLAMA') {
      fetchOllamaModels()
    } else {
      refreshGenericModels()
    }
    updateProviderCapabilities()
  })

watch(() => ai.value.provider, (newProvider: string) => {
  if (newProvider === 'DEEPSEEK') {
    fetchDeepSeekModels()
  } else if (newProvider === 'OLLAMA') {
    fetchOllamaModels()
  } else {
    refreshGenericModels()
  }
  updateProviderCapabilities()
  updateAiSettings()
})

watch(() => ai.value.deepseek.model, () => {
  if (ai.value.provider === 'DEEPSEEK') updateProviderCapabilities()
  updateAiSettings()
})
watch(() => ai.value.ollama.model, () => {
  if (ai.value.provider === 'OLLAMA') updateProviderCapabilities()
  updateAiSettings()
})
watch(() => ai.value.provider_configs?.[ai.value.provider]?.default_model, () => {
  if (ai.value.provider !== 'DEEPSEEK' && ai.value.provider !== 'OLLAMA') {
    updateProviderCapabilities()
  }
  updateAiSettings()
})
const thinkingDisabled = computed(() => !supportsThinking.value)
const webSearchDisabled = computed(() => !networkingCapable.value)

// 即时保存：思考、联网、记忆、URL、API Key
watch(() => ai.value.thinking.enabled, () => updateAiSettings())
watch(() => ai.value.web_search.enabled, () => updateAiSettings())
watch(() => ai.value.memory.enabled, () => updateAiSettings())
watch(() => ai.value.memory.target_k, () => updateAiSettings())
watch(() => ai.value.deepseek.api_key, () => updateAiSettings())
watch(() => ai.value.deepseek.url, () => updateAiSettings())
watch(() => ai.value.ollama.url, () => updateAiSettings())

async function updateProviderCapabilities() {
  const p = createProvider()
  testingConn.value = true
  try {
    connectivity.value = await p.checkConnectivity()
  } catch {
    connectivity.value = false
  } finally {
    testingConn.value = false
  }
  testingThink.value = true
  try {
    const thinkingOk = await p.testThinkingSupport()
    supportsThinking.value = thinkingOk && connectivity.value
  } catch {
    supportsThinking.value = false
  } finally {
    testingThink.value = false
  }
  testingWeb.value = true
  try {
    const webOk = await p.testWebSupport()
    networkingCapable.value = webOk && connectivity.value
  } catch {
    networkingCapable.value = false
  } finally {
    testingWeb.value = false
  }
  testingModel.value = true
  try {
    const list = await p.listModels()
    supportsModelFetch.value = Array.isArray(list) && list.length > 0
  } catch {
    supportsModelFetch.value = false
  } finally {
    testingModel.value = false
  }
}

async function refreshModelsUnified() {
  loadingModels.value = true
  const p = createProvider()
  const list = await p.listModels()
  if (ai.value.provider === 'DEEPSEEK') {
    deepseekModels.value = list
    if (deepseekModels.value.length > 0 && !deepseekModels.value.some(m => m.value === ai.value.deepseek.model)) {
      ai.value.deepseek.model = deepseekModels.value[0].value
    }
  } else if (ai.value.provider === 'OLLAMA') {
    ollamaModels.value = list
    if (ollamaModels.value.length > 0 && !ollamaModels.value.some(m => m.value === ai.value.ollama.model)) {
      ai.value.ollama.model = ollamaModels.value[0].value
    }
  }
  loadingModels.value = false
}

async function refreshGenericModels() {
  loadingModels.value = true
  try {
    const p = createProvider()
    const list = await p.listModels()
    genericModels.value = list
  } finally {
    loadingModels.value = false
  }
}

// 角色与默认问题迁移到 Prompt 标签页

function updateSettings(options: Partial<SettingsState>) {
  settingStore.updateSetting(options)
  
  const payload: any = {}
  
  if (options.systemMessage) {
      // Map systemMessage to ai.system_prompt for unified config
      payload.ai = { ...(payload.ai || {}), system_prompt: options.systemMessage }
  }

  if (options.temperature !== undefined) {
      payload.ai = { ...(payload.ai || {}), temperature: options.temperature }
  }

  if (options.top_p !== undefined) {
      payload.ai = { ...(payload.ai || {}), top_p: options.top_p }
  }
  
  if (Object.keys(payload).length > 0) {
      apiUpdateSettings(payload)
  }
  
  ms.success(t('common.success'))
}

function updateAiSettings() {
    settingStore.updateSetting({ ai: ai.value })
    apiUpdateSettings({ ai: ai.value })
    ms.success(t('common.success'))
}

const isCustomDeepSeek = computed(() => !!ai.value.deepseek.model && !deepseekModels.value.some(m => m.value === ai.value.deepseek.model))
const isCustomOllama = computed(() => !!ai.value.ollama.model && !ollamaModels.value.some(m => m.value === ai.value.ollama.model))
const isCustomGeneric = computed(() => {
  const key = ai.value.provider
  const dm = ai.value.provider_configs?.[key]?.default_model || ''
  return !!dm && !genericModels.value.some(m => m.value === dm)
})

watch(() => ai.value.deepseek.model, (val) => {
  if (isCustomDeepSeek.value) deepseekCustomName.value = val
})
watch(() => ai.value.ollama.model, (val) => {
  if (isCustomOllama.value) ollamaCustomName.value = val
})
watch(() => ai.value.provider_configs?.[ai.value.provider]?.default_model, (val) => {
  if (isCustomGeneric.value) {
    genericCustomName.value = val || ''
  }
})

function saveCustomModelPreset(providerKey: string, name: string) {
  if (!name || !providerKey) return
  const base = (ai.value.provider_configs || {})[providerKey] || { base_url: '', api_key: '', default_model: '', models: [] }
  const models = Array.isArray(base.models) ? base.models.slice() : []
  if (!models.includes(name)) models.push(name)
  ai.value.provider_configs = {
    ...(ai.value.provider_configs || {}),
    [providerKey]: { ...base, models }
  }
  updateAiSettings()
  ms.success('已保存为自定义模型预设')
}

function removeCustomModelPreset(providerKey: string, name: string) {
  const base = (ai.value.provider_configs || {})[providerKey] || { base_url: '', api_key: '', default_model: '', models: [] }
  const models = Array.isArray(base.models) ? base.models.slice() : []
  const idx = models.indexOf(name)
  if (idx >= 0) {
    models.splice(idx, 1)
  }
  const nextDefault = idx >= 0 ? ((genericModels.value.find(m => m.value !== name)?.value) || '') : ''
  ai.value.provider_configs = {
    ...(ai.value.provider_configs || {}),
    [providerKey]: { ...base, default_model: nextDefault, models }
  }
  if (idx >= 0) {
    genericModels.value = genericModels.value.filter(m => m.value !== name)
  } else {
    // 清空当前名称
    genericCustomName.value = ''
  }
  updateAiSettings()
  ms.success('已删除自定义模型预设')
}

function openAddCustomModelModal(providerKey: string) {
  customModelProvider.value = providerKey
  customModelId.value = ''
  showAddCustomModelModal.value = true
}

function confirmAddCustomModel() {
  const id = (customModelId.value || '').trim()
  const providerKey = customModelProvider.value || ai.value.provider
  if (!id) {
    ms.error('请输入模型ID')
    return
  }
  const base = (ai.value.provider_configs || {})[providerKey] || { base_url: '', api_key: '', default_model: '', models: [] }
  const models = Array.isArray(base.models) ? base.models.slice() : []
  if (!models.includes(id)) models.push(id)
  ai.value.provider_configs = {
    ...(ai.value.provider_configs || {}),
    [providerKey]: { ...base, models }
  }
  if (providerKey === 'DEEPSEEK') {
    deepseekModels.value = [...deepseekModels.value, { label: id, value: id }]
    ai.value.deepseek.model = id
  } else if (providerKey === 'OLLAMA') {
    ollamaModels.value = [...ollamaModels.value, { label: id, value: id }]
    ai.value.ollama.model = id
  } else {
    genericModels.value = [...genericModels.value, { label: id, value: id }]
    updateCurrentProviderConfig({ default_model: id })
  }
  updateAiSettings()
  showAddCustomModelModal.value = false
  ms.success('已添加自定义模型')
}

// 默认问题的保存已迁移到 Prompt 标签页

// 输出详细程度相关
const outputDetailLevelValue = computed({
  get() {
    const levelMap: Record<string, number> = { 'simple': 0, 'medium': 1, 'detailed': 2 }
    return levelMap[settingStore.outputDetailLevel] ?? 1
  },
  set(value: number) {
    const levelMap: Record<number, 'simple' | 'medium' | 'detailed'> = { 0: 'simple', 1: 'medium', 2: 'detailed' }
    settingStore.updateSetting({ outputDetailLevel: levelMap[value] ?? 'medium' })
  }
})

const outputDetailLevelText = computed(() => {
  const levelMap: Record<string, string> = { 'simple': '简约', 'medium': '适中', 'detailed': '详细' }
  return levelMap[settingStore.outputDetailLevel] ?? '适中'
})

const outputDetailPresets = ref({ ...settingStore.outputDetailPresets })

function formatOutputDetailTooltip(value: number) {
  const levelMap: Record<number, string> = { 0: '简约', 1: '适中', 2: '详细' }
  return levelMap[value] ?? '适中'
}

function updateOutputDetailLevel() {
  // 保存到后端
  apiUpdateSettings({ output_detail_level: settingStore.outputDetailLevel })
  ms.success(t('common.success'))
}

// 模态框相关
const showPresetModal = ref(false)
const currentPresetType = ref<'simple' | 'medium' | 'detailed'>('simple')
const currentPresetValue = ref('')

function openPresetModal(type: 'simple' | 'medium' | 'detailed') {
  currentPresetType.value = type
  currentPresetValue.value = outputDetailPresets.value[type]
  showPresetModal.value = true
}

function openPresetModalForCurrentLevel() {
  // 根据当前的滑块值确定要编辑的类型
  const levelMap: Record<number, 'simple' | 'medium' | 'detailed'> = { 0: 'simple', 1: 'medium', 2: 'detailed' }
  const currentLevel = outputDetailLevelValue.value
  const currentType = levelMap[currentLevel] ?? 'medium'
  openPresetModal(currentType)
}

function savePresetValue() {
  outputDetailPresets.value[currentPresetType.value] = currentPresetValue.value
  updateOutputDetailPresets()
  showPresetModal.value = false
}

function updateOutputDetailPresets() {
  settingStore.updateSetting({ outputDetailPresets: { ...outputDetailPresets.value } })
  // 保存到后端
  apiUpdateSettings({ output_detail_presets: outputDetailPresets.value })
  ms.success(t('common.success'))
}

function handleReset() {
  settingStore.resetSetting()
  ms.success(t('common.success'))
  window.location.reload()
}
</script>

<template>
  <div class="p-4 space-y-5 min-h-[200px]">
    <div class="space-y-6">
      
      <div class="flex items-center space-x-4">
        <span class="flex-shrink-0 w-[120px]">{{ $t('setting.provider') }}</span>
        <div class="flex-1">
          <NSelect v-model:value="ai.provider" :options="providerOptions" @update:value="() => updateAiSettings()" />
        </div>
      </div>
      <div v-if="ai.provider !== 'DEEPSEEK' && ai.provider !== 'OLLAMA'" class="flex items-center space-x-4">
        <span class="flex-shrink-0 w-[120px]">模型名称</span>
        <div class="flex-1">
          <NInput
            :value="genericCustomName"
            placeholder="输入自定义模型名称"
            @update:value="val => { genericCustomName = val; updateCurrentProviderConfig({ default_model: val }) }"
          />
        </div>
        <NButton size="tiny" text type="error" :disabled="!genericCustomName" @click="showDeleteModelModal = true">删除</NButton>
      </div>

      <div class="flex items-center space-x-4">
        <span class="flex-shrink-0 w-[120px]">{{ $t('setting.thinking') }}</span>
        <div class="flex-1">
          <NSwitch v-model:value="ai.thinking.enabled" :disabled="thinkingDisabled" />
        </div>
        <span class="flex-shrink-0 w-[120px]">{{ $t('setting.web_search') }}</span>
        <div class="flex-1">
          <NSwitch v-model:value="ai.web_search.enabled" :disabled="webSearchDisabled" />
        </div>
        
      </div>
      <div class="flex items-center space-x-4">
        <span class="flex-shrink-0 w-[120px]">记忆摘要</span>
        <div class="flex-1">
          <NSwitch v-model:value="ai.memory.enabled" />
        </div>
        <span class="flex-shrink-0 w-[120px]">目标上下文</span>
        <div class="flex-1">
          <NSlider v-model:value="ai.memory.target_k" :max="128" :min="1" :step="1" />
        </div>
        <span>{{ ai.memory.target_k }}k</span>
        
      </div>
      <div class="flex items-center space-x-4">
        <span class="flex-shrink-0 w-[120px]">状态</span>
        <div class="flex-1">
          <div class="flex gap-2 flex-wrap">
            <NTag :type="testingConn ? 'warning' : (connectivity ? 'success' : 'error')" round>
              连通性：{{ testingConn ? '检测中...' : (connectivity ? '可用' : '不可用') }}
            </NTag>
            <NTag :type="testingThink ? 'warning' : (supportsThinking ? 'success' : 'error')" round>
              思考：{{ testingThink ? '检测中...' : (supportsThinking ? '支持' : '不支持') }}
            </NTag>
            <NTag :type="testingWeb ? 'warning' : (networkingCapable ? 'success' : 'error')" round>
              联网：{{ testingWeb ? '检测中...' : (networkingCapable ? '可用' : '不可用') }}
            </NTag>
            <NTag :type="testingModel ? 'warning' : (supportsModelFetch ? 'success' : 'error')" round>
              模型获取：{{ testingModel ? '检测中...' : (supportsModelFetch ? '可用' : '不可用') }}
            </NTag>
          </div>
        </div>
        <NButton size="tiny" text type="primary" :loading="testingConn || testingThink || testingWeb || testingModel" @click="updateProviderCapabilities">
          {{ $t('common.refresh') }}
        </NButton>
      </div>
      
      
      


      <template v-if="ai.provider === 'DEEPSEEK'">
         <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">{{ $t('setting.api_key') }}</span>
          <div class="flex-1">
            <NInput v-model:value="ai.deepseek.api_key" :placeholder="$t('setting.api_key')" type="password" show-password-on="click" autocomplete="off" />
          </div>
        </div>
         <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">{{ $t('setting.url') }}</span>
          <div class="flex-1">
            <NInput v-model:value="ai.deepseek.url" placeholder="https://api.deepseek.com" />
          </div>
          <NButton size="tiny" text type="primary" @click="resetDeepSeekUrl">
            {{ $t('common.reset') }}
          </NButton>
        </div>
         <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">{{ $t('setting.model') }}</span>
          <div class="flex-1">
            <NSelect
                v-model:value="ai.deepseek.model"
                :options="deepseekModels"
                filterable
                tag
                :placeholder="$t('setting.model')"
            />
          </div>
          <NButton size="tiny" text type="primary" :loading="loadingModels" @click="refreshModelsUnified">
            {{ $t('common.refresh') }}
          </NButton>
          <NButton size="tiny" text type="primary" @click="openAddCustomModelModal('DEEPSEEK')">
            新增自定义
          </NButton>
        </div>
        <div v-if="isCustomDeepSeek" class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">自定义名称</span>
          <div class="flex-1">
            <NInput v-model:value="deepseekCustomName" placeholder="输入自定义模型名称" />
          </div>
          <NButton size="tiny" text type="primary" @click="() => saveCustomModelPreset('DEEPSEEK', deepseekCustomName)">
            保存为预设
          </NButton>
        </div>
      </template>
      
      <template v-if="ai.provider !== 'DEEPSEEK' && ai.provider !== 'OLLAMA'">
        <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">{{ $t('setting.api_key') }}</span>
          <div class="flex-1">
            <NInput
              :value="ai.provider_configs?.[ai.provider]?.api_key || ''"
              :placeholder="$t('setting.api_key')"
              type="password"
              show-password-on="click"
              @update:value="val => updateCurrentProviderConfig({ api_key: val })"
            />
          </div>
        </div>
        <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">{{ $t('setting.url') }}</span>
        <div class="flex-1">
          <NInput
            :value="ai.provider_configs?.[ai.provider]?.base_url || ''"
            placeholder="https://api.example.com/v1"
            @update:value="val => updateCurrentProviderConfig({ base_url: val })"
          />
        </div>
        <NButton size="tiny" text type="primary" @click="resetGenericUrl">
          {{ $t('common.reset') }}
        </NButton>
      </div>
        <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">{{ $t('setting.model') }}</span>
          <div class="flex-1">
            <NSelect
              :value="ai.provider_configs?.[ai.provider]?.default_model || ''"
              :options="genericModels"
              filterable
              tag
              :placeholder="$t('setting.model')"
              @update:value="val => updateCurrentProviderConfig({ default_model: val as string })"
            />
          </div>
          <NButton size="tiny" text type="primary" :loading="loadingModels" @click="refreshGenericModels">
            {{ $t('common.refresh') }}
          </NButton>
          <NButton size="tiny" text type="primary" @click="openAddCustomModelModal(ai.provider)">
            新增自定义
          </NButton>
        </div>
        <div v-if="ai.provider !== 'DEEPSEEK' && ai.provider !== 'OLLAMA'" class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">模型名称</span>
          <div class="flex-1">
            <NInput
              :value="genericCustomName"
              placeholder="输入自定义模型名称"
              @update:value="val => { genericCustomName = val; updateCurrentProviderConfig({ default_model: val }) }"
            />
          </div>
          <NButton size="tiny" text type="primary" @click="() => saveCustomModelPreset(ai.provider, genericCustomName)">
            保存为预设
          </NButton>
        </div>
      </template>

      <template v-if="ai.provider === 'OLLAMA'">
         <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">{{ $t('setting.url') }}</span>
          <div class="flex-1">
            <NInput v-model:value="ai.ollama.url" placeholder="http://localhost:11434" />
          </div>
          <NButton size="tiny" text type="primary" @click="() => { ai.ollama.url = 'http://localhost:11434'; updateAiSettings() }">
            {{ $t('common.reset') }}
          </NButton>
        </div>
         <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">{{ $t('setting.model') }}</span>
          <div class="flex-1">
             <NSelect
                v-model:value="ai.ollama.model"
                :options="ollamaModels"
                filterable
                tag
                :placeholder="$t('setting.model')"
            />
          </div>
          <NButton size="tiny" text type="primary" :loading="loadingModels" @click="refreshModelsUnified">
            {{ $t('common.refresh') }}
          </NButton>
          <NButton size="tiny" text type="primary" @click="openAddCustomModelModal('OLLAMA')">
            新增自定义
          </NButton>
        </div>
        <div v-if="isCustomOllama" class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">自定义名称</span>
          <div class="flex-1">
            <NInput v-model:value="ollamaCustomName" placeholder="输入自定义模型名称" />
          </div>
          <NButton size="tiny" text type="primary" @click="() => saveCustomModelPreset('OLLAMA', ollamaCustomName)">
            保存为预设
          </NButton>
        </div>
      </template>
      <NModal v-model:show="showDeleteModelModal" preset="dialog" title="确认删除">
        <template #default>
          确定删除当前自定义模型预设“{{ genericCustomName }}”吗？
        </template>
        <template #action>
          <div class="flex gap-2">
            <NButton size="small" @click="showDeleteModelModal = false">取消</NButton>
            <NButton size="small" type="error" @click="() => { removeCustomModelPreset(ai.provider, genericCustomName); showDeleteModelModal = false }">删除</NButton>
          </div>
        </template>
      </NModal>
      <NModal v-model:show="showAddCustomModelModal" preset="card" title="新增自定义模型">
        <div class="space-y-3">
          <div class="flex items-center space-x-4">
            <span class="flex-shrink-0 w-[120px]">模型ID</span>
            <div class="flex-1">
              <NInput v-model:value="customModelId" placeholder="例如：my-model-1" />
            </div>
          </div>
          <div class="flex justify-end space-x-2 pt-2">
            <NButton size="small" @click="showAddCustomModelModal=false">取消</NButton>
            <NButton size="small" type="primary" @click="confirmAddCustomModel">保存</NButton>
          </div>
        </div>
      </NModal>

      <!-- 角色与默认问题已迁移到 Prompt 标签页 -->

      <div class="flex items-center space-x-4">
        <span class="flex-shrink-0 w-[120px]">{{ $t('setting.temperature') }} </span>
        <div class="flex-1">
          <NSlider v-model:value="temperature" :max="2" :min="0" :step="0.1" />
        </div>
        <span>{{ temperature }}</span>
        <NButton size="tiny" text type="primary" @click="updateSettings({ temperature })">
          {{ $t('common.save') }}
        </NButton>
      </div>
      <div class="flex items-center space-x-4">
        <span class="flex-shrink-0 w-[120px]">{{ $t('setting.top_p') }} </span>
        <div class="flex-1">
          <NSlider v-model:value="top_p" :max="1" :min="0" :step="0.1" />
        </div>
        <span>{{ top_p }}</span>
        <NButton size="tiny" text type="primary" @click="updateSettings({ top_p })">
          {{ $t('common.save') }}
        </NButton>
      </div>
      <!-- 输出详细程度设置 -->
      <div class="flex items-center space-x-4">
        <span class="flex-shrink-0 w-[120px]">{{ $t('setting.outputDetailLevel') }}</span>
        <div class="flex-1">
          <NSlider
            v-model:value="outputDetailLevelValue"
            :step="1"
            :min="0"
            :max="2"
            :format-tooltip="formatOutputDetailTooltip"
            @dblclick="openPresetModalForCurrentLevel"
          />
        </div>
        <span>{{ outputDetailLevelText }}</span>
        <NButton size="tiny" text type="primary" @click="updateOutputDetailLevel">
          {{ $t('common.save') }}
        </NButton>
      </div>

      <div class="flex items-center space-x-4">
        <span class="flex-shrink-0 w-[120px]">&nbsp;</span>
        <NButton size="small" @click="handleReset">
          {{ $t('common.reset') }}
        </NButton>
      </div>
    </div>
  </div>

  <!-- Prompt 标签页承载角色与默认问题的模态框 -->

  <!-- 输出详细程度预设编辑模态框 -->
  <NModal v-model:show="showPresetModal" preset="card" :title="`${$t('setting.edit')} ${currentPresetType === 'simple' ? $t('setting.simple') : currentPresetType === 'medium' ? $t('setting.medium') : $t('setting.detailed')} ${$t('setting.outputDetailPrompt')}`" style="width: 90%; max-width: 600px;">
    <div class="space-y-4">
      <NInput
        v-model:value="currentPresetValue"
        type="textarea"
        :autosize="{ minRows: 3, maxRows: 6 }"
        :placeholder="$t('setting.promptPlaceholder')"
      />
      <div class="flex justify-center">
        <NButton type="primary" @click="savePresetValue">
          {{ $t('common.save') }}
        </NButton>
      </div>
    </div>
  </NModal>
</template>
