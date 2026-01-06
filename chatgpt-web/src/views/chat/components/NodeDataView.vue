<script setup lang="ts">
import { ref, watch, nextTick, onMounted, computed, onUnmounted } from 'vue'
import type { CSSProperties } from 'vue'
import { NButton } from 'naive-ui'
import { SvgIcon } from '@/components/common'
import Codemirror from 'codemirror-editor-vue3'
import 'codemirror/lib/codemirror.css'
import 'codemirror/theme/dracula.css'
import 'codemirror/mode/javascript/javascript.js'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import dagre from 'dagre'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import BlenderNode from './BlenderNode.vue'
// ... existing code ...

const props = defineProps<{
  processedData: {
    nodes: string
    filename: string
    tokens: number
  }
  detailLevel: number
  displayMode: 'code' | 'graph'
  isFullscreen: boolean
}>()

const emit = defineEmits<{
  (e: 'update:detailLevel', value: number): void
  (e: 'update:displayMode', value: 'code' | 'graph'): void
  (e: 'toggleFullscreen'): void
  (e: 'copy', text: string): void
  (e: 'refresh'): void
}>()

const cmOptions = {
  tabSize: 2,
  mode: 'application/json',
  theme: 'dracula',
  lineNumbers: true,
  line: true,
  readOnly: true,
}

const { fitView, setNodes, setEdges, setViewport, viewport } = useVueFlow()
const graphEmpty = ref(false)
const hoveredRaw = ref<any>(null)
const hoverPos = ref<{ x: number, y: number } | null>(null)
const hoverTimer = ref<number | null>(null)
const hoverVisible = ref(false)
const panOnDrag = ref(false)
const boxSelecting = ref(false)
const boxStart = ref<{x:number,y:number}|null>(null)
const boxCurrent = ref<{x:number,y:number}|null>(null)
function onNodeHover(payload: any) {
  hoveredRaw.value = payload?.raw ?? payload
  if (payload && typeof payload.x === 'number' && typeof payload.y === 'number') {
    hoverPos.value = { x: payload.x, y: payload.y }
  }
  if (hoverTimer.value) {
    window.clearTimeout(hoverTimer.value)
    hoverTimer.value = null
  }
  hoverTimer.value = window.setTimeout(() => {
    hoverVisible.value = true
  }, 500)
}
function onNodeMove(payload: { x: number, y: number }) {
  hoverPos.value = { x: payload.x, y: payload.y }
}
function onNodeLeave() {
  hoveredRaw.value = null
  hoverVisible.value = false
  if (hoverTimer.value) {
    window.clearTimeout(hoverTimer.value)
    hoverTimer.value = null
  }
}
function onKeyDown(e: KeyboardEvent) {
  if (e.code === 'Space') {
    panOnDrag.value = true
  }
}
function onKeyUp(e: KeyboardEvent) {
  if (e.code === 'Space') {
    panOnDrag.value = false
  }
  if (e.key === 'Escape') {
    boxSelecting.value = false
    boxStart.value = null
    boxCurrent.value = null
  }
}
onMounted(() => {
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('keyup', onKeyUp)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('keyup', onKeyUp)
})
function startBoxSelect(e: MouseEvent) {
  // Middle mouse drag for custom panning
  if (e.button === 1) {
    const start = { x: e.clientX, y: e.clientY }
    const startViewport = { ...viewport.value }
    function onMove(ev: MouseEvent) {
      const dx = ev.clientX - start.x
      const dy = ev.clientY - start.y
      setViewport({ x: startViewport.x + dx, y: startViewport.y + dy, zoom: startViewport.zoom })
    }
    function onUp() {
      window.removeEventListener('mousemove', onMove)
      window.removeEventListener('mouseup', onUp)
    }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup', onUp, { once: true })
    return
  }
  // Only left mouse triggers box selection
  if (e.button !== 0 || panOnDrag.value) return
  // Only when dragging on empty pane (not on a node/edge)
  const target = e.target as HTMLElement
  if (!target || !target.classList.contains('vue-flow__pane')) return
  boxSelecting.value = true
  boxStart.value = { x: e.clientX, y: e.clientY }
  boxCurrent.value = { x: e.clientX, y: e.clientY }
  window.addEventListener('mousemove', moveBoxSelect)
  window.addEventListener('mouseup', (ev) => endBoxSelect(ev as MouseEvent), { once: true })
}
function moveBoxSelect(e: MouseEvent) {
  if (!boxSelecting.value) return
  boxCurrent.value = { x: e.clientX, y: e.clientY }
}
function endBoxSelect(e: MouseEvent) {
  if (!boxSelecting.value) return
  const minX = Math.min(boxStart.value!.x, boxCurrent.value!.x)
  const maxX = Math.max(boxStart.value!.x, boxCurrent.value!.x)
  const minY = Math.min(boxStart.value!.y, boxCurrent.value!.y)
  const maxY = Math.max(boxStart.value!.y, boxCurrent.value!.y)
  const nodeEls = Array.from(document.querySelectorAll('.vue-flow__node')) as HTMLElement[]
  const selectedIds = new Set<string>()
  nodeEls.forEach((el) => {
    const r = el.getBoundingClientRect()
    const intersects = !(r.right < minX || r.left > maxX || r.bottom < minY || r.top > maxY)
    if (intersects) {
      const id = el.getAttribute('data-id')
      if (id) selectedIds.add(id)
    }
  })
  // Update selection on nodes
  const additive = !!(e.shiftKey || e.ctrlKey || e.metaKey)
  setNodes((nds: any[]) => nds.map((n) => {
    const nextSelected = additive ? (n.selected || selectedIds.has(n.id)) : selectedIds.has(n.id)
    return { ...n, selected: nextSelected }
  }))
  // Reset
  boxSelecting.value = false
  boxStart.value = null
  boxCurrent.value = null
  window.removeEventListener('mousemove', moveBoxSelect)
}
const boxStyle = computed<CSSProperties>(() => {
  if (!boxSelecting.value || !boxStart.value || !boxCurrent.value) return { display: 'none' }
  const minX = Math.min(boxStart.value.x, boxCurrent.value.x)
  const minY = Math.min(boxStart.value.y, boxCurrent.value.y)
  const w = Math.abs(boxCurrent.value.x - boxStart.value.x)
  const h = Math.abs(boxCurrent.value.y - boxStart.value.y)
  return {
    display: 'block',
    position: 'fixed',
    left: `${minX}px`,
    top: `${minY}px`,
    width: `${w}px`,
    height: `${h}px`,
    border: '1px dashed #8b5cf6',
    background: 'rgba(139,92,246,0.1)',
    zIndex: 4000,
    pointerEvents: 'none'
  }
})

