<script setup lang="ts">
import { computed } from 'vue'
import { Handle, Position } from '@vue-flow/core'
import { useMessage } from 'naive-ui'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  data: {
    label: string
    label_localized?: string
    inputs: any[]
    outputs: any[]
    width?: number
    detailLevel: number // 0=UltraLite, 1=Lite, 2=Standard, 3=Full
    raw?: any
  }
}>()
const emit = defineEmits<{
  (e: 'hover', payload: { raw: any, x: number, y: number }): void
  (e: 'move', payload: { x: number, y: number }): void
  (e: 'leave'): void
}>()

const minWidth = computed(() => Math.max(140, props.data.width || 140))

type Socket = {
  name: string
  name_localized?: string
  type: string
  identifier?: string
  enabled?: boolean
  is_connected?: boolean
}
type SocketGroup = {
  base: string
  primary: Socket
  all: Socket[]
}

// Function to determine handle color based on socket type
function getSocketColor(type: string) {
    const typeLower = (type || '').toLowerCase()
    if (typeLower.includes('vector')) return '#6366f1' // Indigo
    if (typeLower.includes('color')) return '#eab308' // Yellow
    if (typeLower.includes('shader')) return '#22c55e' // Green
    if (typeLower.includes('float') || typeLower.includes('value')) return '#9ca3af' // Gray
    return '#a855f7' // Purple default
}

// 0: UltraLite -> Connected Only
// 1: Lite -> Connected Only (Logic focus)
// 2: Standard -> Connected Only (Default behavior in current code, but let's make it ALL for Standard/Full to match "Full mode shows all")
// User said: "Current view only has two gears (connected only), should allow Full mode to show all"

const filteredInputs = computed(() => {
    const level = props.data.detailLevel ?? 2
    const sockets = props.data.inputs || []
    if (level >= 3) return sockets
    if (level >= 2) return sockets.filter((s: any) => s.enabled !== false)
    return sockets.filter((s: any) => (s.enabled !== false) && s.is_connected)
})

const filteredOutputs = computed(() => {
    const level = props.data.detailLevel ?? 2
    const sockets = props.data.outputs || []
    if (level >= 3) return sockets
    if (level >= 2) return sockets.filter((s: any) => s.enabled !== false)
    return sockets.filter((s: any) => (s.enabled !== false) && s.is_connected)
})

function baseKey(s: any) {
    const id = s?.identifier || s?.name || ''
    const idx = id.indexOf('_')
    return idx > 0 ? id.slice(0, idx) : id
}
function groupByBase(sockets: any[]) {
    const map: Record<string, any[]> = {}
    sockets.forEach((s) => {
        const k = baseKey(s)
        if (!map[k]) map[k] = []
        map[k].push(s)
    })
    return Object.entries(map).map(([k, arr]) => {
        const primary = (arr as Socket[]).find((x) => x.enabled !== false) || (arr as Socket[])[0]
        return { base: k, primary, all: arr as Socket[] } as SocketGroup
    }) as SocketGroup[]
}
const useGrouped = computed<boolean>(() => (props.data.detailLevel ?? 2) >= 2)
const inputGroups = computed<SocketGroup[]>(() => groupByBase(filteredInputs.value as Socket[]))
const outputGroups = computed<SocketGroup[]>(() => groupByBase(filteredOutputs.value as Socket[]))
const message = useMessage()
const { t } = useI18n()
const jsonText = computed(() => {
    const payload = props.data.raw || {
        name: props.data.label,
        inputs: props.data.inputs,
        outputs: props.data.outputs
    }
    try {
        return JSON.stringify(payload, null, 2)
    } catch {
        return ''
    }
})
function copyJson() {
    if (!jsonText.value) return
    navigator.clipboard.writeText(jsonText.value)
        .then(() => message.success(t('chat.copied')))
        .catch(() => message.error(t('chat.copyFailed')))
}
</script>

<template>
  <div 
    class="blender-node bg-[#2d2d2d] border border-gray-600 rounded shadow-xl overflow-hidden text-xs font-sans transition-colors duration-150 hover:border-purple-500 hover:shadow-lg"
    :style="{ minWidth: `${minWidth}px` }"
    @contextmenu.prevent="copyJson"
    @mouseenter="(e) => emit('hover', { raw: data.raw || data, x: (e as MouseEvent).clientX, y: (e as MouseEvent).clientY })"
    @mousemove="(e) => emit('move', { x: (e as MouseEvent).clientX, y: (e as MouseEvent).clientY })"
    @mouseleave="emit('leave')"
  >
    <!-- Header -->
    <div class="px-3 py-1 bg-black/40 border-b border-gray-700 font-bold text-gray-200">
      {{ data.label_localized || data.label }}
    </div>

    <!-- Body -->
    <div class="p-2 space-y-1 relative">
      <div class="flex flex-col gap-1 select-none">
        <!-- Inputs -->
        <div v-if="!useGrouped" v-for="(input, i) in filteredInputs" :key="`in-${i}-${input.name}`" class="relative flex items-center h-5">
            <Handle
                :id="input.name"
                type="target"
                :position="Position.Left"
                class="!w-2.5 !h-2.5 !bg-[#a855f7] !border-none"
                :style="{ top: '50%', background: getSocketColor(input.type) }"
            />
            <span class="ml-3 text-gray-400">{{ input.name_localized || input.name }}</span>
        </div>
        <div v-else v-for="(group, i) in inputGroups" :key="`in-${i}-${group.base}`" class="relative flex items-center h-5">
            <Handle
                :id="group.primary.name"
                type="target"
                :position="Position.Left"
                class="!w-2.5 !h-2.5 !bg-[#a855f7] !border-none"
                :style="{ top: '50%', background: getSocketColor(group.primary.type) }"
            />
            <span class="ml-3 text-gray-400">
              {{ group.primary.name_localized || group.base }}
              <span class="ml-1 px-1 py-0.5 rounded bg-gray-700 text-gray-300">{{ group.primary.type }}</span>
            </span>
        </div>

        <!-- Spacer if needed -->
        
        <!-- Outputs -->
        <div v-if="!useGrouped" v-for="(output, i) in filteredOutputs" :key="`out-${i}-${output.name}`" class="relative flex items-center justify-end h-5">
             <span class="mr-3 text-gray-400">{{ output.name_localized || output.name }}</span>
             <Handle
                :id="output.name"
                type="source"
                :position="Position.Right"
                class="!w-2.5 !h-2.5 !bg-[#a855f7] !border-none"
                :style="{ top: '50%', background: getSocketColor(output.type) }"
             />
        </div>
        <div v-else v-for="(group, i) in outputGroups" :key="`out-${i}-${group.base}`" class="relative flex items-center justify-end h-5">
             <span class="mr-3 text-gray-400">
               {{ group.primary.name_localized || group.base }}
               <span class="ml-1 px-1 py-0.5 rounded bg-gray-700 text-gray-300">{{ group.primary.type }}</span>
             </span>
             <Handle
                :id="group.primary.name"
                type="source"
                :position="Position.Right"
                class="!w-2.5 !h-2.5 !bg-[#a855f7] !border-none"
                :style="{ top: '50%', background: getSocketColor(group.primary.type) }"
             />
        </div>
      </div>
      <!-- preview moved to popover -->
    </div>
  </div>
</template>

<style scoped>
.blender-node {
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5), 0 2px 4px -1px rgba(0, 0, 0, 0.3);
}
</style>
<style>
.vue-flow__node.selected .blender-node {
    border-color: #a855f7;
    box-shadow: 0 0 0 2px rgba(168,85,247,.6), 0 0 12px rgba(168,85,247,.4);
}
</style>
