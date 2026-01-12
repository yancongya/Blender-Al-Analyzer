<script setup lang="ts">
import { NConfigProvider } from 'naive-ui'
import { onMounted } from 'vue'
import { NaiveProvider } from '@/components/common'
import { useTheme } from '@/hooks/useTheme'
import { useLanguage } from '@/hooks/useLanguage'
import { fetchUiConfig } from '@/api'
import { useAppStore, useSettingStore, useUserStore } from '@/store'

const { theme, themeOverrides } = useTheme()
const { language } = useLanguage()

const userStore = useUserStore()
const appStore = useAppStore()
const settingStore = useSettingStore()

onMounted(async () => {
  try {
    const { data } = await fetchUiConfig()
    // Set title/icon
    if (data.title)
      document.title = data.title
    if (data.icon) {
      const link = (document.querySelector('link[rel*=\'icon\']') || document.createElement('link')) as HTMLLinkElement
      link.type = 'image/x-icon'
      link.rel = 'shortcut icon'
      link.href = data.icon
      document.getElementsByTagName('head')[0].appendChild(link)
    }

    // Set User/Assistant
    if (data.user)
      userStore.updateUserInfo(data.user)
    
    // 保存 AI 助手头像到 settingStore
    if (data.assistant?.avatar)
      settingStore.updateSetting({ assistantAvatar: data.assistant.avatar })

    // 保存完整配置到全局window对象，供其他组件使用
    ;(window as any).config = data

    // 只有在store中没有保存的设置时才使用配置文件的默认值
    // 这样可以确保用户的选择在刷新后保持不变
    if (data.system_message_presets)
      settingStore.updateSetting({ systemMessagePresets: data.system_message_presets })

    if (data.default_question_presets)
      settingStore.updateSetting({ defaultQuestionPresets: data.default_question_presets })

    // Set Default Questions
    if (data.default_questions)
      appStore.setDefaultQuestions(data.default_questions)

    // Set Output Detail Presets (only if not already set by user)
    if (data.output_detail_presets && !settingStore.outputDetailPresets.simple)
      settingStore.updateSetting({ outputDetailPresets: data.output_detail_presets })

    // 仅在本地没有保存的设置时才使用配置文件中的默认值
    // 这样可以保留用户的选择
    const localSettings = settingStore.$state
    if (!localSettings.systemMessage && data.system_prompt)
      settingStore.updateSetting({ systemMessage: data.system_prompt })
    if (!localSettings.outputDetailLevel && data.output_detail_level)
      settingStore.updateSetting({ outputDetailLevel: data.output_detail_level })
    
    // 从配置文件读取输出详细程度预设
    if (data.output_detail_presets) {
      settingStore.updateSetting({ outputDetailPresets: data.output_detail_presets })
    }

    // 处理新的AI配置结构
    if (data.ai) {
      // 如果配置中有AI设置，更新store
      const aiUpdates: any = { ...data.ai }

      // 确保provider是正确的格式
      if (typeof data.ai.provider === 'string') {
        // 如果provider是字符串，转换为对象格式
        aiUpdates.provider = {
          name: data.ai.provider,
          model: data.ai.provider_configs?.[data.ai.provider]?.default_model || data.ai.deepseek?.model || 'deepseek-chat'
        }
      } else if (typeof data.ai.provider === 'object' && data.ai.provider.name) {
        // 如果provider已经是对象格式，确保它包含所需字段
        aiUpdates.provider = {
          name: data.ai.provider.name,
          model: data.ai.provider.model || data.ai.provider_configs?.[data.ai.provider.name]?.default_model || data.ai.deepseek?.model || 'deepseek-chat'
        }
      }

      // 更新AI设置
      settingStore.updateSetting({ ai: aiUpdates })
    }
  }
  catch (e) {
    console.error('Failed to load UI config', e)
  }
})
</script>

<template>
  <NConfigProvider
    class="h-full"
    :theme="theme"
    :theme-overrides="themeOverrides"
    :locale="language"
  >
    <NaiveProvider>
      <RouterView />
    </NaiveProvider>
  </NConfigProvider>
</template>
