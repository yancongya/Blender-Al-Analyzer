<script setup lang="ts">
import { nextTick, onMounted, ref, watch } from 'vue'

interface Props {
  value: string
  placeholder?: string
  disabled?: boolean
}

const props = defineProps<Props>()
const emit = defineEmits(['update:value', 'input', 'focus', 'blur', 'keypress', 'keydown', 'drop'])

const editorRef = ref<HTMLElement | null>(null)
const internalValue = ref(props.value || '')
const isComposing = ref(false)
const lastSelectionAnchor = ref<Node | null>(null)

watch(() => props.value, async (v) => {
  if (v !== internalValue.value) {
    internalValue.value = v || ''
    await nextTick()
    renderEditor()
  }
})

function escapeHtml(text: string) {
  return text.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string))
}

function renderEditor() {
  const root = editorRef.value
  if (!root) return
  // Build DOM without relying on Vue's VDOM
  root.innerHTML = ''
  const str = internalValue.value || ''
  const parts = str.split(/({{Current Node Data}}|Current Node Data)/g).filter(p => p !== '')
  for (const p of parts) {
    if (p === '{{Current Node Data}}' || p === 'Current Node Data') {
      const chip = document.createElement('span')
      chip.dataset.var = 'CurrentNodeData'
      chip.contentEditable = 'false'
      chip.className = 'inline-flex items-center px-2 py-1 rounded-md bg-[#2c2f36] border border-[#3a3f48] mx-1 shadow-sm'
      chip.style.color = '#f1f5f9'
      const icon = document.createElement('span')
      icon.className = 'mr-1'
      icon.style.color = '#f1f5f9'
      // render icon via inline svg placeholder; keeps structure simple
      icon.innerHTML = '<svg aria-hidden="true" width="1em" height="1em" viewBox="0 0 24 24"><path fill="currentColor" d="M5.463 4.433A9.96 9.96 0 0 1 12 2c5.523 0 10 4.477 10 10c0 2.136-.67 4.116-1.81 5.74L17 12h3A8 8 0 0 0 6.46 6.228zm13.074 15.134A9.96 9.96 0 0 1 12 22C6.477 22 2 17.523 2 12c0-2.136.67-4.116 1.81-5.74L7 12H4a8 8 0 0 0 13.54 5.772z"></path></svg>'
      const label = document.createElement('span')
      label.className = 'text-xs font-semibold'
      label.style.color = '#f8fafc'
      label.textContent = 'Node Data'
      chip.appendChild(icon)
      chip.appendChild(label)
      root.appendChild(chip)
    } else {
      root.insertAdjacentHTML('beforeend', escapeHtml(p))
    }
  }
}

function toPlainString(root: HTMLElement): string {
  const clone = root.cloneNode(true) as HTMLElement
  const elements = clone.querySelectorAll('[data-var="CurrentNodeData"]')
  elements.forEach((el: Element) => {
    el.textContent = '{{Current Node Data}}'
  })
  return clone.textContent || ''
}

function handleInput() {
  if (!editorRef.value || isComposing.value) return
  const plain = toPlainString(editorRef.value as HTMLElement)
  internalValue.value = plain
  emit('update:value', plain)
  emit('input', plain)
}

onMounted(() => {
  renderEditor()
})

function handleFocus(e: FocusEvent) {
  emit('focus', e)
}
function handleBlur(e: FocusEvent) {
  emit('blur', e)
}
function handleKeypress(e: KeyboardEvent) {
  emit('keypress', e)
}
function handleKeydown(e: KeyboardEvent) {
  // Handle atomic deletion of variable chips
  if (!editorRef.value) {
    emit('keydown', e)
    return
  }
  const sel = window.getSelection?.()
  const isCollapsed = !!sel && sel.rangeCount > 0 && sel.isCollapsed
  const anchorNode = sel?.anchorNode || null
  lastSelectionAnchor.value = anchorNode

  const isChip = (el: Node | null) => {
    const he = el as HTMLElement | null
    return !!he && he.nodeType === Node.ELEMENT_NODE && (he as HTMLElement).dataset?.var === 'CurrentNodeData'
  }
  const removeNodeSafe = (el: Node | null) => {
    const he = el as HTMLElement | null
    if (!he || !he.parentNode) return
    he.parentNode.removeChild(he)
  }

  if (isCollapsed) {
    if (e.key === 'Backspace') {
      // If caret is at start of a text node, remove previous chip as a whole
      const node = anchorNode
      if (node) {
        if (node.nodeType === Node.TEXT_NODE) {
          const range = sel!.getRangeAt(0)
          if (range.startOffset === 0 && (node.parentNode as HTMLElement)?.firstChild) {
            const prev = (node.parentNode as HTMLElement).childNodes[Array.prototype.indexOf.call((node.parentNode as HTMLElement).childNodes, node) - 1] || null
            if (isChip(prev)) {
              e.preventDefault()
              removeNodeSafe(prev)
              handleInput()
              return
            }
          }
        } else if (node.nodeType === Node.ELEMENT_NODE) {
          // If caret is at element start, try previous sibling
          const el = node as HTMLElement
          const prev = el.previousSibling
          if (isChip(prev)) {
            e.preventDefault()
            removeNodeSafe(prev)
            handleInput()
            return
          }
        }
      }
    } else if (e.key === 'Delete') {
      // If caret is at end of a text node, remove next chip as a whole
      const node = anchorNode
      if (node) {
        if (node.nodeType === Node.TEXT_NODE) {
          const range = sel!.getRangeAt(0)
          if (range.startOffset === (node.textContent || '').length) {
            const next = (node.parentNode as HTMLElement)?.childNodes[Array.prototype.indexOf.call((node.parentNode as HTMLElement).childNodes, node) + 1] || null
            if (isChip(next)) {
              e.preventDefault()
              removeNodeSafe(next)
              handleInput()
              return
            }
          }
        } else if (node.nodeType === Node.ELEMENT_NODE) {
          const el = node as HTMLElement
          const next = el.nextSibling
          if (isChip(next)) {
            e.preventDefault()
            removeNodeSafe(next)
            handleInput()
            return
          }
        }
      }
    }
  }
  emit('keydown', e)
}
function handleDrop(e: DragEvent) {
  emit('drop', e)
}
function onCompositionStart() {
  isComposing.value = true
}
function onCompositionEnd() {
  isComposing.value = false
  handleInput()
}
</script>

<template>
  <div class="relative w-full">
    <div
      ref="editorRef"
      class="min-h-[40px] max-h-[200px] overflow-auto rounded border border-gray-300 dark:border-gray-700 bg-white dark:bg-[#101014] px-3 py-2 text-[14px] leading-6 outline-none"
      contenteditable="true"
      :aria-disabled="disabled ? 'true' : 'false'"
      :data-placeholder="placeholder || ''"
      @input="handleInput"
      @focus="handleFocus"
      @blur="handleBlur"
      @keypress="handleKeypress"
      @keydown="handleKeydown"
      @drop.prevent="handleDrop"
      @compositionstart="onCompositionStart"
      @compositionend="onCompositionEnd"
    />
    <div v-if="!internalValue" class="pointer-events-none absolute left-3 top-2 text-gray-400 text-[14px]">
      {{ placeholder || '' }}
    </div>
  </div>
</template>

<style scoped>
[contenteditable][aria-disabled="true"] {
  pointer-events: none;
}
</style>
