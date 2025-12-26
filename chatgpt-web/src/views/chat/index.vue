<script setup lang='ts'>
import type { Ref } from 'vue'
import { computed, h, onMounted, onUnmounted, ref } from 'vue'
import { useRoute } from 'vue-router'
// removed unused storeToRefs
import { NAutoComplete, NButton, NCard, NInput, NModal, NTag, useDialog, useMessage } from 'naive-ui'
import { toPng } from 'html-to-image'
import { Message } from './components'
import NodeDataView from './components/NodeDataView.vue'
import { useScroll } from './hooks/useScroll'
import { useChat } from './hooks/useChat'
import { useUsingContext } from './hooks/useUsingContext'
import HeaderComponent from './components/Header/index.vue'
import { HoverButton, SvgIcon } from '@/components/common'
import { useBasicLayout } from '@/hooks/useBasicLayout'
import { useAppStore, useChatStore, usePromptStore, useSettingStore, useUserStore } from '@/store'
import { fetchBlenderData, fetchChatAPIProcess, fetchUiConfig, triggerRefresh, updateSettings as apiUpdateSettings } from '@/api'
import { t } from '@/locales'
import { copyToClip } from '@/utils/copy'

let controller = new AbortController()

const route = useRoute()
const dialog = useDialog()
const ms = useMessage()

const appStore = useAppStore()
const chatStore = useChatStore()
const settingStore = useSettingStore()
const userStore = useUserStore()

const { isMobile } = useBasicLayout()
const { addChat, updateChat, updateChatSome, getChatByUuidAndIndex } = useChat()

const { scrollRef, scrollToBottom, scrollToBottomIfAtBottom } = useScroll()
const { usingContext, toggleUsingContext } = useUsingContext()

const { uuid } = route.params as { uuid: string }

const dataSources = computed(() => chatStore.getChatByUuid(+uuid))
const conversationList = computed(() => dataSources.value.filter(item => (!item.inversion && !!item.conversationOptions)))

const prompt = ref<string>('')
const attachedVariables = ref<string[]>([])
const loading = ref<boolean>(false)
const inputRef = ref<Ref | null>(null)
const thinkingEnabled = computed<boolean>(() => !!(settingStore.ai?.thinking?.enabled))
const webSearchEnabled = computed<boolean>(() => !!(settingStore.ai?.web_search?.enabled))

const currentConversationId = computed<string>(() => {
  // Find the last message that has a conversationId, traversing backwards
  const list = conversationList.value
  for (let i = list.length - 1; i >= 0; i--) {
    const cid = list[i].conversationOptions?.conversationId
    if (cid) return cid
  }
  return ''
})
const currentRounds = computed<number>(() => {
  const cid = currentConversationId.value
  if (!cid) return 0
  return conversationList.value.filter(it => it.conversationOptions?.conversationId === cid).length
})

const hasNodeDataReference = computed(() => attachedVariables.value.includes('Current Node Data') || prompt.value.includes('{{Current Node Data}}') || prompt.value.includes('Current Node Data'))
const userMessagePreview = computed(() => {
  if (hasNodeDataReference.value) {
    return prompt.value.replace(/{{Current Node Data}}|Current Node Data/g, '').trim()
  }
  return prompt.value
})

function removeVariable(v: string) {
    attachedVariables.value = attachedVariables.value.filter(item => item !== v)
}

const nodeData = computed(() => chatStore.nodeData || {
  nodes: '',
  filename: 'Unknown',
  version: '',
  node_type: '',
  tokens: 0
})

// Data Detail Level: 0=Ultra Lite, 1=Lite, 2=Standard, 3=Full
const dataDetailLevel = ref(2)

