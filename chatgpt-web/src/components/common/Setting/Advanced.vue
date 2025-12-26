<script lang="ts" setup>
import { ref, computed, watch, onMounted } from 'vue'
import { NButton, NInput, NSlider, NSelect, NSwitch, useMessage } from 'naive-ui'
import { useSettingStore, useAppStore } from '@/store'
import type { SettingsState } from '@/store/modules/settings/helper'
import { t } from '@/locales'
import { updateSettings as apiUpdateSettings } from '@/api'

const settingStore = useSettingStore()
const appStore = useAppStore()

const ms = useMessage()

const systemMessage = ref(settingStore.systemMessage ?? '')

const defaultQuestion = ref(appStore.defaultQuestions?.[0] ?? '')

const temperature = ref(settingStore.temperature ?? 0.5)

const top_p = ref(settingStore.top_p ?? 1)

const ai = ref(settingStore.ai)

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

// 获取DeepSeek模型列表
const deepseekModels = ref<ModelOption[]>([])

// 获取Ollama模型列表
const ollamaModels = ref<ModelOption[]>([])

async function fetchDeepSeekModels() {
  console.log('开始获取DeepSeek模型列表...')
  if (!ai.value.deepseek.api_key) {
    ms.error('请先输入API密钥')
    return
  }

  try {
    const response = await fetch(`${ai.value.deepseek.url}/models`, {
      headers: {
        'Authorization': `Bearer ${ai.value.deepseek.api_key}`,
        'Content-Type': 'application/json'
      }
    })

    console.log('API响应状态:', response.status)

    if (!response.ok) {
      throw new Error(`获取模型列表失败: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    console.log('API返回数据:', data)

    if (data && data.data && Array.isArray(data.data)) {
      // 将API返回的模型数据转换为下拉框选项格式
      deepseekModels.value = data.data.map((model: any) => ({
        label: model.id || model.name || 'Unknown Model',
        value: model.id || model.name || 'unknown'
      }))

      console.log('转换后的模型列表:', deepseekModels.value)

      // 如果当前模型不在列表中，使用第一个模型
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
  }
}

// 获取Ollama模型列表
async function fetchOllamaModels() {
  console.log('开始获取Ollama模型列表...')
  try {
    const response = await fetch(`${ai.value.ollama.url}/api/tags`, {
      headers: {
        'Content-Type': 'application/json'
      }
    })

    console.log('Ollama API响应状态:', response.status)

    if (!response.ok) {
      throw new Error(`获取模型列表失败: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    console.log('Ollama API返回数据:', data)

    if (data && data.models && Array.isArray(data.models)) {
      // 将API返回的模型数据转换为下拉框选项格式
      ollamaModels.value = data.models.map((model: any) => ({
        label: model.name || model.id || 'Unknown Model',
        value: model.name || model.id || 'unknown'
      }))

      console.log('Ollama转换后的模型列表:', ollamaModels.value)

      // 如果当前模型不在列表中，使用第一个模型
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
  }
}

const providerOptions = [
  { label: 'DeepSeek', value: 'DEEPSEEK' },
  { label: 'Ollama', value: 'OLLAMA' },
]

// 组件挂载后获取模型列表
onMounted(() => {
  if (ai.value.provider === 'DEEPSEEK') {
    fetchDeepSeekModels()
  } else if (ai.value.provider === 'OLLAMA') {
    fetchOllamaModels()
  }
})

// 监听提供商变化，自动获取对应模型列表
watch(() => ai.value.provider, (newProvider: string) => {
  if (newProvider === 'DEEPSEEK') {
    fetchDeepSeekModels()
  } else if (newProvider === 'OLLAMA') {
    fetchOllamaModels()
  }
})

const systemMessageOptions = computed(() => {
    return (settingStore.systemMessagePresets || []).map(p => ({ label: p.label, value: p.value }))
})

const defaultQuestionOptions = computed(() => {
    return (settingStore.defaultQuestionPresets || []).map(p => ({ label: p.label, value: p.value }))
})

function handleSystemPresetChange(val: string) {
    systemMessage.value = val
}

function handleQuestionPresetChange(val: string) {
    defaultQuestion.value = val
}

function saveSystemAsPreset() {
    if (!systemMessage.value) return
    const label = prompt('Enter a name for this preset:')
    if (label) {
        settingStore.addSystemMessagePreset({ label, value: systemMessage.value })
        apiUpdateSettings({ system_message_presets: settingStore.systemMessagePresets })
        ms.success('Preset saved')
    }
}

function saveQuestionAsPreset() {
    if (!defaultQuestion.value) return
    const label = prompt('Enter a name for this preset:')
    if (label) {
        settingStore.addDefaultQuestionPreset({ label, value: defaultQuestion.value })
        apiUpdateSettings({ default_question_presets: settingStore.defaultQuestionPresets })
        ms.success('Preset saved')
    }
}

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

function updateDefaultQuestion() {
    appStore.setDefaultQuestions([defaultQuestion.value])
    apiUpdateSettings({ default_questions: [defaultQuestion.value] })
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
          <NSelect v-model:value="ai.provider" :options="providerOptions" />
        </div>
        <NButton size="tiny" text type="primary" @click="updateAiSettings">
          {{ $t('common.save') }}
        </NButton>
      </div>

      <div class="flex items-center space-x-4">
        <span class="flex-shrink-0 w-[120px]">{{ $t('setting.thinking') }}</span>
        <div class="flex-1">
          <NSwitch v-model:value="ai.thinking.enabled" />
        </div>
        <span class="flex-shrink-0 w-[120px]">{{ $t('setting.web_search') }}</span>
        <div class="flex-1">
          <NSwitch v-model:value="ai.web_search.enabled" />
        </div>
        <NButton size="tiny" text type="primary" @click="updateAiSettings">
          {{ $t('common.save') }}
        </NButton>
      </div>
      


      <template v-if="ai.provider === 'DEEPSEEK'">
         <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">{{ $t('setting.api_key') }}</span>
          <div class="flex-1">
            <NInput v-model:value="ai.deepseek.api_key" :placeholder="$t('setting.api_key')" type="password" show-password-on="click" />
          </div>
          <NButton size="tiny" text type="primary" @click="updateAiSettings">
            {{ $t('common.save') }}
          </NButton>
        </div>
         <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">{{ $t('setting.url') }}</span>
          <div class="flex-1">
            <NInput v-model:value="ai.deepseek.url" placeholder="https://api.deepseek.com" />
          </div>
          <NButton size="tiny" text type="primary" @click="resetDeepSeekUrl">
            {{ $t('common.reset') }}
          </NButton>
          <NButton size="tiny" text type="primary" @click="updateAiSettings">
            {{ $t('common.save') }}
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
          <NButton size="tiny" text type="primary" @click="fetchDeepSeekModels">
            {{ $t('common.refresh') }}
          </NButton>
          <NButton size="tiny" text type="primary" @click="updateAiSettings">
            {{ $t('common.save') }}
          </NButton>
        </div>
      </template>

      <template v-if="ai.provider === 'OLLAMA'">
         <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">{{ $t('setting.url') }}</span>
          <div class="flex-1">
            <NInput v-model:value="ai.ollama.url" placeholder="http://localhost:11434" />
          </div>
          <NButton size="tiny" text type="primary" @click="updateAiSettings">
            {{ $t('common.save') }}
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
          <NButton size="tiny" text type="primary" @click="fetchOllamaModels">
            {{ $t('common.refresh') }}
          </NButton>
          <NButton size="tiny" text type="primary" @click="updateAiSettings">
            {{ $t('common.save') }}
          </NButton>
        </div>
      </template>

      <div class="flex items-start space-x-4">
        <span class="flex-shrink-0 w-[120px] pt-2">{{ $t('setting.role') }}</span>
        <div class="flex-1 space-y-2">
           <div class="flex gap-2">
               <NSelect 
                   :options="systemMessageOptions" 
                   placeholder="Select a preset" 
                   @update:value="handleSystemPresetChange"
                   class="flex-1"
               />
               <NButton @click="saveSystemAsPreset" ghost>Save Preset</NButton>
           </div>
          <NInput v-model:value="systemMessage" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" placeholder="System Prompt content..." />
        </div>
        <NButton size="tiny" text type="primary" @click="updateSettings({ systemMessage })" class="pt-2">
          {{ $t('common.save') }}
        </NButton>
      </div>

      <div class="flex items-start space-x-4">
        <span class="flex-shrink-0 w-[120px] pt-2">{{ $t('setting.defaultQuestion') }}</span>
        <div class="flex-1 space-y-2">
            <div class="flex gap-2">
               <NSelect 
                   :options="defaultQuestionOptions" 
                   placeholder="Select a preset" 
                   @update:value="handleQuestionPresetChange"
                   class="flex-1"
               />
               <NButton @click="saveQuestionAsPreset" ghost>Save Preset</NButton>
           </div>
          <NInput v-model:value="defaultQuestion" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" placeholder="Default question content..." />
        </div>
        <NButton size="tiny" text type="primary" @click="updateDefaultQuestion" class="pt-2">
          {{ $t('common.save') }}
        </NButton>
      </div>

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
      <div class="flex items-center space-x-4">
        <span class="flex-shrink-0 w-[120px]">&nbsp;</span>
        <NButton size="small" @click="handleReset">
          {{ $t('common.reset') }}
        </NButton>
      </div>
    </div>
  </div>
</template>
