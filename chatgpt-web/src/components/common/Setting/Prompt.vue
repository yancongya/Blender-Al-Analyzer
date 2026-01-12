<script setup lang="ts">
import { ref, computed } from 'vue'
import { NButton, NInput, NSelect, NModal, useMessage } from 'naive-ui'
import { useSettingStore, useAppStore } from '@/store'
import { updateSettings as apiUpdateSettings } from '@/api'
import { t } from '@/locales'

const settingStore = useSettingStore()
const appStore = useAppStore()
const ms = useMessage()

const systemMessage = ref(settingStore.systemMessage ?? '')
const selectedSystemPreset = ref('')
const showAddSystemPresetModal = ref(false)
const newSystemPresetName = ref('')

const defaultQuestion = ref(appStore.defaultQuestions?.[0] ?? '')
const selectedQuestionPreset = ref('')
const showAddQuestionPresetModal = ref(false)
const newQuestionPresetName = ref('')

// 输出详细程度设置
const outputDetailPresets = ref({ ...settingStore.outputDetailPresets })
const selectedOutputDetailLevel = ref<'simple' | 'medium' | 'detailed'>('medium')
const showEditOutputDetailModal = ref(false)
const editingOutputDetailType = ref<'simple' | 'medium' | 'detailed'>('medium')
const editingOutputDetailValue = ref('')

const systemMessageOptions = computed(() => {
  const presets = (settingStore.systemMessagePresets || [])
  const options = presets.map(p => ({ label: p.label, value: p.value }))
  if (presets.length > 0 && !selectedSystemPreset.value) {
    selectedSystemPreset.value = presets[0].value
    systemMessage.value = presets[0].value
  }
  return options
})

const defaultQuestionOptions = computed(() => {
  const presets = (settingStore.defaultQuestionPresets || [])
  const options = presets.map(p => ({ label: p.label, value: p.value }))
  if (presets.length > 0 && !selectedQuestionPreset.value) {
    selectedQuestionPreset.value = presets[0].value
    defaultQuestion.value = presets[0].value
  }
  return options
})

const outputDetailLevelOptions = computed(() => {
  return [
    { label: '简约', value: 'simple' as const },
    { label: '适中', value: 'medium' as const },
    { label: '详细', value: 'detailed' as const }
  ]
})

function handleSystemPresetChange(val: string) {
  systemMessage.value = val
  selectedSystemPreset.value = val
}

function handleQuestionPresetChange(val: string) {
  defaultQuestion.value = val
  selectedQuestionPreset.value = val
}

function handleOutputDetailLevelChange(val: 'simple' | 'medium' | 'detailed') {
  selectedOutputDetailLevel.value = val
}

function addSystemPreset() {
  if (!newSystemPresetName.value.trim()) {
    ms.error(t('setting.presetNameRequired'))
    return
  }
  const exists = settingStore.systemMessagePresets?.find(p => p.label === newSystemPresetName.value)
  if (exists) {
    ms.error(t('setting.presetAlreadyExists'))
    return
  }
  settingStore.addSystemMessagePreset({ label: newSystemPresetName.value, value: systemMessage.value })
  apiUpdateSettings({ system_message_presets: settingStore.systemMessagePresets })
  ms.success(t('setting.presetAddedSuccessfully'))
  newSystemPresetName.value = ''
  showAddSystemPresetModal.value = false
}

function cancelAddSystemPreset() {
  newSystemPresetName.value = ''
  showAddSystemPresetModal.value = false
}

function addQuestionPreset() {
  if (!newQuestionPresetName.value.trim()) {
    ms.error(t('setting.presetNameRequired'))
    return
  }
  const exists = settingStore.defaultQuestionPresets?.find(p => p.label === newQuestionPresetName.value)
  if (exists) {
    ms.error(t('setting.presetAlreadyExists'))
    return
  }
  settingStore.addDefaultQuestionPreset({ label: newQuestionPresetName.value, value: defaultQuestion.value })
  apiUpdateSettings({ default_question_presets: settingStore.defaultQuestionPresets })
  ms.success(t('setting.presetAddedSuccessfully'))
  newQuestionPresetName.value = ''
  showAddQuestionPresetModal.value = false
}

