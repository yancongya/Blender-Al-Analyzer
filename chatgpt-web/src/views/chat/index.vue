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
import { fetchBlenderData, fetchChatAPIProcess, fetchUiConfig, triggerRefresh, updateSettings as apiUpdateSettings, fetchPromptTemplates } from '@/api'
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

// 输出详细程度相关
const outputDetailLevel = computed({
  get() {
    return settingStore.outputDetailLevel || 'medium'
  },
  set(value: 'simple' | 'medium' | 'detailed') {
    settingStore.updateSetting({ outputDetailLevel: value })
  }
})

const outputDetailOptions = [
  { label: '简约', value: 'simple', description: '简要说明，无格式' },
  { label: '适中', value: 'medium', description: '常规回答，使用markdown' },
  { label: '详细', value: 'detailed', description: '详细说明，使用图表等' }
]

const outputDetailLevelIcon = computed(() => {
  const iconMap: Record<string, string> = {
    'simple': 'ri:layout-bottom-line', // 简约模式使用底部布局图标
    'medium': 'ri:layout-column-line', // 适中模式使用列布局图标
    'detailed': 'ri:layout-3-line' // 详细模式使用三列布局图标
  }
  return iconMap[outputDetailLevel.value] || 'ri:layout-bottom-line'
})

function cycleOutputDetailLevel() {
  const levels: Array<'simple' | 'medium' | 'detailed'> = ['simple', 'medium', 'detailed']
  const currentIndex = levels.indexOf(outputDetailLevel.value)
  const nextIndex = (currentIndex + 1) % levels.length
  outputDetailLevel.value = levels[nextIndex]

  // 显示切换提示
  const levelLabels = { 'simple': '简约', 'medium': '适中', 'detailed': '详细' }
  ms.info(`已切换到${levelLabels[outputDetailLevel.value]}模式`)
}
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

  // 加载提示词模板
  try {
    const res = await fetchPromptTemplates()
    if (res.data && Array.isArray(res.data)) {
      // 确保数据符合PromptItem类型
      const templates = res.data.map(item => ({
        ...item,
        createdAt: item.createdAt || Date.now()
      }))
      // 更新store，这将触发本地存储和后端同步
      await promptStore.updatePromptList(templates)
    }
  } catch (error) {
    console.error('Failed to load prompt templates', error)
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
  // 监听刷新请求
  window.addEventListener('refresh-request', handleRefreshRequest)
  // 监听配置更新
  window.addEventListener('config-updated', handleConfigUpdate)
  // 监听角色切换事件
  window.addEventListener('roleChanged', handleRoleChanged)
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
  // 移除事件监听器
  window.removeEventListener('openSettingFromAvatar', handleOpenSettingFromAvatar)
  window.removeEventListener('refresh-request', handleRefreshRequest)
  window.removeEventListener('config-updated', handleConfigUpdate)
  window.removeEventListener('roleChanged', handleRoleChanged)
})

// 添加事件监听器
window.addEventListener('openSettingFromAvatar', handleOpenSettingFromAvatar as EventListener)

// 处理角色切换事件
function handleRoleChanged(event: Event) {
  const customEvent = event as CustomEvent
  const { message, roleLabel } = customEvent.detail

  // 添加用户消息到聊天
  const userMessage = {
    dateTime: new Date().toLocaleString(),
    text: message,
    inversion: true,
    error: false,
    loading: false,
    conversationOptions: null,
    requestOptions: { prompt: message, options: null },
  }
  addChat(+uuid, userMessage)

  // 发送消息到AI
  // 临时存储原始提示
  const originalPrompt = prompt.value
  prompt.value = message
  setTimeout(() => {
    onConversation().then(() => {
      // 恢复原始提示
      prompt.value = originalPrompt
    })
  }, 0)

  ms.success(`Role switched to: ${roleLabel}`)
}

function handleRefreshRequest(event: Event) {
  // 处理刷新请求
  console.log('Received refresh request', event)
  // 这里可以添加刷新逻辑
}

