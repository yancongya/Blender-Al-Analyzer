<script setup lang="ts">
import { ref, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { NButton } from 'naive-ui'
import { SvgIcon } from '@/components/common'
import Codemirror from 'codemirror-editor-vue3'
import 'codemirror/lib/codemirror.css'
import 'codemirror/theme/dracula.css'
import 'codemirror/mode/javascript/javascript.js'
import cytoscape from 'cytoscape'
import dagre from 'cytoscape-dagre'

// Register dagre extension
try {
  cytoscape.use(dagre)
} catch (e) {
  // ignore if already registered
}

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
}>()

const graphRef = ref<HTMLDivElement | null>(null)
const graphEmpty = ref(false)
let cy: any = null

const cmOptions = {
  tabSize: 2,
  mode: 'application/json',
  theme: 'dracula',
  lineNumbers: true,
  line: true,
  readOnly: true,
}

// Graph Logic
function getLogicalElements(data: any) {
  const nodes = (data.selected_nodes || data.nodes || []).map((n: any) => ({
    data: { id: n.name || n.type }
  }))
  
  const edges = (data.connections || data.links || []).map((c: any, i: number) => ({
    data: { source: c.from_node, target: c.to_node }
  }))
  
  // Fallback edges if none
  if (edges.length === 0 && nodes.length > 0) {
      const selected = data.selected_nodes || data.nodes || []
      selected.forEach((n: any) => {
        if (!n.outputs) return
        n.outputs.forEach((o: any) => {
           if (!o.connected_to) return
           o.connected_to.forEach((ct: any) => {
               edges.push({ data: { source: n.name, target: ct.node } })
           })
        })
      })
  }
  
  return { nodes, edges }
}

