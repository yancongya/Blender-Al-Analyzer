<script lang="ts" setup>
import { ref, computed, watch, onMounted } from 'vue'
import { NButton, NInput, NSlider, NSelect, NSwitch, useMessage, NModal } from 'naive-ui'
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

// 系统消息预设相关
const selectedSystemPreset = ref('')
const showAddSystemPresetModal = ref(false)
const newSystemPresetName = ref('')


// 默认问题预设相关
const selectedQuestionPreset = ref('')
const showAddQuestionPresetModal = ref(false)
const newQuestionPresetName = ref('')

const defaultQuestionOptions = computed(() => {
    const presets = (settingStore.defaultQuestionPresets || [])
    const options = presets.map(p => ({ label: p.label, value: p.value }))

    // 如果有预设且没有选择任何预设，则默认选择第一个
    if (presets.length > 0 && !selectedQuestionPreset.value) {
        selectedQuestionPreset.value = presets[0].value
        defaultQuestion.value = presets[0].value
    }

    return options
})


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

    if (!response.ok) {
      throw new Error(`获取模型列表失败: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()

    if (data && data.data && Array.isArray(data.data)) {
      // 将API返回的模型数据转换为下拉框选项格式
      deepseekModels.value = data.data.map((model: any) => ({
        label: model.id || model.name || 'Unknown Model',
        value: model.id || model.name || 'unknown'
      }))

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
      // 将API返回的模型数据转换为下拉框选项格式
      ollamaModels.value = data.models.map((model: any) => ({
        label: model.name || model.id || 'Unknown Model',
        value: model.name || model.id || 'unknown'
      }))

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
    const presets = (settingStore.systemMessagePresets || [])
    const options = presets.map(p => ({ label: p.label, value: p.value }))

    // 如果有预设且没有选择任何预设，则默认选择第一个
    if (presets.length > 0 && !selectedSystemPreset.value) {
        selectedSystemPreset.value = presets[0].value
        systemMessage.value = presets[0].value
    }

    return options
})


function handleSystemPresetChange(val: string) {
    systemMessage.value = val
    selectedSystemPreset.value = val
}


function handleQuestionPresetChange(val: string) {
    defaultQuestion.value = val
    selectedQuestionPreset.value = val
}

function addQuestionPreset() {
    if (!newQuestionPresetName.value.trim()) {
        ms.error(t('setting.presetNameRequired'))
        return
    }

    // 检查是否已存在同名预设
    const existingPreset = settingStore.defaultQuestionPresets?.find(p => p.label === newQuestionPresetName.value)
    if (existingPreset) {
        ms.error(t('setting.presetAlreadyExists'))
        return
    }

    // 添加到预设列表
    const newPreset = { label: newQuestionPresetName.value, value: defaultQuestion.value }
    settingStore.addDefaultQuestionPreset(newPreset)
    apiUpdateSettings({ default_question_presets: settingStore.defaultQuestionPresets })
    ms.success(t('setting.presetAddedSuccessfully'))

    // 重置并关闭模态框
    newQuestionPresetName.value = ''
    showAddQuestionPresetModal.value = false
}

function cancelAddQuestionPreset() {
    newQuestionPresetName.value = ''
    showAddQuestionPresetModal.value = false
}

function addSystemPreset() {
    if (!newSystemPresetName.value.trim()) {
        ms.error(t('setting.presetNameRequired'))
        return
    }

    // 检查是否已存在同名预设
    const existingPreset = settingStore.systemMessagePresets?.find(p => p.label === newSystemPresetName.value)
    if (existingPreset) {
        ms.error(t('setting.presetAlreadyExists'))
        return
    }

    settingStore.addSystemMessagePreset({ label: newSystemPresetName.value, value: systemMessage.value })
    apiUpdateSettings({ system_message_presets: settingStore.systemMessagePresets })
    ms.success(t('setting.presetAddedSuccessfully'))

    // 重置并关闭模态框
    newSystemPresetName.value = ''
    showAddSystemPresetModal.value = false
}


function cancelAddSystemPreset() {
    newSystemPresetName.value = ''
    showAddSystemPresetModal.value = false
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
                   :placeholder="$t('setting.selectAPreset')"
                   @update:value="handleSystemPresetChange"
                   v-model:value="selectedSystemPreset"
                   class="flex-1"
               />
               <NButton @click="showAddSystemPresetModal = true" ghost>{{ $t('setting.addPreset') }}</NButton>
           </div>
          <NInput v-model:value="systemMessage" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" :placeholder="$t('setting.systemPromptPlaceholder')" />
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
                   :placeholder="$t('setting.selectAPreset')"
                   @update:value="handleQuestionPresetChange"
                   v-model:value="selectedQuestionPreset"
                   class="flex-1"
               />
               <NButton @click="showAddQuestionPresetModal = true" ghost>{{ $t('setting.addPreset') }}</NButton>
           </div>
          <NInput v-model:value="defaultQuestion" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" :placeholder="$t('setting.defaultQuestionPlaceholder')" />
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

  <!-- 添加系统消息预设模态框 -->
  <NModal v-model:show="showAddSystemPresetModal" preset="card" :title="$t('setting.addSystemPreset')" style="width: 600px;">
    <div class="space-y-4">
      <div>
        <label class="block mb-2">{{ $t('setting.presetName') }}</label>
        <NInput v-model:value="newSystemPresetName" :placeholder="$t('setting.enterPresetName')" />
      </div>
      <div>
        <label class="block mb-2">{{ $t('setting.content') }}</label>
        <NInput v-model:value="systemMessage" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" :placeholder="$t('setting.systemPromptPlaceholder')" />
      </div>
      <div class="flex justify-center space-x-3">
        <NButton @click="cancelAddSystemPreset">
          {{ $t('common.cancel') }}
        </NButton>
        <NButton type="primary" @click="addSystemPreset">
          {{ $t('common.confirm') }}
        </NButton>
      </div>
    </div>
  </NModal>

  <!-- 添加默认问题预设模态框 -->
  <NModal v-model:show="showAddQuestionPresetModal" preset="card" :title="$t('setting.addQuestionPreset')" style="width: 600px;">
    <div class="space-y-4">
      <div>
        <label class="block mb-2">{{ $t('setting.presetName') }}</label>
        <NInput v-model:value="newQuestionPresetName" :placeholder="$t('setting.enterPresetName')" />
      </div>
      <div>
        <label class="block mb-2">{{ $t('setting.content') }}</label>
        <NInput v-model:value="defaultQuestion" type="textarea" :autosize="{ minRows: 3, maxRows: 6 }" :placeholder="$t('setting.defaultQuestionPlaceholder')" />
      </div>
      <div class="flex justify-center space-x-3">
        <NButton @click="cancelAddQuestionPreset">
          {{ $t('common.cancel') }}
        </NButton>
        <NButton type="primary" @click="addQuestionPreset">
          {{ $t('common.confirm') }}
        </NButton>
      </div>
    </div>
  </NModal>

</template>
