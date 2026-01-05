<script lang="ts" setup>
import { computed, onMounted, onUnmounted, onUpdated, ref } from 'vue'
import { NButton, NModal, NCard, useMessage } from 'naive-ui'
import MarkdownIt from 'markdown-it'
import MdKatex from '@vscode/markdown-it-katex'
import MdLinkAttributes from 'markdown-it-link-attributes'
import MdMermaid from 'mermaid-it-markdown'
import hljs from 'highlight.js'
import { useBasicLayout } from '@/hooks/useBasicLayout'
import { t } from '@/locales'
import { copyToClip } from '@/utils/copy'
import { useChatStore } from '@/store'
import { sendSelectionToBlender, triggerRefresh } from '@/api'
import { stripMarkdown } from '@/utils/functions'

interface Props {
  inversion?: boolean
  error?: boolean
  text?: string
  loading?: boolean
  asRawText?: boolean
}

const props = defineProps<Props>()

const { isMobile } = useBasicLayout()
const chatStore = useChatStore()

const textRef = ref<HTMLElement>()
const isExpanded = ref(false)
const showThinking = ref(false)
const showVariableModal = ref(false)
const ms = useMessage()
const hoverRect = ref<{ left: number; top: number; width: number; height: number; visible: boolean }>({ left: 0, top: 0, width: 0, height: 0, visible: false })
const hoverText = ref('')
let candidates: HTMLElement[] = []

const textParts = computed(() => {
  if (!props.text) return []
  if (!props.inversion) return [] // Only for user messages
  
  // Split by regex to capture both {{Current Node Data}} and Current Node Data
  // We use a capturing group so the separator is included in the result array
  const parts = props.text.split(/({{Current Node Data}}|Current Node Data)/g)
  const result = []
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i]
    if (!part) continue
    
    if (part === '{{Current Node Data}}' || part === 'Current Node Data') {
      result.push({ text: part, isVariable: true })
    } else {
      result.push({ text: part, isVariable: false })
    }
  }
  return result
})

const mdi = new MarkdownIt({
  html: false,
  linkify: true,
  highlight(code, language) {
    const validLang = !!(language && hljs.getLanguage(language))
    if (validLang) {
      const lang = language ?? ''
      return highlightBlock(hljs.highlight(code, { language: lang }).value, lang)
    }
    return highlightBlock(hljs.highlightAuto(code).value, '')
  },
})

mdi.use(MdLinkAttributes, { attrs: { target: '_blank', rel: 'noopener' } }).use(MdKatex).use(MdMermaid)

const wrapClass = computed(() => {
  return [
    'text-wrap',
    'min-w-[20px]',
    'rounded-md',
    isMobile.value ? 'p-2' : 'px-3 py-2',
    props.inversion ? 'bg-[#d2f9d1]' : 'bg-[#f4f6f8]',
    props.inversion ? 'dark:bg-[#a1dc95]' : 'dark:bg-[#1e1e20]',
    props.inversion ? 'message-request' : 'message-reply',
    { 'text-red-500': props.error },
  ]
})

const hasThinking = computed(() => {
  const value = props.text ?? ''
  return !props.inversion && value.includes('【思维链】\n') && value.includes('\n<<END_THINKING>>\n')
})

const thinkingContent = computed(() => {
  if (!hasThinking.value) return ''
  const value = props.text ?? ''
  const prefixLen = '【思维链】\n'.length
  const sepIndex = value.indexOf('\n<<END_THINKING>>\n', prefixLen)
  if (sepIndex !== -1) {
    return value.substring(prefixLen, sepIndex)
  }
  return value.substring(prefixLen)
})

const answerContent = computed(() => {
  if (!hasThinking.value) return props.text ?? ''
  const value = props.text ?? ''
  const sepIndex = value.indexOf('\n<<END_THINKING>>\n')
  if (sepIndex !== -1) {
    return value.substring(sepIndex + '\n<<END_THINKING>>\n'.length)
  }
  return ''
})

const needsCollapse = computed(() => {
  const value = answerContent.value ?? ''
  return value.length > 500
})

const renderedAnswer = computed(() => {
  const value = answerContent.value
  if (!props.asRawText) {
    const escapedText = escapeBrackets(escapeDollarNumber(value))
    return mdi.render(escapedText)
  }
  return value
})

function highlightBlock(str: string, lang?: string) {
  return `<pre class="code-block-wrapper"><div class="code-block-header"><span class="code-block-header__lang">${lang}</span><span class="code-block-header__copy">${t('chat.copyCode')}</span></div><code class="hljs code-block-body ${lang}">${str}</code></pre>`
}

