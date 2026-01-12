# Web Hooks 文档

## Hooks 概述

Web 前端使用 Vue 3 Composition API 的 Hooks 来复用逻辑，Hooks 位于 `src/hooks/` 和 `src/views/chat/hooks/` 目录。

## Hooks 列表

### 通用 Hooks (src/hooks)

| Hook | 文件 | 功能 |
|------|------|------|
| useBasicLayout | useBasicLayout.ts | 基础布局 |
| useIconRender | useIconRender.ts | 图标渲染 |
| useLanguage | useLanguage.ts | 语言切换 |
| useTheme | useTheme.ts | 主题切换 |

### 聊天 Hooks (src/views/chat/hooks)

| Hook | 文件 | 功能 |
|------|------|------|
| useChat | useChat.ts | 聊天逻辑 |
| useScroll | useScroll.ts | 滚动管理 |
| useUsingContext | useUsingContext.ts | 上下文使用 |

---

## 1. useBasicLayout

**文件**：`src/hooks/useBasicLayout.ts`

**功能**：基础布局 Hook，提供响应式布局信息。

### 返回值

```typescript
{
  isMobile: Ref<boolean>
  isTablet: Ref<boolean>
  isDesktop: Ref<boolean>
}
```

### 使用示例

```typescript
import { useBasicLayout } from '@/hooks/useBasicLayout'

const { isMobile, isTablet, isDesktop } = useBasicLayout()

if (isMobile.value) {
  // 移动设备逻辑
}
```

---

## 2. useIconRender

**文件**：`src/hooks/useIconRender.ts`

**功能**：图标渲染 Hook，提供图标渲染函数。

### 返回值

```typescript
{
  iconRender: (icon: string) => VNode
}
```

### 使用示例

```typescript
import { useIconRender } from '@/hooks/useIconRender'

const { iconRender } = useIconRender()

// 在模板中使用
<template>
  <component :is="iconRender('ri:home-line')" />
</template>
```

---

## 3. useLanguage

**文件**：`src/hooks/useLanguage.ts`

**功能**：语言切换 Hook，提供语言切换功能。

### 返回值

```typescript
{
  language: Ref<string>
  changeLanguage: (lang: string) => void
  availableLanguages: Array<{ label: string; value: string }>
}
```

### 使用示例

```typescript
import { useLanguage } from '@/hooks/useLanguage'

const { language, changeLanguage, availableLanguages } = useLanguage()

// 切换语言
changeLanguage('en-US')

// 获取当前语言
console.log(language.value)
```

---

## 4. useTheme

**文件**：`src/hooks/useTheme.ts`

**功能**：主题切换 Hook，提供主题切换功能。

### 返回值

```typescript
{
  theme: Ref<'light' | 'dark'>
  themeOverrides: Ref<GlobalThemeOverrides>
  toggleTheme: () => void
}
```

### 使用示例

```typescript
import { useTheme } from '@/hooks/useTheme'

const { theme, themeOverrides, toggleTheme } = useTheme()

// 切换主题
toggleTheme()

// 获取当前主题
console.log(theme.value)
```

---

## 5. useChat

**文件**：`src/views/chat/hooks/useChat.ts`

**功能**：聊天逻辑 Hook，提供聊天相关功能。

### 返回值

```typescript
{
  addChat: (chat: Chat) => void
  updateChat: (uuid: number, index: number, chat: Partial<Chat>) => void
  updateChatSome: (uuid: number, index: number, chat: Partial<Chat>) => void
  deleteChat: (uuid: number, index: number) => void
  clearChat: (uuid: number) => void
}
```

### 使用示例

```typescript
import { useChat } from '@/views/chat/hooks/useChat'

const { addChat, updateChat } = useChat()

// 添加聊天
addChat({
  uuid: 1,
  dateTime: new Date().toLocaleString(),
  text: 'Hello',
  inversion: true,
  error: false,
  conversationOptions: null,
  requestOptions: { prompt: 'Hello' }
})

// 更新聊天
updateChat(1, 0, { text: 'Updated' })
```

---

## 6. useScroll

**文件**：`src/views/chat/hooks/useScroll.ts`

**功能**：滚动管理 Hook，提供滚动相关功能。

### 返回值

```typescript
{
  scrollRef: Ref<HTMLDivElement | null>
  scrollToBottom: () => void
  scrollToBottomIfAtBottom: () => void
}
```

### 使用示例

```typescript
import { useScroll } from '@/views/chat/hooks/useScroll'

const { scrollRef, scrollToBottom, scrollToBottomIfAtBottom } = useScroll()

// 滚动到底部
scrollToBottom()

// 如果在底部则滚动
scrollToBottomIfAtBottom()
```

---

## 7. useUsingContext

**文件**：`src/views/chat/hooks/useUsingContext.ts`

**功能**：上下文使用 Hook，提供上下文相关功能。

### 返回值

```typescript
{
  usingContext: Ref<boolean>
  toggleUsingContext: () => void
}
```

### 使用示例

```typescript
import { useUsingContext } from '@/views/chat/hooks/useUsingContext'

const { usingContext, toggleUsingContext } = useUsingContext()

// 切换上下文
toggleUsingContext()

// 获取上下文状态
console.log(usingContext.value)
```

---

## 自定义 Hook 开发

### 基本结构

```typescript
import { ref, computed, onMounted, onUnmounted } from 'vue'

export function useMyHook() {
  // 状态
  const state = ref('initial')
  
  // 计算属性
  const computedState = computed(() => state.value.toUpperCase())
  
  // 方法
  const method = () => {
    state.value = 'updated'
  }
  
  // 生命周期
  onMounted(() => {
    console.log('mounted')
  })
  
  onUnmounted(() => {
    console.log('unmounted')
  })
  
  // 返回
  return {
    state,
    computedState,
    method
  }
}
```

### 使用示例

```typescript
import { useMyHook } from '@/hooks/useMyHook'

const { state, computedState, method } = useMyHook()

method()
console.log(state.value)
console.log(computedState.value)
```

---

## Hooks 最佳实践

1. **命名规范**：使用 `use` 前缀
2. **单一职责**：每个 Hook 只做一件事
3. **可复用性**：设计可复用的 Hook
4. **类型安全**：使用 TypeScript 定义类型
5. **清理副作用**：在 `onUnmounted` 中清理
6. **文档注释**：添加 JSDoc 注释
7. **测试友好**：设计易于测试的 Hook

---

## Hooks 文档索引

- [01-主界面文档](./01-主界面文档.md)
- [02-组件文档](./02-组件文档.md)
- [03-Store 文档](./03-Store文档.md)
- [04-API 文档](./04-API文档.md)
- [05-Hooks 文档](./05-Hooks文档.md)
- [06-路由文档](./06-路由文档.md)