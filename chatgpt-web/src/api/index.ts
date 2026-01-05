import type { AxiosProgressEvent, GenericAbortSignal } from 'axios'
import { get, post } from '@/utils/request'
import { useAuthStore, useSettingStore } from '@/store'

export function fetchChatAPI<T = any>(
  prompt: string,
  options?: { conversationId?: string; parentMessageId?: string },
  signal?: GenericAbortSignal,
) {
  return post<T>({
    url: '/chat',
    data: { prompt, options },
    signal,
  })
}

export function fetchChatConfig<T = any>() {
  return post<T>({
    url: '/config',
  })
}

export function fetchBlenderData<T = any>() {
  return get<T>({
    url: '/blender-data',
  })
}

export function fetchChatAPIProcess<T = any>(
  params: {
    prompt: string
    options?: { conversationId?: string; parentMessageId?: string; content?: string }
    signal?: GenericAbortSignal
    onDownloadProgress?: (progressEvent: AxiosProgressEvent) => void },
) {
  const settingStore = useSettingStore()
  const authStore = useAuthStore()

  let data: Record<string, any> = {
    question: params.prompt,
    conversationId: params.options?.conversationId,
    content: params.options?.content,
  }

  if (authStore.isChatGPTAPI) {
    data = {
      ...data,
      systemMessage: settingStore.systemMessage,
      temperature: settingStore.temperature,
      top_p: settingStore.top_p,
    }
  }

  return post<T>({
    url: '/stream-analyze',
    data,
    signal: params.signal,
    onDownloadProgress: params.onDownloadProgress,
  })
}

export function fetchSession<T>() {
  return post<T>({
    url: '/session',
  })
}

export function fetchVerify<T>(token: string) {
  return post<T>({
    url: '/verify',
    data: { token },
  })
}

export function fetchUiConfig<T = any>() {
  return get<T>({
    url: '/ui-config',
  })
}

export function triggerRefresh<T = any>() {
  return post<T>({
    url: '/trigger-refresh',
  })
}

export function updateSettings<T = any>(settings: Record<string, any>) {
  return post<T>({
    url: '/save-ui-config',
    data: settings,
  })
}

export function fetchPromptTemplates<T = any>() {
  return get<T>({
    url: '/prompt-templates',
  })
}

export function savePromptTemplates<T = any>(templates: any) {
  return post<T>({
    url: '/save-prompt-templates',
    data: templates,
  })
}

export function importPromptTemplates<T = any>(url: string) {
  return post<T>({
    url: '/import-prompt-templates',
    data: { url },
  })
}

export function fetchDefaultPromptTemplates<T = any>() {
  return get<T>({
    url: '/default-prompt-templates',
  })
}

export function sendSelectionToBlender<T = any>(text: string) {
  return post<T>({
    url: '/create-annotation',
    data: { text },
  })
}

export function updateBlenderAnnotation<T = any>(text: string) {
  return post<T>({
    url: '/update-annotation',
    data: { text },
  })
}

export function openBlenderAnnotationEditor<T = any>() {
  return post<T>({
    url: '/open-annotation-editor',
  })
}

export function fitBlenderAnnotation<T = any>() {
  return post<T>({
    url: '/fit-annotation',
  })
}
