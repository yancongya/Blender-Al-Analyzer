<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { NList, NListItem, NButton, NInput, NTag, NEmpty, NSpin, NText, NSpace, NDrawer, NDrawerContent } from 'naive-ui'
import { SvgIcon } from '@/components/common'
import { fetchDocsList, fetchDocContent, searchDocs } from '@/api'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'
import 'highlight.js/styles/github-dark.css'

const route = useRoute()

// 监听路由变化，设置页面标题
watch(() => route.name, (newName) => {
  if (newName === 'Docs') {
    document.title = '文档阅读 - AI Node Analyzer'
  }
}, { immediate: true })

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  highlight: function (str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value
      } catch (__) {}
    }
    return ''
  }
})

// 状态
const loading = ref(false)
const docsList = ref<any[]>([])
const categories = ref<string[]>([])
const currentCategory = ref<string>('全部')
const searchKeyword = ref('')
const currentDoc = ref<any>(null)
const docContent = ref('')
const showDrawer = ref(false)
const searchResults = ref<any[]>([])

// 获取文档列表
async function loadDocsList() {
  try {
    loading.value = true
    const { data } = await fetchDocsList()
    docsList.value = data.docs || []
    categories.value = ['全部', ...(data.categories || [])]
  } catch (error) {
    console.error('加载文档列表失败:', error)
  } finally {
    loading.value = false
  }
}

// 获取文档内容
async function loadDocContent(doc: any) {
  try {
    currentDoc.value = doc
    showDrawer.value = true
    const { data } = await fetchDocContent(doc.path)
    docContent.value = data.content || ''
  } catch (error) {
    console.error('加载文档内容失败:', error)
  }
}

// 搜索文档
async function handleSearch() {
  if (!searchKeyword.value.trim()) {
    searchResults.value = []
    return
  }
  
  try {
    loading.value = true
    const { data } = await searchDocs(searchKeyword.value)
    searchResults.value = data.results || []
  } catch (error) {
    console.error('搜索文档失败:', error)
  } finally {
    loading.value = false
  }
}

// 过滤文档
const filteredDocs = computed(() => {
  if (searchKeyword.value.trim()) {
    return searchResults.value
  }
  
  if (currentCategory.value === '全部') {
    return docsList.value
  }
  
  return docsList.value.filter(doc => doc.category === currentCategory.value)
})

// Markdown 渲染
const renderedContent = computed(() => {
  if (!docContent.value) return ''
  return md.render(docContent.value)
})

// 格式化文件大小
function formatSize(bytes: number): string {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(2) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(2) + ' MB'
}

// 刷新
function handleRefresh() {
  loadDocsList()
  searchResults.value = []
  searchKeyword.value = ''
}

// 切换分类
function handleCategoryChange(category: string) {
  currentCategory.value = category
}

onMounted(() => {
  loadDocsList()
})
</script>

<template>
  <div class="docs-container h-full p-6">
    <!-- 头部 -->
    <div class="docs-header mb-6">
      <div class="flex items-center justify-between mb-4">
        <h1 class="text-2xl font-bold flex items-center gap-2">
          <SvgIcon icon="ri:book-open-line" class="text-2xl" />
          文档阅读系统
        </h1>
        <n-button @click="handleRefresh" :loading="loading" secondary>
          <template #icon>
            <SvgIcon icon="ri:refresh-line" class="text-xl" />
          </template>
          刷新
        </n-button>
      </div>
      
      <!-- 搜索框 -->
      <div class="search-box mb-4">
        <n-input
          v-model:value="searchKeyword"
          placeholder="搜索文档..."
          clearable
          @keyup.enter="handleSearch"
        >
          <template #prefix>
            <SvgIcon icon="ri:search-line" class="text-xl" />
          </template>
          <template #suffix>
            <n-button text @click="handleSearch" :disabled="!searchKeyword.trim()">
              搜索
            </n-button>
          </template>
        </n-input>
      </div>
      
      <!-- 分类标签 -->
      <div class="category-tags flex gap-2 flex-wrap">
        <n-tag
          v-for="category in categories"
          :key="category"
          :type="currentCategory === category ? 'primary' : 'default'"
          :bordered="currentCategory !== category"
          checkable
          @click="handleCategoryChange(category)"
        >
          <template #icon>
            <SvgIcon v-if="category !== '全部'" icon="ri:folder-line" class="text-base" />
          </template>
          {{ category }}
        </n-tag>
      </div>
    </div>
    
    <!-- 文档列表 -->
    <n-spin :show="loading">
      <div v-if="filteredDocs.length === 0" class="empty-state">
        <n-empty description="暂无文档" />
      </div>
      
      <n-list v-else hoverable clickable>
        <n-list-item
          v-for="doc in filteredDocs"
          :key="doc.id"
          @click="loadDocContent(doc)"
        >
          <template #prefix>
            <SvgIcon icon="ri:file-text-line" class="text-2xl" />
          </template>
          
          <div class="doc-item">
            <div class="doc-title">{{ doc.title }}</div>
            <div class="doc-meta">
              <n-tag size="small" type="info" round>{{ doc.category }}</n-tag>
              <span class="doc-size">{{ formatSize(doc.size) }}</span>
              <span class="doc-time">{{ doc.modified_formatted }}</span>
            </div>
          </div>
          
          <template #suffix>
            <n-button text type="primary">
              查看
            </n-button>
          </template>
        </n-list-item>
      </n-list>
    </n-spin>
    
    <!-- 文档内容抽屉 -->
    <n-drawer v-model:show="showDrawer" :width="800" placement="right">
      <n-drawer-content :title="currentDoc?.title" closable>
        <div v-if="currentDoc" class="doc-meta-info mb-4">
          <n-space>
            <n-tag type="info" round>{{ currentDoc.category }}</n-tag>
            <n-text depth="3">{{ currentDoc.path }}</n-text>
            <n-text depth="3">{{ formatSize(currentDoc.size) }}</n-text>
          </n-space>
        </div>
        
        <div v-if="docContent" class="markdown-content" v-html="renderedContent"></div>
        <n-empty v-else description="文档内容为空" />
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<style scoped>
.docs-container {
  max-width: 1200px;
  margin: 0 auto;
}