const processedNodeData = computed(() => {
  const rawNodes = nodeData.value.nodes
  if (!rawNodes) {
    return { ...nodeData.value, nodes: '', tokens: 0 }
  }
  
  // If Full level, return raw data
  if (dataDetailLevel.value === 3) {
    return nodeData.value
  }

  try {
    const data = JSON.parse(rawNodes)
    
    // Recursive cleaner function
    const cleanNode = (node: any) => {
      // Remove visual properties
      delete node.location
      delete node.width
      delete node.height
      delete node.color
      delete node.use_custom_color
      delete node.select
      
      if (dataDetailLevel.value === 0) { // Ultra Lite mode
        // Keep only minimal identifiers
        const minimal: any = {
          name: node.name,
          type: node.type,
        }
        // Replace node fields in place
        node.name = minimal.name
        node.type = minimal.type
        delete node.label
        delete node.inputs
        delete node.outputs
        delete node.group_content
      }
      
      if (dataDetailLevel.value === 1) { // Lite mode
        // Remove identifier from inputs/outputs
        if (node.inputs) {
           node.inputs.forEach((i: any) => delete i.identifier)
           // Filter unconnected inputs that have no special value
           node.inputs = node.inputs.filter((i: any) => i.is_connected || (i.default_value !== undefined && i.default_value !== 'N/A'))
        }
        if (node.outputs) {
           node.outputs.forEach((o: any) => delete o.identifier)
        }
      }
      
      // Handle groups recursively
      if (node.group_content && node.group_content.nodes) {
        node.group_content.nodes.forEach(cleanNode)
      }
    }

    // Handle both 'selected_nodes' (top level) and 'nodes' (recursive/group)
    const nodesArray = data.selected_nodes || data.nodes
    if (nodesArray && Array.isArray(nodesArray)) {
      nodesArray.forEach(cleanNode)
    }
    
    // Remove metadata in Lite mode
    if (dataDetailLevel.value === 1 || dataDetailLevel.value === 0) {
       delete data.blender_version
       delete data.addon_version
       delete data.selected_nodes_count
       delete data.node_tree_type
    }

    const filteredStr = JSON.stringify(data, null, 2)
    return {
      ...nodeData.value,
      nodes: filteredStr,
      tokens: Math.ceil(filteredStr.length / 4) // Estimate tokens
    }
  } catch (e) {
    // If parse fails, return raw
    return nodeData.value
  }
})

const showNodeDataModal = ref(false)

const displayMode = ref<'code' | 'graph'>('code')

const isModalFullscreen = ref(false)

function toggleModalFullscreen() {
  isModalFullscreen.value = !isModalFullscreen.value
}

// Listen for ESC to exit fullscreen
onMounted(() => {
    // ... existing onMounted ...
    window.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && isModalFullscreen.value) {
            isModalFullscreen.value = false
        }
    })
})

function handleCopy(text: string) {
    if (!text) return
    copyToClip(text).then(() => {
        ms.success(t('common.copySuccess'))
    }).catch(() => {
        ms.error(t('common.copyFailed'))
    })
}

function handleCopyAll() {
    const parts = []
    
    // System
    parts.push(`[${t('chat.defaultPrompt')}]\n${settingStore.systemMessage}`)
    
    // User
    let userMsg = userMessagePreview.value
    if (hasNodeDataReference.value || (!prompt.value && processedNodeData.value.nodes)) {
        userMsg = `[Current Node Data Variable] (${processedNodeData.value.tokens} tokens)\n${userMsg}`
    }
    parts.push(`[${t('chat.userMessageStructure')}]\n${userMsg}`)
    
    // Node Data
    if (processedNodeData.value.nodes) {
        parts.push(`[${t('chat.nodeDataSource')}]\n${processedNodeData.value.nodes}`)
    }
    
    const fullText = parts.join('\n\n' + '-'.repeat(20) + '\n\n')
    handleCopy(fullText)
}

let autoRefreshTimer: number | null = null

async function fetchNodeData() {
  try {
    const res = await fetchBlenderData<Chat.NodeData>()
    if (res.data) {
      chatStore.setNodeData({
        nodes: res.data.nodes || '',
        filename: res.data.filename || 'Unknown',
        version: res.data.version || '',
        node_type: res.data.node_type || '',
        tokens: res.data.tokens || 0
      })
    }
  }
  catch (error) {
    console.error('Failed to fetch node data', error)
  }
}

async function autoFetchNodeData() {
  try {
    const res = await fetchBlenderData<Chat.NodeData>()
    if (res.data) {
      const prevTokens = nodeData.value.tokens
      const prevNodes = nodeData.value.nodes
      const nextNodes = res.data.nodes || ''
      const nextTokens = res.data.tokens || 0
      if (nextTokens !== prevTokens || nextNodes !== prevNodes) {
        chatStore.setNodeData({
          nodes: nextNodes,
          filename: res.data.filename || 'Unknown',
          version: res.data.version || '',
          node_type: res.data.node_type || '',
          tokens: nextTokens
        })
      }
    }
  } catch (error) {
    // swallow
  }
}

async function loadConfig() {
  try {
    const res = await fetchUiConfig()
    if (res.data) {
      const config = res.data
      
      if (config.default_questions) appStore.setDefaultQuestions(config.default_questions)
      if (config.system_message_presets) settingStore.updateSetting({ systemMessagePresets: config.system_message_presets })
      if (config.default_question_presets) settingStore.updateSetting({ defaultQuestionPresets: config.default_question_presets })
      if (config.theme) appStore.setTheme(config.theme)
      if (config.language) appStore.setLanguage(config.language)
      if (config.user) userStore.updateUserInfo(config.user)
      
      if (config.ai) {
        if (config.ai.system_prompt) settingStore.updateSetting({ systemMessage: config.ai.system_prompt })
        settingStore.updateSetting({ ai: config.ai })
      }
    }
  } catch (error) {
    console.error('Failed to load config', error)
  }
}