async function buildDetailedElements() {
  const rawData = props.processedData.nodes
  if (!rawData) return []
  let data
  try {
      data = JSON.parse(rawData)
  } catch (e) {
      return []
  }
  
  const { nodes: logicalNodes, edges: logicalEdges } = getLogicalElements(data)
  if (logicalNodes.length === 0) return []

  const MIN_WIDTH = 100
  const CHAR_WIDTH = 7 // approximate px per char
  const HEADER_HEIGHT = 40
  const ITEM_HEIGHT = 24
  const nodeDims: Record<string, any> = {}

  const selectedNodes = data.selected_nodes || data.nodes || []
  selectedNodes.forEach((n: any) => {
     const id = n.name || n.type
     const visibleInputs = (n.inputs || []).filter((inp: any) => inp.is_connected)
     const visibleOutputs = (n.outputs || []).filter((out: any) => out.is_connected)
     
     // Calculate adaptive width
     const titleLen = (n.label || n.name || n.type || '').length
     let maxInputLen = 0
     visibleInputs.forEach((i: any) => maxInputLen = Math.max(maxInputLen, (i.name || '').length))
     let maxOutputLen = 0
     visibleOutputs.forEach((o: any) => maxOutputLen = Math.max(maxOutputLen, (o.name || '').length))
     
     // Width logic: Title or (Input + Output + gap)
     const contentWidth = Math.max(
         titleLen * 8, 
         (maxInputLen + maxOutputLen) * CHAR_WIDTH + 40
     )
     const width = Math.max(MIN_WIDTH, contentWidth)
     
     const height = HEADER_HEIGHT + Math.max(visibleInputs.length, visibleOutputs.length) * ITEM_HEIGHT + 10
     nodeDims[id] = { w: width, h: height, visibleInputs, visibleOutputs }
  })

  // Update logicalNodes dimensions for layout
  logicalNodes.forEach((n: any) => {
      const d = nodeDims[n.data.id]
      if (d) {
          n.data.width = d.w
          n.data.height = d.h
      } else {
          n.data.width = MIN_WIDTH
          n.data.height = 100
      }
  })

  // Pass 1: Abstract Layout
  const positions: Record<string, {x: number, y: number}> = await new Promise((resolve) => {
      const cyTemp = cytoscape({
          elements: { nodes: logicalNodes, edges: logicalEdges },
          headless: true,
          style: [
            {
              selector: 'node',
              style: {
                width: 'data(width)',
                height: 'data(height)'
              }
            }
          ]
      })
      cyTemp.layout({
          name: 'dagre',
          rankDir: 'LR',
          nodeSep: 80,
          rankSep: 250, // More space for connections
          stop: () => {
              const pos: Record<string, {x: number, y: number}> = {}
              cyTemp.nodes().forEach(n => {
                pos[n.id()] = n.position()
              })
              cyTemp.destroy()
              resolve(pos)
          }
      } as any).run()
  })

  // Pass 2: Generate Sockets & Parents
  const elements: any[] = []
  
  selectedNodes.forEach((n: any) => {
      const id = n.name || n.type
      const pos = positions[id] || { x: 0, y: 0 }
      const dims = nodeDims[id] || { w: MIN_WIDTH, h: 100, visibleInputs: [], visibleOutputs: [] }
      const { w: width, h: totalHeight, visibleInputs, visibleOutputs } = dims
      
      // Parent Node
      elements.push({
          data: { 
              id, 
              label: n.label || n.name || n.type,
              width: width,
              height: totalHeight,
              type: 'parent'
          },
          position: pos,
          classes: 'parent-node'
      })
      
      // Input Sockets (Left)
      visibleInputs.forEach((inp: any, i: number) => {
          const socketId = `${id}__in__${inp.name}`
          const absX = pos.x - width / 2
          const absY = pos.y - totalHeight / 2 + HEADER_HEIGHT + i * ITEM_HEIGHT + ITEM_HEIGHT/2
          
          elements.push({
              data: { id: socketId, parent: id, label: inp.name, type: 'socket-in' },
              position: { x: absX, y: absY },
              classes: 'socket-in'
          })
      })
      
      // Output Sockets (Right)
      visibleOutputs.forEach((out: any, i: number) => {
          const socketId = `${id}__out__${out.name}`
          const absX = pos.x + width / 2
          const absY = pos.y - totalHeight / 2 + HEADER_HEIGHT + i * ITEM_HEIGHT + ITEM_HEIGHT/2
          
          elements.push({
              data: { id: socketId, parent: id, label: out.name, type: 'socket-out' },
              position: { x: absX, y: absY },
              classes: 'socket-out'
          })
      })
  })
  
  // Edges
  const rawConnections = data.connections || data.links || []
  
  if (rawConnections.length > 0) {
      rawConnections.forEach((c: any, i: number) => {
          if (c.from_socket && c.to_socket) {
              elements.push({
                  data: {
                      id: `e${i}`,
                      source: `${c.from_node}__out__${c.from_socket}`,
                      target: `${c.to_node}__in__${c.to_socket}`
                  },
                  classes: 'connection'
              })
          } else {
             elements.push({
                  data: { id: `e${i}`, source: c.from_node, target: c.to_node },
                  classes: 'connection'
             })
          }
      })
  } else {
      // Fallback
       selectedNodes.forEach((n: any) => {
        if (!n.outputs) return
        n.outputs.forEach((o: any) => {
           if (!o.connected_to) return
           o.connected_to.forEach((ct: any, j: number) => {
               elements.push({
                   data: { 
                       id: `eo${n.name}-${o.name}-${ct.node}-${ct.socket}-${j}`,
                       source: `${n.name}__out__${o.name}`,
                       target: `${ct.node}__in__${ct.socket}`
                   },
                   classes: 'connection'
               })
           })
        })
      })
  }

  return elements
}

async function renderGraph() {
  if (props.displayMode !== 'graph') return
  
  await nextTick()
  const container = graphRef.value
  if (!container) return

  const elements = await buildDetailedElements()
  graphEmpty.value = elements.length === 0

  if (cy) { cy.destroy(); cy = null }
  
  // Limit pixel ratio to balance performance and quality
  const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5)

  cy = cytoscape({
    container,
    elements,
    layout: { name: 'preset' },
    style: [
      { 
        selector: 'node[type="parent"]', 
        style: { 
          'shape': 'round-rectangle',
          'background-color': '#2d2d2d',
          'background-opacity': 0.9,
          'border-width': 1,
          'border-color': '#555',
          'width': 'data(width)',
          'height': 'data(height)',
          'label': 'data(label)',
          'color': '#fff',
          'font-size': 14,
          'font-weight': 'bold',
          'text-valign': 'top',
          'text-halign': 'center',
          'text-margin-y': 5,
          'padding': '0px'
        } 
      },
      {
        selector: 'node[type="parent"]:selected',
        style: {
          'border-width': 2,
          'border-color': '#7e57c2',
          'background-color': '#3d3d3d'
        }
      },
      {
        selector: 'node[type="parent"]:active',
        style: {
          'overlay-opacity': 0
        }
      },
      {
        selector: 'core',
        style: {
          'active-bg-opacity': 0
        } as any
      },
      {
          selector: 'node[type^="socket"]',
          style: {
              'shape': 'ellipse',
              'width': 10,
              'height': 10,
              'background-color': '#7e57c2',
              'label': 'data(label)',
              'font-size': 10,
              'color': '#ccc'
          }
      },
      {
          selector: 'node[type="socket-in"]',
          style: {
              'text-halign': 'right',
              'text-valign': 'center',
              'text-margin-x': 5
          }
      },
      {
          selector: 'node[type="socket-out"]',
          style: {
              'text-halign': 'left',
              'text-valign': 'center',
              'text-margin-x': -5
          }
      },
      { 
        selector: 'edge', 
        style: { 
          'line-color': '#9fa8da', 
          'target-arrow-color': '#9fa8da', 
          'target-arrow-shape': 'triangle', 
          'curve-style': 'bezier', 
          'width': 2,
          'arrow-scale': 1.2
        } 
      },
    ],
    wheelSensitivity: 0.2,
    pixelRatio, 
    textureOnViewport: false, 
    motionBlur: false,
    hideEdgesOnViewport: true
  })
  
  cy.fit(undefined, 50)
}

