<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { debounce } from '@/utils/functions/debounce'
import { useMessage } from 'naive-ui'
import { sendSelectedTextToBlender } from '@/api'

const visible = ref(false)
const top = ref(0)
const left = ref(0)
const selectedText = ref('')
const message = useMessage()
let hideTimer: number | undefined

function updateFromSelection() {
  const sel = window.getSelection()
  if (!sel || sel.isCollapsed) {
    visible.value = false
    selectedText.value = ''
    return
  }
  const text = sel.toString().trim()
  if (!text) {
    visible.value = false
    selectedText.value = ''
    return
  }
  let rect: DOMRect | null = null
  try {
    const range = sel.getRangeAt(0)
    rect = range.getBoundingClientRect()
  }
  catch {
    rect = null
  }
  const offset = 12
  const scrollY = window.scrollY || document.documentElement.scrollTop || 0
  const scrollX = window.scrollX || document.documentElement.scrollLeft || 0
  if (rect) {
    top.value = rect.top + scrollY
    left.value = rect.left + scrollX + rect.width / 2
  }
  else {
    top.value = scrollY + offset
    left.value = scrollX + offset
  }
  selectedText.value = text
  visible.value = true
  if (hideTimer) window.clearTimeout(hideTimer)
  hideTimer = window.setTimeout(() => { visible.value = false }, 3500)
}

const handleSelectionChange = debounce(updateFromSelection, 150)
const handleMouseUp = debounce(updateFromSelection, 100)
const handleKeyUp = debounce(updateFromSelection, 100)

function hide() {
  visible.value = false
  if (hideTimer) window.clearTimeout(hideTimer)
}

async function send() {
  if (!selectedText.value.trim()) {
    return
  }
  try {
    await sendSelectedTextToBlender(selectedText.value)
    message.success('已发送到 Blender')
  }
  catch (e) {
    message.error('发送失败')
  }
  finally {
    hide()
    const sel = window.getSelection()
    sel?.removeAllRanges()
  }
}

onMounted(() => {
  document.addEventListener('selectionchange', handleSelectionChange)
  document.addEventListener('mouseup', handleMouseUp)
  document.addEventListener('keyup', handleKeyUp)
  window.addEventListener('scroll', hide, { passive: true })
  window.addEventListener('resize', hide)
})

onBeforeUnmount(() => {
  document.removeEventListener('selectionchange', handleSelectionChange)
  document.removeEventListener('mouseup', handleMouseUp)
  document.removeEventListener('keyup', handleKeyUp)
  window.removeEventListener('scroll', hide)
  window.removeEventListener('resize', hide)
})
</script>

<template>
  <div
    v-show="visible"
    class="selection-send"
    :style="{ top: `${top}px`, left: `${left}px` }"
    @mouseenter="() => hideTimer && window.clearTimeout(hideTimer)"
    @mouseleave="() => { if (visible) hideTimer = window.setTimeout(() => { visible = false }, 2000) }"
  >
    <button class="send-pill" @click="send" aria-label="发送到Blender">
      <svg class="icon" viewBox="0 0 24 24" width="16" height="16">
        <path d="M2 21l21-9-21-9v7l15 2-15 2v7z" fill="currentColor"></path>
      </svg>
      <span class="label">发送到Blender</span>
    </button>
  </div>
>
</template>

<style scoped>
.selection-send {
  position: fixed;
  z-index: 2000;
  transform: translate(-50%, calc(-100% - 12px));
  pointer-events: auto;
  opacity: 0;
  animation: pop 120ms ease-out forwards;
}
.selection-send::after {
  content: '';
  position: absolute;
  left: 50%;
  bottom: -6px;
  transform: translateX(-50%);
  width: 0;
  height: 0;
  border-left: 6px solid transparent;
  border-right: 6px solid transparent;
  border-top: 6px solid rgba(30, 30, 30, 0.92);
}
.send-pill {
  border: none;
  outline: none;
  background: rgba(30, 30, 30, 0.92);
  color: #fff;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  padding: 8px 12px;
  border-radius: 999px;
  cursor: pointer;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.25);
  backdrop-filter: saturate(180%) blur(8px);
  transition: transform 120ms ease-out, background 120ms ease-out;
}
.send-pill:hover {
  transform: translateY(-1px);
  background: rgba(34, 34, 34, 0.96);
}
.icon {
  display: inline-block;
  color: #18a058;
}
.label {
  white-space: nowrap;
}
@keyframes pop {
  from { opacity: 0; transform: translate(-50%, calc(-100% - 16px)) scale(0.98); }
  to { opacity: 1; transform: translate(-50%, calc(-100% - 12px)) scale(1); }
}
</style>
