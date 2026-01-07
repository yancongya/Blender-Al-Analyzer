<script setup lang='ts'>
import { computed, ref, watch } from 'vue'
import { NModal, NTabPane, NTabs, NButton } from 'naive-ui'
import General from './General.vue'
import Advanced from './Advanced.vue'
import Prompt from './Prompt.vue'
import About from './About.vue'
import { useAuthStore } from '@/store'
import { SvgIcon } from '@/components/common'

interface Props {
  visible: boolean
  activeTab?: string
}

interface Emit {
  (e: 'update:visible', visible: boolean): void
  (e: 'update:activeTab', tab: string): void
}

const props = withDefaults(defineProps<Props>(), {
  activeTab: 'General'
})

const emit = defineEmits<Emit>()

const authStore = useAuthStore()

const isChatGPTAPI = computed<boolean>(() => !!authStore.isChatGPTAPI)

const active = ref('General')

// 监听外部传入的activeTab变化
watch(() => props.activeTab, (newTab) => {
  // 将传入的tab名称转换为组件中使用的名称
  const tabMap: Record<string, string> = {
    'general': 'General',
    'advanced': 'Advanced',
    'config': 'Config'
  }
  active.value = tabMap[newTab.toLowerCase()] || 'General'
}, { immediate: true })

const show = computed({
  get() {
    return props.visible
  },
  set(visible: boolean) {
    emit('update:visible', visible)
  },
})
</script>

<template>
  <NModal v-model:show="show" :auto-focus="false" preset="card" :closable="false" style="width: 95%; max-width: 640px">
    <div>
      <NTabs v-model:value="active" type="line" animated>
        <template #suffix>
          <NButton text class="ml-2" @click="show = false">
            <SvgIcon class="text-xl" icon="ri:close-line" />
          </NButton>
        </template>
        <NTabPane name="General" tab="General">
          <template #tab>
            <SvgIcon class="text-lg" icon="ri:file-user-line" />
            <span class="ml-2">{{ $t('setting.general') }}</span>
          </template>
          <div class="min-h-[100px]">
            <General />
          </div>
        </NTabPane>
        <NTabPane v-if="isChatGPTAPI" name="Advanced" tab="Advanced">
          <template #tab>
            <SvgIcon class="text-lg" icon="ri:equalizer-line" />
            <span class="ml-2">{{ $t('setting.advanced') }}</span>
          </template>
          <div class="min-h-[100px]">
            <Advanced />
          </div>
        </NTabPane>
        <NTabPane v-if="isChatGPTAPI" name="Prompt" tab="Prompt">
          <template #tab>
            <SvgIcon class="text-lg" icon="ri:chat-3-line" />
            <span class="ml-2">Prompt</span>
          </template>
          <div class="min-h-[100px]">
            <Prompt />
          </div>
        </NTabPane>
        <NTabPane name="Config" tab="Config">
          <template #tab>
            <SvgIcon class="text-lg" icon="ri:list-settings-line" />
            <span class="ml-2">{{ $t('setting.related') }}</span>
          </template>
          <About />
        </NTabPane>
      </NTabs>
    </div>
  </NModal>
</template>