function handleConfigUpdate(event: Event) {
  // 处理配置更新
  console.log('Received config update', event)
  // 这里可以添加配置更新逻辑
}

function handleOpenSettingFromAvatar(event: Event) {
  const customEvent = event as CustomEvent
  // 由于设置面板在侧边栏，我们需要通过某种方式打开它
  // 但当前没有直接访问侧边栏设置面板的引用
  // 可能需要通过全局状态或事件总线来实现
  console.log('Open setting from avatar click:', customEvent.detail.tab)
  // 这里需要实现打开设置面板的逻辑
  // 直接触发事件，不需要弹窗
}

// 添加PromptStore
const promptStore = usePromptStore()

// 使用getter以避免类型问题
const promptTemplate = computed<any[]>(() => promptStore.getPromptList().promptList)

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

  // Add output detail level instruction to the message
  const outputDetailInstruction = settingStore.outputDetailPresets[outputDetailLevel.value]
  if (outputDetailInstruction && !message.includes(outputDetailInstruction)) {
    message = `${message}\n\n${outputDetailInstruction}`
  }

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

    // 1. Existing Prompts (Store) - now loaded from config file
    const storePrompts = promptTemplate.value.filter((item: { key: string }) =>
      item.key.toLowerCase().includes(prompt.value.substring(1).toLowerCase())
    ).map((obj: { key: string; value: string }) => {
      return {
        label: obj.key,  // Use key as label (the prompt title)
        value: obj.value, // Use value as value (the prompt content)
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

async function handleAutoCompleteSelect(value: string) {
    if (value.startsWith('__SYSTEM_PROMPT:')) {
        const content = value.replace('__SYSTEM_PROMPT:', '').replace('__', '')
        settingStore.updateSetting({ systemMessage: content })

        // Send a confirmation message to ensure AI uses the new role
        const roleLabel = settingStore.systemMessagePresets?.find(p => p.value === content)?.label || 'New Role'
        const confirmationMessage = `I've switched to the role of "${roleLabel}". Please respond according to this new role: ${content}`;

        // Set the confirmation message as the prompt
        prompt.value = confirmationMessage;

        // Trigger the conversation with the confirmation message
        await onConversation();

        ms.success(`Role switched to: ${roleLabel}`)

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
        // For normal prompt templates, find the matching prompt from the store
        const matchingPrompt = promptTemplate.value.find((item: any) => item.value === value)
        if (matchingPrompt) {
            // Set the prompt to the value of the matching prompt (the actual prompt text)
            setTimeout(() => {
                prompt.value = matchingPrompt.value
            }, 0)
        }
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

  // Check if this is a prompt template from the store
  for (const i of promptTemplate.value) {
    if (i.value === option.value) {
      return h('div', { class: 'flex items-center justify-between gap-2' }, [
        h('span', {}, i.key), // Display the prompt title
        h(NTag, { type: 'info', size: 'small', bordered: false }, { default: () => 'Prompt' })
      ])
    }
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

function getNodeTypeName(nodeType: string): string {
  switch(nodeType) {
    case 'Geometry Nodes':
      return t('chat.geometryNodes')
    case 'Shader Nodes':
      return t('chat.shaderNodes')
    case 'Compositor Nodes':
      return t('chat.compositorNodes')
    case 'World Nodes':
      return t('chat.worldNodes')
    default:
      return nodeType
  }
}

function getNodeTagType(nodeType: string): 'success' | 'warning' | 'info' | 'primary' | 'default' {
  switch(nodeType) {
    case 'Geometry Nodes':
      return 'success' // 绿色
    case 'Shader Nodes':
      return 'warning' // 黄色
    case 'Compositor Nodes':
      return 'info' // 蓝色
    case 'World Nodes':
      return 'primary' // 紫色
    default:
      return 'default' // 灰色
  }
}

function getNodeCount(): number {
  if (!processedNodeData.value.nodes) return 0
  try {
    const data = JSON.parse(processedNodeData.value.nodes)
    // 检查是否包含selected_nodes或nodes数组
    if (data.selected_nodes && Array.isArray(data.selected_nodes)) {
      return data.selected_nodes.length
    } else if (data.nodes && Array.isArray(data.nodes)) {
      return data.nodes.length
    }
    return 0
  } catch (e) {
    // 如果解析失败，尝试简单计算节点数量
    const matches = processedNodeData.value.nodes.match(/"type":\s*"/g)
    return matches ? matches.length : 0
  }
}

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
      <div class="flex items-center justify-between w-full">
        <div class="flex items-center gap-2">
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

        </div>

        <div class="flex items-center gap-2">
          <!-- Refresh Button -->
          <NButton size="tiny" quaternary circle @click="handleRefresh">
            <template #icon>
              <SvgIcon icon="ri:refresh-line" />
            </template>
          </NButton>

          <!-- Status Badge - now shows node type, count and tokens -->
          <NTag
            v-if="processedNodeData.nodes"
            :type="getNodeTagType(nodeData.node_type)"
            size="small"
            :bordered="false"
            class="cursor-pointer hover:opacity-80 transition select-none"
            @click="showNodeDataModal = true"
            :title="`${getNodeTypeName(nodeData.node_type)} | ${getNodeCount()} nodes | ${processedNodeData.tokens} tokens`"
          >
            {{ getNodeTypeName(nodeData.node_type) }} | {{ $t('chat.loaded') }} {{ getNodeCount() }} {{ $t('chat.nodes') }} | {{ processedNodeData.tokens }} {{ $t('chat.tokens') }}
          </NTag>
          <NTag
            v-else
            type="default"
            size="small"
            :bordered="false"
            class="cursor-pointer hover:opacity-80 transition select-none"
            @click="showNodeDataModal = true"
            :title="$t('chat.noNodeData')"
          >
            {{ $t('chat.noNodeData') }}
          </NTag>
          <div class="flex items-center gap-2 text-xs whitespace-nowrap overflow-hidden text-ellipsis">
            <span :class="thinkingEnabled ? 'text-green-600' : 'text-gray-500'">{{ $t('chat.thinkingEnabled', { status: thinkingEnabled ? $t('chat.thinkingOn') : $t('chat.thinkingOff') }) }}</span>
            <span v-if="currentConversationId" class="text-gray-500" :title="currentConversationId">{{ $t('chat.conversationId') }}: {{ currentConversationId.slice(0, 8) }}...</span>
            <span v-else class="text-gray-500">{{ $t('chat.conversationId') }}: -</span>
            <span class="text-gray-500">{{ $t('chat.rounds') }}: {{ currentRounds }}</span>
          </div>
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

          <!-- Output Detail Level -->
          <div class="border rounded p-2 dark:border-gray-700">
             <div class="flex justify-between items-center mb-1">
                 <div class="font-bold text-purple-600 dark:text-purple-400">{{ $t('setting.outputDetailLevel') }}</div>
                 <NButton size="tiny" quaternary circle @click="handleCopy(settingStore.outputDetailPresets[outputDetailLevel])">
                    <template #icon><SvgIcon icon="ri:file-copy-2-line" /></template>
                 </NButton>
             </div>
             <div class="whitespace-pre-wrap bg-gray-50 dark:bg-gray-900 p-2 rounded text-gray-600 dark:text-gray-400">
               {{ outputDetailOptions.find(opt => opt.value === outputDetailLevel)?.label }}: {{ settingStore.outputDetailPresets[outputDetailLevel] }}
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
                  :role="item.inversion ? 'User' : currentRoleLabel"
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
          <!-- Output Detail Level Selector - Click to cycle -->
          <HoverButton @click="cycleOutputDetailLevel" :title="`输出详细程度: ${outputDetailOptions.find(opt => opt.value === outputDetailLevel)?.label}`">
            <span class="text-xl text-[#4f555e] dark:text-white">
              <SvgIcon :icon="outputDetailLevelIcon" />
            </span>
          </HoverButton>
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