async function handleRefresh() {
  try {
    await triggerRefresh()
    // Wait for Blender to pick up the refresh request (timer is 1s)
    await new Promise(resolve => setTimeout(resolve, 1500))
    await fetchNodeData()
    await loadConfig()
    ms.success(t('common.success'))
  }
  catch (error) {
    console.error('Failed to refresh', error)
    ms.error(t('common.wrong'))
  }
}

function toggleThinkingMode() {
  const next = !thinkingEnabled.value
  const ai = {
    ...settingStore.ai,
    thinking: { enabled: next },
  }
  settingStore.updateSetting({ ai })
  apiUpdateSettings({ ai })
}

function toggleWebSearchMode() {
  const next = !webSearchEnabled.value
  const ai = {
    ...settingStore.ai,
    web_search: { ...settingStore.ai?.web_search, enabled: next },
  }
  settingStore.updateSetting({ ai })
  apiUpdateSettings({ ai })
}

onMounted(() => {
  fetchNodeData()
  loadConfig()
  scrollToBottom()
  if (inputRef.value && !isMobile.value)
    inputRef.value?.focus()
  autoRefreshTimer = window.setInterval(autoFetchNodeData, 1500)
})

onUnmounted(() => {
  if (autoRefreshTimer) {
    window.clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
})

// 添加PromptStore
const promptStore = usePromptStore()

// 使用getter以避免类型问题
const promptTemplate = computed<any>(() => promptStore.getPromptList().promptList)

// 未知原因刷新页面，loading 状态不会重置，手动重置
dataSources.value.forEach((item, index) => {
  if (item.loading)
    updateChatSome(+uuid, index, { loading: false })
})

function handleSubmit() {
  onConversation()
}

async function onConversation() {
  let message = prompt.value

  if (loading.value)
    return

  // If we have variables but no text, allow it if variables imply content (like node data)
  // But usually we want some prompt. However, if user just wants to analyze node data, maybe empty prompt is fine?
  // Let's allow empty prompt if variables exist.
  const hasVariables = attachedVariables.value.length > 0
  
  if (!message || message.trim() === '') {
      if (!hasVariables) return
      // If has variables, message can be empty string initially
      message = '' 
  }
  
  // Combine variables into message
  // For 'Current Node Data', we use {{Current Node Data}} syntax which backend/frontend logic handles
  const variableContent = attachedVariables.value.map(v => `{{${v}}}`).join('\n')
  if (variableContent) {
      message = variableContent + '\n' + message
  }
  message = message.trim()

  // Note: Variable replacement {{Current Node Data}} is handled by backend
  // We send the variable as-is to keep the UI clean

  controller = new AbortController()

  addChat(
    +uuid,
    {
      dateTime: new Date().toLocaleString(),
      text: message,
      inversion: true,
      error: false,
      conversationOptions: null,
      requestOptions: { prompt: message, options: null },
    },
  )
  scrollToBottom()

  loading.value = true
  prompt.value = ''

  let options: Chat.ConversationRequest = {}
  const lastContext = conversationList.value[conversationList.value.length - 1]?.conversationOptions

  if (lastContext && usingContext.value)
    options = { ...lastContext }

  addChat(
    +uuid,
    {
      dateTime: new Date().toLocaleString(),
      text: t('chat.thinking'),
      loading: true,
      inversion: false,
      error: false,
      conversationOptions: null,
      requestOptions: { prompt: message, options: { ...options } },
    },
  )
  scrollToBottom()

  try {
    await fetchNodeData() // Refresh node data before sending
    const fetchChatAPIOnce = async () => {
      await fetchChatAPIProcess<Chat.ConversationResponse>({
        prompt: message,
        options: { ...options, content: processedNodeData.value.nodes },
        signal: controller.signal,
        onDownloadProgress: ({ event }) => {
          const xhr = event.target
          const { responseText } = xhr
          const lines = responseText.split('\n')
          let fullText = ''
          let fullThinking = ''
          let currentConversationId = ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const jsonStr = line.substring(6).trim()
              if (jsonStr === '[DONE]') break
              try {
                const data = JSON.parse(jsonStr)
                if (data.type === 'start') {
                  currentConversationId = data.conversationId
                }
                else if (data.type === 'chunk') {
                  if (typeof data.content === 'string' && data.content) fullText += data.content
                }
                else if (data.type === 'thinking') {
                  if (typeof data.content === 'string' && data.content) fullThinking += data.content
                }
                else if (data.type === 'complete') {
                  currentConversationId = data.conversationId
                }
              }
              catch (e) { }
            }
          }

          const combinedText = (fullThinking ? `【思维链】\n${fullThinking}\n<<END_THINKING>>\n` : '') + fullText
          updateChat(
            +uuid,
            dataSources.value.length - 1,
            {
              dateTime: new Date().toLocaleString(),
              text: combinedText,
              inversion: false,
              error: false,
              loading: true,
              conversationOptions: { conversationId: currentConversationId, parentMessageId: '' },
              requestOptions: { prompt: message, options: { ...options } },
            },
          )
          scrollToBottomIfAtBottom()
        },
      })
      updateChatSome(+uuid, dataSources.value.length - 1, { loading: false })
    }

    await fetchChatAPIOnce()
  }
  catch (error: any) {
    const errorMessage = error?.message ?? t('common.wrong')

    if (error.message === 'canceled') {
      updateChatSome(
        +uuid,
        dataSources.value.length - 1,
        {
          loading: false,
        },
      )
      scrollToBottomIfAtBottom()
      return
    }

    const currentChat = getChatByUuidAndIndex(+uuid, dataSources.value.length - 1)

    if (currentChat?.text && currentChat.text !== '') {
      updateChatSome(
        +uuid,
        dataSources.value.length - 1,
        {
          text: `${currentChat.text}\n[${errorMessage}]`,
          error: false,
          loading: false,
        },
      )
      return
    }

    updateChat(
      +uuid,
      dataSources.value.length - 1,
      {
        dateTime: new Date().toLocaleString(),
        text: errorMessage,
        inversion: false,
        error: true,
        loading: false,
        conversationOptions: null,
        requestOptions: { prompt: message, options: { ...options } },
      },
    )
    scrollToBottomIfAtBottom()
  }
  finally {
    loading.value = false
  }
}