// Watchers
watch(() => props.processedData.nodes, () => {
  if (props.displayMode === 'graph') renderGraph()
})

watch(() => props.displayMode, () => {
  if (props.displayMode === 'graph') {
      renderGraph()
  }
})

watch(() => props.isFullscreen, async () => {
  // If we just entered fullscreen, we need to wait for DOM and re-render
  if (props.isFullscreen && props.displayMode === 'graph') {
      // Force a slight delay to ensure container size is ready
      await nextTick()
      renderGraph()
  }
})

// Initial render check
onMounted(() => {
    if (props.displayMode === 'graph') renderGraph()
})

onUnmounted(() => {
    if (cy) { cy.destroy(); cy = null }
})

</script>

<template>
  <div class="flex flex-col h-full bg-[#101014] rounded-lg overflow-hidden border border-gray-700" :class="{ 'border-0 rounded-none': isFullscreen }">
     <!-- Header -->
     <div class="flex justify-between items-center p-2 border-b border-gray-800 bg-black/20 backdrop-blur-sm" :class="{ 'absolute top-0 left-0 right-0 z-20 p-4': isFullscreen }">
         <div class="font-bold text-purple-400 flex items-center gap-4">
            <span v-if="!isFullscreen">Node Data</span>
            <span v-else class="text-xl">Node Data Source Preview</span>
            
            <!-- 4-Dot Level Switcher -->
            <div class="relative flex items-center justify-between w-20 h-1 bg-gray-600 rounded ml-2">
                <div 
                    v-for="level in 4" 
                    :key="level"
                    class="absolute w-3 h-3 rounded-full cursor-pointer transition-all shadow-sm border border-gray-800"
                    :class="detailLevel === (level - 1) ? 'bg-purple-600 scale-125' : 'bg-gray-400 hover:bg-purple-400'"
                    :style="{ left: `${(level - 1) * 33.33}%`, transform: 'translateX(-50%)' }"
                    @click="emit('update:detailLevel', level - 1)"
                    :title="(level - 1) === 0 ? 'Ultra Lite' : (level - 1) === 1 ? 'Lite (Logic Only)' : (level - 1) === 2 ? 'Standard (Default)' : 'Full (Debug)'"
                ></div>
            </div>
            
            <!-- Display Mode -->
            <div class="ml-4 flex items-center gap-2">
              <NButton size="tiny" tertiary :type="displayMode === 'code' ? 'primary' : 'default'" @click="emit('update:displayMode', 'code')">Code</NButton>
              <NButton size="tiny" tertiary :type="displayMode === 'graph' ? 'primary' : 'default'" @click="emit('update:displayMode', 'graph')">Graph</NButton>
            </div>
         </div>
         <div class="flex items-center gap-2">
             <span class="text-xs text-gray-500">{{ processedData.filename }} ({{ processedData.tokens }} tokens)</span>
             <NButton size="tiny" quaternary circle @click="emit('copy', processedData.nodes)">
                <template #icon><SvgIcon icon="ri:file-copy-2-line" /></template>
             </NButton>
             <NButton size="tiny" quaternary circle @click="emit('toggleFullscreen')" :title="isFullscreen ? 'Exit Fullscreen (Esc)' : 'Fullscreen'">
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
        <div v-else class="h-full w-full relative bg-[#101014]">
            <div v-if="graphEmpty" class="p-3 text-center text-xs text-gray-500 absolute inset-0 flex items-center justify-center">
              No graph data available.
            </div>
            <div ref="graphRef" class="w-full h-full"></div>
        </div>
     </div>
  </div>
</template>
