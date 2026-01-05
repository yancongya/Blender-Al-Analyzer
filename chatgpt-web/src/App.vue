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