function cancelAddQuestionPreset() {
  newQuestionPresetName.value = ''
  showAddQuestionPresetModal.value = false
}

function saveSystemMessage() {
  settingStore.updateSetting({ systemMessage: systemMessage.value })
  apiUpdateSettings({ ai: { system_prompt: systemMessage.value } })
  ms.success(t('common.success'))
}

function saveDefaultQuestion() {
  appStore.setDefaultQuestions([defaultQuestion.value])
  apiUpdateSettings({ default_questions: [defaultQuestion.value] })
  ms.success(t('common.success'))
}

function openEditOutputDetailModal(type: 'simple' | 'medium' | 'detailed') {
  editingOutputDetailType.value = type
  editingOutputDetailValue.value = outputDetailPresets.value[type]
  showEditOutputDetailModal.value = true
}

function saveOutputDetailPreset() {
  outputDetailPresets.value[editingOutputDetailType.value] = editingOutputDetailValue.value
  settingStore.updateSetting({ outputDetailPresets: { ...outputDetailPresets.value } })
  apiUpdateSettings({ output_detail_presets: outputDetailPresets.value })
  ms.success(t('common.success'))
  showEditOutputDetailModal.value = false
}

function cancelEditOutputDetail() {
  showEditOutputDetailModal.value = false
}
</script>

<template>
  <div class="p-4 space-y-6">
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
      <NButton size="tiny" text type="primary" @click="saveSystemMessage" class="pt-2">
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
      <NButton size="tiny" text type="primary" @click="saveDefaultQuestion" class="pt-2">
        {{ $t('common.save') }}
      </NButton>
    </div>

    <!-- 输出详细程度设置 -->
    <div class="flex items-start space-x-4">
      <span class="flex-shrink-0 w-[120px] pt-2">{{ $t('setting.outputDetailLevel') }}</span>
      <div class="flex-1 space-y-2">
        <div class="flex gap-2">
          <NSelect
            :options="outputDetailLevelOptions"
            @update:value="handleOutputDetailLevelChange"
            v-model:value="selectedOutputDetailLevel"
            class="flex-1"
          />
        </div>
        <NInput
          v-model:value="outputDetailPresets[selectedOutputDetailLevel]"
          type="textarea"
          :autosize="{ minRows: 2, maxRows: 6 }"
          :placeholder="`请输入${selectedOutputDetailLevel === 'simple' ? '简约' : selectedOutputDetailLevel === 'medium' ? '适中' : '详细'}模式的提示词`"
        />
      </div>
      <NButton size="tiny" text type="primary" @click="openEditOutputDetailModal(selectedOutputDetailLevel)" class="pt-2">
        {{ $t('common.edit') }}
      </NButton>
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

    <!-- 编辑输出详细程度提示词模态框 -->
    <NModal v-model:show="showEditOutputDetailModal" preset="card" :title="`编辑${editingOutputDetailType === 'simple' ? '简约' : editingOutputDetailType === 'medium' ? '适中' : '详细'}提示词`" style="width: 600px;">
      <div class="space-y-4">
        <div>
          <label class="block mb-2">{{ $t('setting.content') }}</label>
          <NInput
            v-model:value="editingOutputDetailValue"
            type="textarea"
            :autosize="{ minRows: 4, maxRows: 10 }"
            placeholder="请输入提示词内容"
          />
        </div>
        <div class="flex justify-center space-x-3">
          <NButton @click="cancelEditOutputDetail">
            {{ $t('common.cancel') }}
          </NButton>
          <NButton type="primary" @click="saveOutputDetailPreset">
            {{ $t('common.save') }}
          </NButton>
        </div>
      </div>
    </NModal>
  </div>
</template>
