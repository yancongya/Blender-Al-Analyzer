<script lang="ts" setup>
import { computed, onMounted, onUnmounted, onUpdated, ref } from 'vue'
import { NButton, NModal, NCard } from 'naive-ui'
import MarkdownIt from 'markdown-it'
import MdKatex from '@vscode/markdown-it-katex'
import MdLinkAttributes from 'markdown-it-link-attributes'
import MdMermaid from 'mermaid-it-markdown'
import hljs from 'highlight.js'
import { useBasicLayout } from '@/hooks/useBasicLayout'
import { t } from '@/locales'
import { copyToClip } from '@/utils/copy'
import { useChatStore } from '@/store'

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
})

onUpdated(() => {
  addCopyEvents()
})

onUnmounted(() => {
  removeCopyEvents()
})
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
      <div ref="textRef" class="leading-relaxed break-words">
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
      </div>
    </div>
    
    <NModal v-model:show="showVariableModal">
      <NCard
        style="width: 600px; max-width: 90vw;"
        title="Node Data Variable Content"
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
</style>