function addCopyEvents() {
  if (textRef.value) {
    const copyBtn = textRef.value.querySelectorAll('.code-block-header__copy')
    copyBtn.forEach((btn) => {
      btn.addEventListener('click', () => {
        const code = btn.parentElement?.nextElementSibling?.textContent
        if (code) {
          copyToClip(code).then(() => {
            btn.textContent = t('chat.copied')
            setTimeout(() => {
              btn.textContent = t('chat.copyCode')
            }, 1000)
          })
        }
      })
    })
  }
}

function removeCopyEvents() {
  if (textRef.value) {
    const copyBtn = textRef.value.querySelectorAll('.code-block-header__copy')
    copyBtn.forEach((btn) => {
      btn.removeEventListener('click', () => { })
    })
  }
}

function escapeDollarNumber(text: string) {
  let escapedText = ''

  for (let i = 0; i < text.length; i += 1) {
    let char = text[i]
    const nextChar = text[i + 1] || ' '

    if (char === '$' && nextChar >= '0' && nextChar <= '9')
      char = '\\$'

    escapedText += char
  }

  return escapedText
}

function escapeBrackets(text: string) {
  const pattern = /(```[\s\S]*?```|`.*?`)|\\\[([\s\S]*?[^\\])\\\]|\\\((.*?)\\\)/g
  return text.replace(pattern, (match, codeBlock, squareBracket, roundBracket) => {
    if (codeBlock)
      return codeBlock
    else if (squareBracket)
      return `$$${squareBracket}$$`
    else if (roundBracket)
      return `$${roundBracket}$`
    return match
  })
}

onMounted(() => {
  addCopyEvents()
  updateCandidates()
})

onUpdated(() => {
  addCopyEvents()
  updateCandidates()
})

onUnmounted(() => {
  removeCopyEvents()
})

async function onContextMenuSend() {
  let content = ''
  const sel = window.getSelection?.()
  const selected = sel ? String(sel.toString()).trim() : ''
  content = selected || (props.text || '')
  content = stripMarkdown(content)
  if (!content) return
  try {
    const res = await sendSelectionToBlender(content)
    if ((res as any)?.status === 'Success') {
      ms.success(t('chat.sendSuccess'))
      await triggerRefresh()
    } else {
      ms.error(t('chat.sendFailed'))
    }
  } catch {
    ms.error(t('chat.sendFailed'))
  }
}

async function onContextMenuSendFromHover() {
  let content = hoverText.value || ''
  content = stripMarkdown(content)
  if (!content.trim()) {
    await onContextMenuSend()
    return
  }
  try {
    const res = await sendSelectionToBlender(content)
    if ((res as any)?.status === 'Success') {
      ms.success(t('chat.sendSuccess'))
      await triggerRefresh()
    } else {
      ms.error(t('chat.sendFailed'))
    }
  } catch {
    ms.error(t('chat.sendFailed'))
  }
}
function updateCandidates() {
  candidates = []
  if (!textRef.value) return
  const root = textRef.value
  const nodes = root.querySelectorAll('p, li, pre, blockquote, h1, h2, h3, h4, h5, h6')
  nodes.forEach(n => candidates.push(n as HTMLElement))
}

function onMouseMove(e: MouseEvent) {
  if (!textRef.value) return
  const rootRect = textRef.value.getBoundingClientRect()
  const x = e.clientX
  const y = e.clientY
  let targetEl: HTMLElement | null = null
  for (const el of candidates) {
    const r = el.getBoundingClientRect()
    if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) {
      targetEl = el
      break
    }
  }
  if (targetEl) {
    const r = targetEl.getBoundingClientRect()
    hoverRect.value = {
      left: r.left - rootRect.left,
      top: r.top - rootRect.top,
      width: r.width,
      height: r.height,
      visible: true,
    }
    hoverText.value = targetEl.innerText || ''
  } else {
    hoverRect.value.visible = false
    hoverText.value = ''
  }
}

function onMouseLeave() {
  hoverRect.value.visible = false
  hoverText.value = ''
}
</script>

