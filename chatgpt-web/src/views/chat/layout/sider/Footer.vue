<script setup lang='ts'>
import { defineAsyncComponent, ref, onMounted, onUnmounted } from 'vue'
import { HoverButton, SvgIcon, UserAvatar } from '@/components/common'

const Setting = defineAsyncComponent(() => import('@/components/common/Setting/index.vue'))

const show = ref(false)
const activeTab = ref('general') // 默认为总览tab

function openGeneralTab() {
  activeTab.value = 'general'
  show.value = true
}

function openAdvancedTab() {
  activeTab.value = 'advanced'
  show.value = true
}

// 监听来自对话面板的事件
function handleOpenSettingFromAvatar(event: Event) {
  const customEvent = event as CustomEvent
  activeTab.value = customEvent.detail.tab
  show.value = true
}

onMounted(() => {
  window.addEventListener('openSettingFromAvatar', handleOpenSettingFromAvatar as EventListener)
})

onUnmounted(() => {
  window.removeEventListener('openSettingFromAvatar', handleOpenSettingFromAvatar as EventListener)
})
</script>

<template>
  <footer class="flex items-center justify-between min-w-0 p-4 overflow-hidden border-t dark:border-neutral-800">
    <div class="flex-1 flex-shrink-0 overflow-hidden">
      <UserAvatar @click="openGeneralTab" class="cursor-pointer" />
    </div>

    <HoverButton @click="openAdvancedTab">
      <span class="text-xl text-[#4f555e] dark:text-white">
        <SvgIcon icon="ri:settings-4-line" />
      </span>
    </HoverButton>

    <Setting v-if="show" v-model:visible="show" :active-tab="activeTab" @update:active-tab="activeTab = $event" />
  </footer>
</template>