async function onRegenerate(index: number) {
  if (loading.value)
    return

  controller = new AbortController()

  const { requestOptions } = dataSources.value[index]

  let message = requestOptions?.prompt ?? ''

  let options: Chat.ConversationRequest = {}

  if (requestOptions.options)
    options = { ...requestOptions.options }

  loading.value = true

  updateChat(
    +uuid,
    index,
    {
      dateTime: new Date().toLocaleString(),
      text: '',
      inversion: false,
      error: false,
      loading: true,
      conversationOptions: null,
      requestOptions: { prompt: message, options: { ...options } },
    },
  )

  try {
    await fetchNodeData()
    const fetchChatAPIOnce = async () => {
      await fetchChatAPIProcess<Chat.ConversationResponse>({
        prompt: message,
        options: { ...options, content: processedNodeData.value.nodes },
        signal: controller.signal,
        onDownloadProgress: ({ event }) => {
          const xhr = event.target
          const { responseText } = xhr
          const lines = responseText.split('\n')
          let fullText = ''
          let fullThinking = ''
          let currentConversationId = ''

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const jsonStr = line.substring(6).trim()
              if (jsonStr === '[DONE]') break
              try {
                const data = JSON.parse(jsonStr)
                if (data.type === 'start') {
                  currentConversationId = data.conversationId
                }
                else if (data.type === 'chunk') {
                  if (typeof data.content === 'string' && data.content) fullText += data.content
                }
                else if (data.type === 'thinking') {
                  if (typeof data.content === 'string' && data.content) fullThinking += data.content
                }
                else if (data.type === 'complete') {
                  currentConversationId = data.conversationId
                }
              }
              catch (e) { }
            }
          }

          const combinedText = (fullThinking ? `【思维链】\n${fullThinking}\n<<END_THINKING>>\n` : '') + fullText
          updateChat(
            +uuid,
            index,
            {
              dateTime: new Date().toLocaleString(),
              text: combinedText,
              inversion: false,
              error: false,
              loading: true,
              conversationOptions: { conversationId: currentConversationId, parentMessageId: '' },
              requestOptions: { prompt: message, options: { ...options } },
            },
          )
          scrollToBottomIfAtBottom()
        },
      })
      updateChatSome(+uuid, index, { loading: false })
    }
    await fetchChatAPIOnce()
  }
  catch (error: any) {
    if (error.message === 'canceled') {
      updateChatSome(
        +uuid,
        index,
        {
          loading: false,
        },
      )
      return
    }

    const errorMessage = error?.message ?? t('common.wrong')

    updateChat(
      +uuid,
      index,
      {
        dateTime: new Date().toLocaleString(),
        text: errorMessage,
        inversion: false,
        error: true,
        loading: false,
        conversationOptions: null,
        requestOptions: { prompt: message, options: { ...options } },
      },
    )
  }
  finally {
    loading.value = false
  }
}