<template>
  <div class="text-black">
    <div v-if="!inversion && hasThinking" class="mb-2 rounded border border-neutral-200 dark:border-neutral-700">
      <div class="flex items-center justify-between px-3 py-2 bg-neutral-100 dark:bg-neutral-800">
        <span class="font-semibold">【思维链】</span>
        <NButton size="tiny" text type="primary" @click="showThinking = !showThinking">
          {{ showThinking ? $t('common.collapse') : $t('common.expand') }}
        </NButton>
      </div>
      <div v-show="showThinking" class="px-3 py-2 font-mono text-xs whitespace-pre-wrap text-neutral-700 dark:text-neutral-300">
        {{ thinkingContent }}
      </div>
    </div>

    <div :class="wrapClass">
      <div
        ref="textRef"
        class="leading-relaxed break-words relative"
        @contextmenu.prevent="onContextMenuSendFromHover"
        @mousemove="onMouseMove"
        @mouseleave="onMouseLeave"
      >
        <div :class="{ 'max-h-[300px] overflow-hidden relative': !isExpanded && needsCollapse && !inversion }">
          <div v-if="!inversion">
            <div v-if="!asRawText" class="markdown-body" :class="{ 'markdown-body-generate': loading }" v-html="renderedAnswer" />
            <div v-else class="whitespace-pre-wrap" v-text="renderedAnswer" />
          </div>
          <div v-else class="whitespace-pre-wrap">
            <template v-if="textParts.length > 0">
               <span v-for="(part, idx) in textParts" :key="idx">
                 <span v-if="part.isVariable" 
                       class="font-bold text-blue-600 dark:text-blue-400 cursor-pointer hover:underline mx-1"
                       @click.stop="showVariableModal = true"
                       title="Click to view node data"
                 >
                   {{ part.text }}
                 </span>
                 <span v-else class="whitespace-pre-wrap">{{ part.text }}</span>
               </span>
            </template>
            <template v-else>
               {{ props.text }}
            </template>
          </div>

          <div v-if="!isExpanded && needsCollapse && !inversion" class="absolute bottom-0 w-full h-10 bg-gradient-to-t from-neutral-100 dark:from-[#1e1e20] to-transparent pointer-events-none" />
        </div>

        <div v-if="needsCollapse && !inversion" class="mt-2 text-center">
          <NButton size="tiny" text type="primary" @click="isExpanded = !isExpanded">
            {{ isExpanded ? $t('common.collapse') : $t('common.expand') }}
          </NButton>
        </div>
        <div
          v-if="hoverRect.visible"
          class="pointer-events-none absolute ants-overlay"
          :style="{
            left: hoverRect.left + 'px',
            top: hoverRect.top + 'px',
            width: hoverRect.width + 'px',
            height: hoverRect.height + 'px',
            borderRadius: '6px'
          }"
        />
      </div>
    </div>
    
    
    <NModal v-model:show="showVariableModal">
      <NCard
        style="width: 600px; max-width: 90vw;"
        :title="$t('chat.nodeDataVariableContent')"
        :bordered="false"
        size="huge"
        role="dialog"
        aria-modal="true"
      >
         <div class="mb-2 text-xs text-gray-500">
            Source: {{ chatStore.nodeData?.filename || 'Unknown' }}
            <span v-if="chatStore.nodeData?.tokens">({{ chatStore.nodeData.tokens }} tokens)</span>
         </div>
         <div class="max-h-[60vh] overflow-y-auto font-mono text-xs whitespace-pre-wrap bg-gray-50 dark:bg-gray-900 p-3 rounded">
           {{ chatStore.nodeData?.nodes || 'No data available.' }}
         </div>
      </NCard>
    </NModal>
  </div>
</template>

<style lang="less">
@import url(./style.less);
.ants-overlay {
  pointer-events: none;
}
.ants-overlay::before {
  content: '';
  position: absolute;
  inset: 0;
  padding: 1px;
  border-radius: inherit;
  background:
    linear-gradient(90deg, rgba(59,130,246,0.9) 50%, transparent 0) 0 0 / 12px 2px repeat-x,
    linear-gradient(90deg, rgba(59,130,246,0.9) 50%, transparent 0) 0 100% / 12px 2px repeat-x,
    linear-gradient(0deg,  rgba(59,130,246,0.9) 50%, transparent 0) 0 0 / 2px 12px repeat-y,
    linear-gradient(0deg,  rgba(59,130,246,0.9) 50%, transparent 0) 100% 0 / 2px 12px repeat-y;
  background-position: 0 0, 0 100%, 0 0, 100% 0;
  animation: ants 0.6s steps(12) infinite;
  -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
  -webkit-mask-composite: xor;
  mask-composite: exclude;
}
@keyframes ants {
  to {
    background-position:
      12px 0, -12px 100%, 0 12px, 100% -12px;
  }
}
</style>
