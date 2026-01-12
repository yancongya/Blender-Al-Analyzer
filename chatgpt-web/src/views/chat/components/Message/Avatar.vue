<script lang="ts" setup>
import { computed } from 'vue'
import { NAvatar } from 'naive-ui'
import { useUserStore, useSettingStore } from '@/store'
import { isString } from '@/utils/is'
import defaultAvatar from '/avatar.png'

interface Props {
  image?: boolean
}
const props = defineProps<Props>()

const userStore = useUserStore()
const settingStore = useSettingStore()

const userAvatar = computed(() => userStore.userInfo.avatar)

// 计算属性：根据是否为用户消息决定使用哪个头像
const currentAvatar = computed(() => {
  if (props.image) {
    // 用户消息，使用用户头像
    return (isString(userAvatar.value) && userAvatar.value.length > 0) ? userAvatar.value : defaultAvatar
  } else {
    // AI消息，使用配置中的AI助手头像
    // 优先从 settingStore 获取用户设置的头像
    // 如果没有设置，才使用 window.config 中的默认头像
    if (isString(settingStore.assistantAvatar) && settingStore.assistantAvatar.length > 0) {
      return settingStore.assistantAvatar
    }
    const config = (window as any).config || {}
    if (isString(config.assistant?.avatar) && config.assistant?.avatar.length > 0) {
      return config.assistant.avatar
    }
    return defaultAvatar
  }
})
</script>

<template>
  <NAvatar :src="currentAvatar" :fallback-src="defaultAvatar" round />
</template>