function handleExport() {
  if (loading.value)
    return

  const d = dialog.warning({
    title: t('chat.exportImage'),
    content: t('chat.exportImageConfirm'),
    positiveText: t('common.yes'),
    negativeText: t('common.no'),
    onPositiveClick: async () => {
      try {
        d.loading = true
        const ele = document.getElementById('image-wrapper')
        const imgUrl = await toPng(ele as HTMLDivElement)
        const tempLink = document.createElement('a')
        tempLink.style.display = 'none'
        tempLink.href = imgUrl
        tempLink.setAttribute('download', 'chat-shot.png')
        if (typeof tempLink.download === 'undefined')
          tempLink.setAttribute('target', '_blank')
        document.body.appendChild(tempLink)
        tempLink.click()
        document.body.removeChild(tempLink)
        window.URL.revokeObjectURL(imgUrl)
        d.loading = false
        ms.success(t('chat.exportSuccess'))
        Promise.resolve()
      }
      catch (error: any) {
        ms.error(t('chat.exportFailed'))
      }
      finally {
        d.loading = false
      }
    },
  })
}

function handleDelete(index: number) {
  if (loading.value)
    return

  dialog.warning({
    title: t('chat.deleteMessage'),
    content: t('chat.deleteMessageConfirm'),
    positiveText: t('common.yes'),
    negativeText: t('common.no'),
    onPositiveClick: () => {
      chatStore.deleteChatByUuid(+uuid, index)
    },
  })
}

function handleClear() {
  if (loading.value)
    return

  dialog.warning({
    title: t('chat.clearChat'),
    content: t('chat.clearChatConfirm'),
    positiveText: t('common.yes'),
    negativeText: t('common.no'),
    onPositiveClick: () => {
      chatStore.clearChatByUuid(+uuid)
    },
  })
}

function handleEnter(event: KeyboardEvent) {
  if (!isMobile.value) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      handleSubmit()
    }
  }
  else {
    if (event.key === 'Enter' && event.ctrlKey) {
      event.preventDefault()
      handleSubmit()
    }
  }
}

function handleStop() {
  if (loading.value) {
    controller.abort()
    loading.value = false
  }
}

// 可优化部分
// 搜索选项计算，这里使用value作为索引项，所以当出现重复value时渲染异常(多项同时出现选中效果)
// 理想状态下其实应该是key作为索引项,但官方的renderOption会出现问题，所以就需要value反renderLabel实现
const searchOptions = computed(() => {
  if (prompt.value.startsWith('@')) {
    const list: { label: string; value: string }[] = []
    
    // 1. Existing Prompts (Store)
    const storePrompts = promptTemplate.value.filter((item: { key: string }) => item.key.toLowerCase().includes(prompt.value.substring(1).toLowerCase())).map((obj: { value: any }) => {
      return {
        label: obj.value,
        value: obj.value,
      }
    })
    list.push(...storePrompts)

    // 2. System Prompts (Presets)
    if (settingStore.systemMessagePresets) {
        settingStore.systemMessagePresets.forEach(p => {
            if (p.label.toLowerCase().includes(prompt.value.substring(1).toLowerCase()) || prompt.value === '@') {
                list.push({
                    label: p.label,
                    value: `__SYSTEM_PROMPT:${p.value}__`
                })
            }
        })
    }

    // 3. Default Questions (Presets)
    if (settingStore.defaultQuestionPresets) {
        settingStore.defaultQuestionPresets.forEach(p => {
             if (p.label.toLowerCase().includes(prompt.value.substring(1).toLowerCase()) || prompt.value === '@') {
                list.push({
                    label: p.label,
                    value: `__QUESTION:${p.value}`
                })
            }
        })
    }

    // 4. Node Data
    if (nodeData.value.nodes) {
      list.unshift({
        label: 'Current Node Data',
        value: '{{Current Node Data}}',
      })
    }
    return list
  }
  else {
    return []
  }
})