// Layout Logic
const dagreGraph = new dagre.graphlib.Graph()
dagreGraph.setDefaultEdgeLabel(() => ({}))

function getLayoutedElements(nodes: any[], edges: any[]) {
    dagreGraph.setGraph({ rankdir: 'LR', align: 'UL', nodesep: 40, ranksep: 80 })

    nodes.forEach((node) => {
        dagreGraph.setNode(node.id, { width: node.data.width || 200, height: node.data.height || 100 })
    })

    edges.forEach((edge) => {
        dagreGraph.setEdge(edge.source, edge.target)
    })

    dagre.layout(dagreGraph)

    return {
        nodes: nodes.map((node) => {
            const nodeWithPosition = dagreGraph.node(node.id)
            return {
                ...node,
                position: { x: nodeWithPosition.x, y: nodeWithPosition.y },
            }
        }),
        edges,
    }
}

async function renderGraph() {
  if (props.displayMode !== 'graph') return
  await nextTick()

  const rawData = props.processedData.nodes
  if (!rawData) {
      graphEmpty.value = true
      return
  }
  
  let data
  try {
      data = JSON.parse(rawData)
  } catch (e) {
      graphEmpty.value = true
      return
  }

  const selectedNodes = data.selected_nodes || data.nodes || []
  const connections = data.connections || data.links || []
  
  if (selectedNodes.length === 0) {
      graphEmpty.value = true
      setNodes([])
      setEdges([])
      return
  }

  graphEmpty.value = false
  
  const HEADER_HEIGHT = 28
  const ROW_HEIGHT = 20 // Approx height per input/output row

  const nodes = selectedNodes.map((n: any) => {
      const rawInputs = n.inputs || []
      const rawOutputs = n.outputs || []
      
      // Calculate dimensions based on CURRENT detail level visibility
      let visibleInputs: any[] = []
      let visibleOutputs: any[] = []
      if (props.detailLevel >= 3) {
        visibleInputs = rawInputs
        visibleOutputs = rawOutputs
      } else if (props.detailLevel >= 2) {
        visibleInputs = rawInputs.filter((i: any) => i.enabled !== false)
        visibleOutputs = rawOutputs.filter((o: any) => o.enabled !== false)
      } else {
        visibleInputs = rawInputs.filter((i: any) => (i.enabled !== false) && i.is_connected)
        visibleOutputs = rawOutputs.filter((o: any) => (o.enabled !== false) && o.is_connected)
      }
      function baseKey(s: any) {
        const id = s?.identifier || s?.name || ''
        const idx = id.indexOf('_')
        return idx > 0 ? id.slice(0, idx) : id
      }
      function countGroups(arr: any[]) {
        const set = new Set(arr.map((s: any) => baseKey(s)))
        return set.size
      }
      const maxRows = props.detailLevel >= 3
        ? Math.max(visibleInputs.length, visibleOutputs.length)
        : Math.max(countGroups(visibleInputs), countGroups(visibleOutputs))
      const estimatedHeight = HEADER_HEIGHT + maxRows * ROW_HEIGHT + 10
      const estimatedWidth = Math.max(140, (n.label || n.name || '').length * 8 + 40)
      
      return {
          id: n.name || n.type,
          type: 'blender',
          selectable: true,
          draggable: true,
          data: { 
              label: n.label || n.name || n.type,
              label_localized: n.label_localized,
              inputs: rawInputs, // Pass ALL inputs so component can filter
              outputs: rawOutputs, // Pass ALL outputs
              width: estimatedWidth,
              height: estimatedHeight,
              detailLevel: props.detailLevel,
              raw: n
          },
          position: { x: 0, y: 0 } // Initial position, will be set by dagre
      }
  })

  const edges: any[] = []
  
  if (connections.length > 0) {
      connections.forEach((c: any, i: number) => {
         if (c.from_socket && c.to_socket) {
             edges.push({
                 id: `e-${i}`,
                 source: c.from_node,
                 target: c.to_node,
                 sourceHandle: c.from_socket,
                 targetHandle: c.to_socket,
                 type: 'default',
                 animated: false
             })
         } else {
             edges.push({
                 id: `e-${i}`,
                 source: c.from_node,
                 target: c.to_node
             })
         }
      })
  } else {
      // Fallback connections
      selectedNodes.forEach((n: any) => {
        if (!n.outputs) return
        n.outputs.forEach((o: any) => {
           if (!o.connected_to) return
           o.connected_to.forEach((ct: any, j: number) => {
               edges.push({
                   id: `eo-${n.name}-${o.name}-${j}`,
                   source: n.name,
                   target: ct.node,
                   sourceHandle: o.name,
                   targetHandle: ct.socket
               })
           })
        })
      })
  }

  const layouted = getLayoutedElements(nodes, edges)
  setNodes(layouted.nodes)
  setEdges(layouted.edges)
  
  await nextTick()
  fitView({ padding: 0.2 })
}

