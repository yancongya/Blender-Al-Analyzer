<script setup lang='ts'>
import { computed, ref } from 'vue'
import { NDropdown, useMessage } from 'naive-ui'
import AvatarComponent from './Avatar.vue'
import TextComponent from './Text.vue'
import { SvgIcon } from '@/components/common'
import { useIconRender } from '@/hooks/useIconRender'
import { t } from '@/locales'
import { useBasicLayout } from '@/hooks/useBasicLayout'
import { copyToClip } from '@/utils/copy'
import { useSettingStore } from '@/store'

interface Props {
  dateTime?: string
  text?: string
  inversion?: boolean
  error?: boolean
  loading?: boolean
  role?: string
}

interface Emit {
  (ev: 'regenerate'): void
  (ev: 'delete'): void
}

const props = defineProps<Props>()

const emit = defineEmits<Emit>()

const { isMobile } = useBasicLayout()

const { iconRender } = useIconRender()

const message = useMessage()
const settingStore = useSettingStore()

const textRef = ref<HTMLElement>()

const asRawText = ref(props.inversion)

const messageRef = ref<HTMLElement>()

// 角色切换下拉选项
const roleOptions = computed(() => {
  if (settingStore.systemMessagePresets) {
    return settingStore.systemMessagePresets.map((preset, index) => ({
      label: preset.label,
      key: `role-${index}`,
      preset: preset // 保存原始预设对象
    }))
  }
  return []
})

const options = computed(() => {
  const common = [
    {
      label: t('chat.copy'),
      key: 'copyText',
      icon: iconRender({ icon: 'ri:file-copy-2-line' }),
    },
    {
      label: t('common.delete'),
      key: 'delete',
      icon: iconRender({ icon: 'ri:delete-bin-line' }),
    },
  ]

  if (!props.inversion) {
    common.unshift({
      label: asRawText.value ? t('chat.preview') : t('chat.showRawText'),
      key: 'toggleRenderType',
      icon: iconRender({ icon: asRawText.value ? 'ic:outline-code-off' : 'ic:outline-code' }),
    })
  }

  return common
})

function handleSelect(key: 'copyText' | 'delete' | 'toggleRenderType') {
  switch (key) {
    case 'copyText':
      handleCopy()
      return
    case 'toggleRenderType':
      asRawText.value = !asRawText.value
      return
    case 'delete':
      emit('delete')
  }
}

function handleRoleSelect(key: string) {
  const selectedOption = roleOptions.value.find(option => option.key === key)
  if (selectedOption && selectedOption.preset) {
    // 更新系统消息
    settingStore.updateSetting({ systemMessage: selectedOption.preset.value })

    // 将更改保存到后端 - 通过自定义事件通知父组件处理
    window.dispatchEvent(new CustomEvent('save-settings-to-backend', {
      detail: {
        settings: { ai: { system_prompt: selectedOption.preset.value } },
        message: `Settings updated: System prompt changed to ${selectedOption.preset.label}`
      }
    }))

    // 发送确认消息
    const confirmationMessage = `I've switched to the role of "${selectedOption.preset.label}". Please respond according to this new role: ${selectedOption.preset.value}`
    // 触发事件通知父组件发送确认消息
    window.dispatchEvent(new CustomEvent('roleChanged', {
      detail: {
        message: confirmationMessage,
        roleLabel: selectedOption.preset.label
      }
    }))
  }
}

function handleRegenerate() {
  messageRef.value?.scrollIntoView()
  emit('regenerate')
}

async function handleCopy() {
  try {
    await copyToClip(props.text || '')
    message.success(t('chat.copied'))
  }
  catch {
    message.error(t('chat.copyFailed'))
  }
}

function handleAvatarClick() {
  // 创建一个自定义事件来通知打开设置面板
  const event = new CustomEvent('openSettingFromAvatar', {
    detail: {
      tab: props.inversion ? 'general' : 'advanced'
    }
  });
  window.dispatchEvent(event);
}
</script>

<template>
  <div
    ref="messageRef"
    class="flex w-full mb-6 overflow-hidden"
    :class="[{ 'flex-row-reverse': inversion }]"
  >
    <div
      class="flex items-center justify-center flex-shrink-0 h-8 overflow-hidden rounded-full basis-8 cursor-pointer"
      :class="[inversion ? 'ml-2' : 'mr-2']"
      @click="handleAvatarClick"
    >
      <AvatarComponent :image="inversion" />
    </div>
    <div class="overflow-hidden text-sm " :class="[inversion ? 'items-end' : 'items-start']">
      <NDropdown
        trigger="click"
        :options="roleOptions"
        @select="handleRoleSelect"
        placement="bottom-start"
        :class="[inversion ? 'text-right' : 'items-start']"
      >
        <p class="text-xs text-[#b4bbc4] cursor-pointer hover:text-[#6b7280] transition-colors" :class="[inversion ? 'text-right' : 'text-left']">
          <span v-if="role">{{ role }} - </span>{{ dateTime }}
        </p>
      </NDropdown>
      <div
        class="flex items-end gap-1 mt-2"
        :class="[inversion ? 'flex-row-reverse' : 'flex-row']"
      >
        <TextComponent
          ref="textRef"
          :inversion="inversion"
          :error="error"
          :text="text"
          :loading="loading"
          :as-raw-text="asRawText"
        />
        <div class="flex flex-col">
          <button
            v-if="!inversion"
            class="mb-2 transition text-neutral-300 hover:text-neutral-800 dark:hover:text-neutral-300"
            @click="handleRegenerate"
          >
            <SvgIcon icon="ri:restart-line" />
          </button>
          <NDropdown
            :trigger="isMobile ? 'click' : 'hover'"
            :placement="!inversion ? 'right' : 'left'"
            :options="options"
            @select="handleSelect"
          >
            <button class="transition text-neutral-300 hover:text-neutral-800 dark:hover:text-neutral-200">
              <SvgIcon icon="ri:more-2-fill" />
            </button>
          </NDropdown>
        </div>
      </div>
    </div>
  </div>
</template>