function handleAutoCompleteSelect(value: string) {
    if (value.startsWith('__SYSTEM_PROMPT:')) {
        const content = value.replace('__SYSTEM_PROMPT:', '').replace('__', '')
        settingStore.updateSetting({ systemMessage: content })
        ms.success(`Role switched to: ${content.substring(0, 20)}...`)
        // Clear the prompt after selection (next tick)
        setTimeout(() => {
            prompt.value = ''
        }, 0)
    } else if (value === '{{Current Node Data}}') {
        if (!attachedVariables.value.includes('Current Node Data')) {
            attachedVariables.value.push('Current Node Data')
        }
        setTimeout(() => {
            prompt.value = ''
        }, 0)
    } else if (value.startsWith('__QUESTION:')) {
        const content = value.replace('__QUESTION:', '')
        setTimeout(() => {
            prompt.value = content
        }, 0)
    } else {
        // Normal prompt template
        // Default behavior of NAutoComplete is to replace.
        // But since we are using custom input slot and v-model on it, 
        // we might need to be careful. 
        // For normal text, it's fine.
    }
}

const currentRoleLabel = computed(() => {
  const currentMsg = settingStore.systemMessage
  const preset = settingStore.systemMessagePresets?.find(p => p.value === currentMsg)
  if (preset) return preset.label
  return currentMsg && currentMsg.length > 20 ? currentMsg.substring(0, 20) + '...' : (currentMsg || 'Default')
})

// value反渲染key
const renderOption = (option: { label: string; value?: string }) => {
  if (option.label === 'Current Node Data') {
    return h('div', { class: 'flex items-center justify-between gap-2' }, [
        h('span', {}, 'Node Data'),
        h(NTag, { type: 'warning', size: 'small', bordered: false }, { default: () => 'Variable' })
    ])
  }
    
  for (const i of promptTemplate.value) {
    if (i.value === option.label)
      return [i.key]
  }
  
  if (option.value && option.value.startsWith('__SYSTEM_PROMPT:')) {
      return h('div', { class: 'flex items-center justify-between gap-2' }, [
        h('span', {}, option.label),
        h(NTag, { type: 'info', size: 'small', bordered: false }, { default: () => 'Role' })
      ])
  }

  if (option.value && option.value.startsWith('__QUESTION:')) {
      return h('div', { class: 'flex items-center justify-between gap-2' }, [
        h('span', {}, option.label),
        h(NTag, { type: 'success', size: 'small', bordered: false }, { default: () => 'Question' })
      ])
  }

  return option.label
}

const placeholder = computed(() => {
  if (isMobile.value)
    return t('chat.placeholderMobile')
  return t('chat.placeholder')
})

const buttonDisabled = computed(() => {
  return loading.value || (!prompt.value?.trim() && attachedVariables.value.length === 0)
})

const footerClass = computed(() => {
  let classes = ['p-4']
  if (isMobile.value)
    classes = ['sticky', 'left-0', 'bottom-0', 'right-0', 'p-2', 'pr-3', 'overflow-hidden']
  return classes
})

onUnmounted(() => {
  if (loading.value)
    controller.abort()
})
</script>

