<script lang="ts" setup>
import { computed } from 'vue'
import { NAvatar } from 'naive-ui'
import { useUserStore } from '@/store'
import { isString } from '@/utils/is'
import defaultAvatar from '/avatar.png'

interface Props {
  image?: boolean
}
const props = defineProps<Props>()

const userStore = useUserStore()

const userAvatar = computed(() => userStore.userInfo.avatar)

// 计算属性：根据是否为用户消息决定使用哪个头像
const currentAvatar = computed(() => {
  if (props.image) {
    // 用户消息，使用用户头像
    return (isString(userAvatar.value) && userAvatar.value.length > 0) ? userAvatar.value : defaultAvatar
  } else {
    // AI消息，使用配置中的AI助手头像
    // 从全局配置获取AI助手头像，如果不存在则使用默认头像
    const config = (window as any).config || {}
    return config.assistant?.avatar || defaultAvatar
  }
})
</script>

<template>
  <NAvatar :src="currentAvatar" :fallback-src="defaultAvatar" round />
</template>