.docs-header {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.dark .docs-header {
  background: #1f1f1f;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}

.doc-item {
  flex: 1;
}

.doc-title {
  font-size: 1rem;
  font-weight: 500;
  margin-bottom: 0.5rem;
  color: #333;
}

.dark .doc-title {
  color: #e5e5e5;
}

.doc-meta {
  display: flex;
  align-items: center;
  gap: 1rem;
  color: #999;
  font-size: 0.875rem;
}

.doc-size,
.doc-time {
  color: #999;
}

.empty-state {
  padding: 4rem 0;
  text-align: center;
}

.markdown-content {
  line-height: 1.8;
  color: #333;
}

.dark .markdown-content {
  color: #e5e5e5;
}

.markdown-content :deep(h1) {
  font-size: 2em;
  font-weight: bold;
  margin: 1em 0;
  padding-bottom: 0.3em;
  border-bottom: 1px solid #eaecef;
  color: #333;
}

.dark .markdown-content :deep(h1) {
  border-bottom-color: #3c3c3c;
  color: #e5e5e5;
}

.markdown-content :deep(h2) {
  font-size: 1.5em;
  font-weight: bold;
  margin: 1em 0;
  padding-bottom: 0.3em;
  border-bottom: 1px solid #eaecef;
  color: #333;
}

.dark .markdown-content :deep(h2) {
  border-bottom-color: #3c3c3c;
  color: #e5e5e5;
}

.markdown-content :deep(h3) {
  font-size: 1.25em;
  font-weight: bold;
  margin: 1em 0;
  color: #333;
}

.dark .markdown-content :deep(h3) {
  color: #e5e5e5;
}

.markdown-content :deep(p) {
  margin: 1em 0;
}

.markdown-content :deep(code) {
  background: #f6f8fa;
  padding: 0.2em 0.4em;
  border-radius: 3px;
  font-family: 'Courier New', monospace;
  color: #333;
}

.dark .markdown-content :deep(code) {
  background: #2d2d2d;
  color: #e5e5e5;
}

.markdown-content :deep(pre) {
  background: #f6f8fa;
  padding: 1em;
  border-radius: 6px;
  overflow-x: auto;
  margin: 1em 0;
}

.dark .markdown-content :deep(pre) {
  background: #2d2d2d;
}

.markdown-content :deep(pre code) {
  background: transparent;
  padding: 0;
}

.markdown-content :deep(blockquote) {
  border-left: 4px solid #dfe2e5;
  padding-left: 1em;
  color: #6a737d;
  margin: 1em 0;
}

.dark .markdown-content :deep(blockquote) {
  border-left-color: #3c3c3c;
  color: #999;
}

.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  padding-left: 2em;
  margin: 1em 0;
}

.markdown-content :deep(li) {
  margin: 0.5em 0;
}

.markdown-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 1em 0;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid #dfe2e5;
  padding: 0.5em 1em;
}

.dark .markdown-content :deep(th),
.dark .markdown-content :deep(td) {
  border-color: #3c3c3c;
}

.markdown-content :deep(th) {
  background: #f6f8fa;
  font-weight: bold;
  color: #333;
}

.dark .markdown-content :deep(th) {
  background: #2d2d2d;
  color: #e5e5e5;
}

.markdown-content :deep(a) {
  color: #0366d6;
  text-decoration: none;
}

.dark .markdown-content :deep(a) {
  color: #58a6ff;
}

.markdown-content :deep(a:hover) {
  text-decoration: underline;
}

.markdown-content :deep(img) {
  max-width: 100%;
  height: auto;
}
</style>