<template>
  <div class="flex flex-col w-full h-full">
    <HeaderComponent
      v-if="isMobile"
      :using-context="usingContext"
      @export="handleExport"
      @handle-clear="handleClear"
    />
    <div v-if="!isMobile" class="flex items-center justify-between p-4 border-b dark:border-neutral-800">
      <div class="flex items-center gap-2">
        <!-- Icon -->
        <img src="/favicon.svg" alt="Icon" class="w-6 h-6" />
        
        <!-- Version -->
        <span v-if="nodeData.version" class="text-xs text-gray-500 font-mono">
          v{{ nodeData.version }}
        </span>
        <span v-else class="text-xs text-gray-400">v?.?.?</span>

        <!-- Filename -->
        <span class="text-lg font-bold">
          {{ nodeData.filename !== 'Unknown' ? nodeData.filename : 'Blender AI Assistant' }}
        </span>

        <!-- Node Type -->
        <span v-if="nodeData.node_type" class="text-xs text-gray-400 bg-gray-100 dark:bg-gray-800 px-1 rounded">{{ nodeData.node_type }}</span>

        <!-- Refresh Button -->
        <NButton size="tiny" quaternary circle @click="handleRefresh">
          <template #icon>
            <SvgIcon icon="ri:refresh-line" />
          </template>
        </NButton>

        <!-- Status Badge -->
          <span 
          class="text-xs px-2 py-1 rounded cursor-pointer hover:opacity-80 transition select-none ml-2" 
          :class="processedNodeData.nodes ? 'bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300' : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'"
          @click="processedNodeData.nodes && (showNodeDataModal = true)"
          :title="processedNodeData.nodes ? 'Click to view details' : ''"
          >
            {{ processedNodeData.nodes ? 'Node Data Loaded' : 'No Node Data' }}
            <span v-if="processedNodeData.tokens > 0" class="ml-1 opacity-75">({{ processedNodeData.tokens }} tokens)</span>
          </span>
          <div class="ml-4 flex items-center gap-2 text-xs whitespace-nowrap overflow-hidden text-ellipsis">
            <span :class="thinkingEnabled ? 'text-green-600' : 'text-gray-500'">Thinking: {{ thinkingEnabled ? 'On' : 'Off' }}</span>
            <span v-if="currentConversationId" class="text-gray-500" :title="currentConversationId">CID: {{ currentConversationId.slice(0, 8) }}...</span>
            <span v-else class="text-gray-500">CID: -</span>
            <span class="text-gray-500">Rounds: {{ currentRounds }}</span>
          </div>
        </div>
      </div>

    <NModal v-model:show="showNodeDataModal">
      <NCard
        style="width: 800px; max-width: 90vw;"
        :title="$t('chat.messageStructurePreview')"
        :bordered="false"
        size="huge"
        role="dialog"
        aria-modal="true"
      >
        <template #header-extra>
            <NButton size="small" secondary @click="handleCopyAll">
                <template #icon>
                    <SvgIcon icon="ri:file-copy-line" />
                </template>
                {{ $t('chat.copyAll') }}
            </NButton>
        </template>
        <div class="max-h-[70vh] overflow-y-auto font-mono text-xs space-y-2">
          <!-- System Prompt -->
          <div class="border rounded p-2 dark:border-gray-700">
             <div class="flex justify-between items-center mb-1">
                 <div class="font-bold text-blue-600 dark:text-blue-400">{{ $t('chat.defaultPrompt') }}</div>
                 <NButton size="tiny" quaternary circle @click="handleCopy(settingStore.systemMessage)">
                    <template #icon><SvgIcon icon="ri:file-copy-2-line" /></template>
                 </NButton>
             </div>
             <div class="whitespace-pre-wrap bg-gray-50 dark:bg-gray-900 p-2 rounded text-gray-600 dark:text-gray-400">
               {{ settingStore.systemMessage }}
             </div>
          </div>

          <!-- User Message -->
          <div class="border rounded p-2 dark:border-gray-700">
             <div class="flex justify-between items-center mb-1">
                 <div class="font-bold text-green-600 dark:text-green-400">{{ $t('chat.userMessageStructure') }}</div>
                 <NButton size="tiny" quaternary circle @click="handleCopy(userMessagePreview)">
                    <template #icon><SvgIcon icon="ri:file-copy-2-line" /></template>
                 </NButton>
             </div>
             <div class="whitespace-pre-wrap bg-gray-50 dark:bg-gray-900 p-2 rounded">
                <template v-if="hasNodeDataReference || (!prompt && processedNodeData.nodes)">
                  <div class="p-2 mb-2 bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 rounded border border-purple-200 dark:border-purple-800 flex justify-between items-center">
                     <span>[Current Node Data Variable]</span>
                     <span class="text-xs opacity-70">{{ processedNodeData.tokens }} tokens</span>
                  </div>
                </template>
                <div>{{ userMessagePreview || '(Input your question here...)' }}</div>
             </div>
          </div>

          <!-- Current Node Data -->
          <!-- Normal View (inside Modal) -->
          <div v-if="!isModalFullscreen" class="relative h-[400px]">
             <NodeDataView 
                :processed-data="processedNodeData"
                v-model:detail-level="dataDetailLevel"
                v-model:display-mode="displayMode"
                :is-fullscreen="false"
                @toggle-fullscreen="toggleModalFullscreen"
                @copy="handleCopy"
             />
          </div>
          
          <!-- Fullscreen View (Teleport to Body) -->
          <Teleport to="body">
             <div v-if="isModalFullscreen" class="fixed inset-0 z-[99999] bg-white dark:bg-[#101014]">
                 <NodeDataView 
                    :processed-data="processedNodeData"
                    v-model:detail-level="dataDetailLevel"
                    v-model:display-mode="displayMode"
                    :is-fullscreen="true"
                    @toggle-fullscreen="toggleModalFullscreen"
                    @copy="handleCopy"
                 />
             </div>
          </Teleport>
        </div>
      </NCard>
    </NModal>
    <main class="flex-1 overflow-hidden">
      <div id="scrollRef" ref="scrollRef" class="h-full overflow-hidden overflow-y-auto">
        <div
          class="w-full max-w-screen-xl m-auto dark:bg-[#101014]"
          :class="[isMobile ? 'p-2' : 'p-4']"
        >
          <div id="image-wrapper" class="relative">
            <template v-if="!dataSources.length">
              <div class="flex items-center justify-center mt-4 text-center text-neutral-300">
                <SvgIcon icon="ri:bubble-chart-fill" class="mr-2 text-3xl" />
                <span>{{ t('chat.newChatTitle') }}</span>
              </div>
            </template>
            <template v-else>
              <div>
                <Message
                  v-for="(item, index) of dataSources"
                  :key="index"
                  :date-time="item.dateTime"
                  :text="item.text"
                  :inversion="item.inversion"
                  :error="item.error"
                  :loading="item.loading"
                  @regenerate="onRegenerate(index)"
                  @delete="handleDelete(index)"
                />
                <div class="sticky bottom-0 left-0 flex justify-center">
                  <NButton v-if="loading" type="warning" @click="handleStop">
                    <template #icon>
                      <SvgIcon icon="ri:stop-circle-line" />
                    </template>
                    {{ t('common.stopResponding') }}
                  </NButton>
                </div>
              </div>
            </template>
          </div>
        </div>
      </div>
    </main>
    <footer :class="footerClass">
      <div class="w-full max-w-screen-xl m-auto">
        <div class="flex items-center justify-between mb-2 px-1">
             <div class="flex items-center gap-2 text-xs text-gray-500">
                <SvgIcon icon="ri:user-settings-line" />
                <span class="font-bold">Current Role:</span>
                <span class="bg-gray-100 dark:bg-gray-800 px-2 py-1 rounded border border-gray-200 dark:border-gray-700 max-w-[200px] truncate" :title="settingStore.systemMessage">
                    {{ currentRoleLabel }}
                </span>
            </div>
        </div>
        <div class="flex items-center justify-between space-x-2">
          <HoverButton v-if="!isMobile" @click="handleClear">
            <span class="text-xl text-[#4f555e] dark:text-white">
              <SvgIcon icon="ri:delete-bin-line" />
            </span>
          </HoverButton>
          <HoverButton v-if="!isMobile" @click="handleExport">
            <span class="text-xl text-[#4f555e] dark:text-white">
              <SvgIcon icon="ri:download-2-line" />
            </span>
          </HoverButton>
          <HoverButton @click="handleRefresh" :title="t('common.refresh') || 'Refresh'">
            <span class="text-xl text-[#4f555e] dark:text-white">
              <SvgIcon icon="ri:refresh-line" />
            </span>
          </HoverButton>
          <HoverButton @click="toggleUsingContext">
            <span class="text-xl" :class="{ 'text-[#4b9e5f]': usingContext, 'text-[#a8071a]': !usingContext }">
              <SvgIcon icon="ri:chat-history-line" />
            </span>
          </HoverButton>
          <HoverButton @click="toggleThinkingMode" :title="(thinkingEnabled ? 'Thinking: On' : 'Thinking: Off')">
            <span class="text-xl" :class="{ 'text-[#4b9e5f]': thinkingEnabled, 'text-[#a8071a]': !thinkingEnabled }">
              <SvgIcon icon="ri:brain-line" />
            </span>
          </HoverButton>
          <HoverButton @click="toggleWebSearchMode" :title="(webSearchEnabled ? 'Web Search: On' : 'Web Search: Off')">
            <span class="text-xl" :class="{ 'text-[#4b9e5f]': webSearchEnabled, 'text-[#a8071a]': !webSearchEnabled }">
              <SvgIcon icon="ri:search-line" />
            </span>
          </HoverButton>
          <NAutoComplete v-model:value="prompt" :options="searchOptions" :render-label="renderOption" @select="handleAutoCompleteSelect">
            <template #default="{ handleInput, handleBlur, handleFocus }">
              <div class="relative w-full">
                <!-- Variable Indicator -->
                <div v-if="attachedVariables.length > 0" class="absolute bottom-full left-0 mb-2 px-1 z-10 flex gap-2 flex-wrap">
                  <NTag 
                    v-for="v in attachedVariables"
                    :key="v"
                    closable 
                    round 
                    type="info" 
                    size="small" 
                    @close="removeVariable(v)"
                  >
                    {{ v }}
                  </NTag>
                </div>
                <NInput
                  ref="inputRef"
                  v-model:value="prompt"
                  type="textarea"
                  :placeholder="placeholder"
                  :autosize="{ minRows: 1, maxRows: isMobile ? 4 : 8 }"
                  @input="handleInput"
                  @focus="handleFocus"
                  @blur="handleBlur"
                  @keypress="handleEnter"
                />
              </div>
            </template>
          </NAutoComplete>
          <NButton type="primary" :disabled="buttonDisabled" @click="handleSubmit">
            <template #icon>
              <span class="dark:text-black">
                <SvgIcon icon="ri:send-plane-fill" />
              </span>
            </template>
          </NButton>
        </div>
      </div>
    </footer>
  </div>
</template>