// Controls Logic
function handleResetView() {
    renderGraph()
}

function handleCenterView() {
    fitView({ padding: 0.2, duration: 500 })
}

// Watchers
watch(() => props.processedData.nodes, () => {
  if (props.displayMode === 'graph') renderGraph()
})

watch(() => props.detailLevel, () => {
  if (props.displayMode === 'graph') {
      renderGraph() // Re-render to update nodes with new detailLevel
  }
})

watch(() => props.displayMode, () => {
  if (props.displayMode === 'graph') {
      renderGraph()
  }
})

watch(() => props.isFullscreen, async () => {
  if (props.isFullscreen && props.displayMode === 'graph') {
      await nextTick()
      fitView({ padding: 0.2 })
  }
})

onMounted(() => {
    if (props.displayMode === 'graph') renderGraph()
})
</script>

<template>
  <div class="flex flex-col h-full bg-[#101014] rounded-lg overflow-hidden border border-gray-700" :class="{ 'border-0 rounded-none': isFullscreen }">
     <!-- Header -->
     <div class="flex justify-between items-center p-2 border-b border-gray-800 bg-black/20 backdrop-blur-sm" :class="{ 'absolute top-0 left-0 right-0 z-20 p-4': isFullscreen }">
         <div class="font-bold text-purple-400 flex items-center gap-4">
           <span v-if="!isFullscreen">Node Data</span>
           <span v-else class="text-xl">{{ $t('chat.nodeDataPreview') }}</span>
           <span class="text-xs text-gray-400">≈ {{ Math.ceil((processedData.tokens || 0)) }} {{ $t('chat.tokens') }}</span>
           <NButton size="tiny" tertiary @click="emit('refresh')" :title="$t('common.refresh')">
             <template #icon><SvgIcon icon="ri:refresh-line" /></template>
           </NButton>
            
            <!-- 4-Dot Level Switcher -->
            <div class="relative flex items-center justify-between w-20 h-1 bg-gray-600 rounded ml-2">
                <div 
                    v-for="level in 4" 
                    :key="level"
                    class="absolute w-3 h-3 rounded-full cursor-pointer transition-all shadow-sm border border-gray-800"
                    :class="detailLevel === (level - 1) ? 'bg-purple-600 scale-125' : 'bg-gray-400 hover:bg-purple-400'"
                    :style="{ left: `${(level - 1) * 33.33}%`, transform: 'translateX(-50%)' }"
                    @click="emit('update:detailLevel', level - 1)"
                    :title="(level - 1) === 0 ? $t('chat.ultraLite') : (level - 1) === 1 ? $t('chat.lite') : (level - 1) === 2 ? $t('chat.standard') : $t('chat.full')"
                ></div>
            </div>
            
            <!-- Display Mode -->
            <div class="ml-4 flex items-center gap-2">
              <NButton size="tiny" tertiary :type="displayMode === 'code' ? 'primary' : 'default'" @click="emit('update:displayMode', 'code')">{{ $t('chat.code') }}</NButton>
              <NButton size="tiny" tertiary :type="displayMode === 'graph' ? 'primary' : 'default'" @click="emit('update:displayMode', 'graph')">{{ $t('chat.graph') }}</NButton>
            </div>
         </div>
         <div class="flex items-center gap-2">
             <span class="text-xs text-gray-500">{{ processedData.filename }}</span>
             <NButton size="tiny" quaternary circle @click="emit('copy', processedData.nodes)">
                <template #icon><SvgIcon icon="ri:file-copy-2-line" /></template>
             </NButton>
             <NButton size="tiny" quaternary circle @click="emit('toggleFullscreen')" :title="isFullscreen ? $t('chat.exitFullscreen') : $t('chat.fullscreen')">
                <template #icon><SvgIcon :icon="isFullscreen ? 'ri:fullscreen-exit-line' : 'ri:fullscreen-line'" /></template>
             </NButton>
         </div>
     </div>

     <!-- Body -->
     <div class="flex-1 overflow-hidden relative" :class="{ 'pt-16': isFullscreen }">
        <div v-if="displayMode === 'code'" class="h-full">
           <Codemirror
               :value="processedData.nodes"
               :options="cmOptions"
               :height="'100%'"
           />
        </div>
        <div v-else class="h-full w-full relative bg-[#1e1e1e]">
            <div v-if="graphEmpty" class="p-3 text-center text-xs text-gray-500 absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
              {{ $t('chat.noGraphData') }}
            </div>
            
            <VueFlow 
                :fit-view-on-init="true" 
                :min-zoom="0.1" 
                :max-zoom="4"
                :only-render-visible-elements="true"
                :elements-selectable="true"
                :nodes-draggable="true"
                :nodes-connectable="false"
                :selection-on-drag="true"
                :pan-on-drag="panOnDrag"
                :zoom-on-scroll="true"
                @mousedown="startBoxSelect"
            >
                <template #node-blender="props">
                    <BlenderNode :data="props.data" @hover="onNodeHover" @move="onNodeMove" @leave="onNodeLeave" />
                </template>
                
                <Background pattern-color="#333" :gap="20" />
                <Controls :show-interactive="false" />

                <!-- Custom Controls Overlay -->
                <div class="absolute bottom-4 left-4 z-10 flex gap-2">
                    <NButton size="small" secondary type="primary" @click="handleResetView">
                        <template #icon><SvgIcon icon="ri:refresh-line" /></template>
                        {{ $t('chat.resetLayout') }}
                    </NButton>
                    <NButton size="small" secondary type="info" @click="handleCenterView">
                         <template #icon><SvgIcon icon="ri:focus-3-line" /></template>
                        {{ $t('chat.centerView') }}
                    </NButton>
                </div>
            </VueFlow>
            <!-- Hover JSON tooltip -->
            <div v-if="hoverVisible && hoveredRaw && hoverPos" class="fixed z-50 pointer-events-none" :style="{ left: (hoverPos.x + 12) + 'px', top: (hoverPos.y + 12) + 'px' }">
              <div class="w-[320px] max-h-[50vh] overflow-auto bg-black/80 border border-gray-700 rounded p-2 shadow-xl">
                <div class="text-xs font-bold text-purple-300 mb-1">{{ $t('chat.nodeDataSource') }}</div>
                <pre class="text-[11px] leading-[1.25] text-green-200">{{ JSON.stringify(hoveredRaw, null, 2) }}</pre>
              </div>
            </div>
            <!-- Box selection overlay -->
            <div v-if="boxSelecting && boxStart && boxCurrent" :style="boxStyle"></div>
        </div>
     </div>
  </div>
</template>

<style>
/* Vue Flow Dark Theme Overrides */
.vue-flow__edge-path {
    stroke: #888;
    stroke-width: 2;
}
.vue-flow__controls {
    box-shadow: 0 0 10px rgba(0,0,0,0.5);
    border: 1px solid #444;
}
.vue-flow__controls-button {
    background: #333;
    color: #eee;
    border-bottom: 1px solid #444;
}
.vue-flow__controls-button:hover {
    background: #444;
}
.vue-flow__controls-button svg {
    fill: currentColor;
}
</style>
