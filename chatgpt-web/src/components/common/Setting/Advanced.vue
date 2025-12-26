<script lang="ts" setup>
import { ref, computed } from 'vue'
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

const providerOptions = [
  { label: 'DeepSeek', value: 'DEEPSEEK' },
  { label: 'Ollama', value: 'OLLAMA' },
]

const deepseekModels = [
  { label: 'deepseek-chat', value: 'deepseek-chat' },
  { label: 'deepseek-coder', value: 'deepseek-coder' },
]

const ollamaModels = [
  { label: 'llama2', value: 'llama2' },
  { label: 'mistral', value: 'mistral' },
  { label: 'codellama', value: 'codellama' },
  { label: 'gemma', value: 'gemma' },
]

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
        <span class="flex-shrink-0 w-[120px]">Provider</span>
        <div class="flex-1">
          <NSelect v-model:value="ai.provider" :options="providerOptions" />
        </div>
        <NButton size="tiny" text type="primary" @click="updateAiSettings">
          {{ $t('common.save') }}
        </NButton>
      </div>

      <div class="flex items-center space-x-4">
        <span class="flex-shrink-0 w-[120px]">Thinking</span>
        <div class="flex-1">
          <NSwitch v-model:value="ai.thinking.enabled" />
        </div>
        <NButton size="tiny" text type="primary" @click="updateAiSettings">
          {{ $t('common.save') }}
        </NButton>
      </div>

      <div class="flex items-center space-x-4">
        <span class="flex-shrink-0 w-[120px]">Web Search</span>
        <div class="flex-1">
          <NSwitch v-model:value="ai.web_search.enabled" />
        </div>
        <NButton size="tiny" text type="primary" @click="updateAiSettings">
          {{ $t('common.save') }}
        </NButton>
      </div>
      


      <template v-if="ai.provider === 'DEEPSEEK'">
         <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">API Key</span>
          <div class="flex-1">
            <NInput v-model:value="ai.deepseek.api_key" placeholder="DeepSeek API Key" type="password" show-password-on="click" />
          </div>
          <NButton size="tiny" text type="primary" @click="updateAiSettings">
            {{ $t('common.save') }}
          </NButton>
        </div>
         <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">Model</span>
          <div class="flex-1">
            <NSelect 
                v-model:value="ai.deepseek.model" 
                :options="deepseekModels" 
                filterable 
                tag 
                placeholder="Select or type model name" 
            />
          </div>
          <NButton size="tiny" text type="primary" @click="updateAiSettings">
            {{ $t('common.save') }}
          </NButton>
        </div>
      </template>

      <template v-if="ai.provider === 'OLLAMA'">
         <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">URL</span>
          <div class="flex-1">
            <NInput v-model:value="ai.ollama.url" placeholder="http://localhost:11434" />
          </div>
          <NButton size="tiny" text type="primary" @click="updateAiSettings">
            {{ $t('common.save') }}
          </NButton>
        </div>
         <div class="flex items-center space-x-4">
          <span class="flex-shrink-0 w-[120px]">Model</span>
          <div class="flex-1">
             <NSelect 
                v-model:value="ai.ollama.model" 
                :options="ollamaModels" 
                filterable 
                tag 
                placeholder="Select or type model name" 
            />
          </div>
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
