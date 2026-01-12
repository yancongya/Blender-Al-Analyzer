# Web Store 文档

## Store 概述

Web 前端使用 Pinia 进行状态管理，Store 模块位于 `src/store/modules/` 目录。

## Store 模块列表

| 模块 | 文件 | 功能 |
|------|------|------|
| app | app/index.ts | 应用状态 |
| auth | auth/index.ts | 认证状态 |
| chat | chat/index.ts | 聊天状态 |
| prompt | prompt/index.ts | 提示词状态 |
| settings | settings/index.ts | 设置状态 |
| user | user/index.ts | 用户状态 |

---

## 1. App Store

**文件**：`src/store/modules/app/index.ts`

**功能**：管理应用全局状态。

### State

```typescript
{
  theme: 'light' | 'dark' | 'auto'
  language: 'zh-CN' | 'en-US' | 'ja-JP' | ...
  defaultQuestions: string[]
}
```

### Getters

| Getter | 返回类型 | 描述 |
|--------|----------|------|
| `isMobile` | `boolean` | 是否为移动设备 |
| `isDark` | `boolean` | 是否为暗色主题 |

### Actions

| Action | 参数 | 返回值 | 描述 |
|--------|------|--------|------|
| `setTheme` | `theme: string` | `void` | 设置主题 |
| `setLanguage` | `language: string` | `void` | 设置语言 |
| `setDefaultQuestions` | `questions: string[]` | `void` | 设置默认问题 |

### 使用示例

```typescript
import { useAppStore } from '@/store'

const appStore = useAppStore()

// 获取状态
const theme = appStore.theme
const language = appStore.language

// 调用 action
appStore.setTheme('dark')
appStore.setLanguage('en-US')
appStore.setDefaultQuestions(['问题1', '问题2'])
```

---

## 2. Auth Store

**文件**：`src/store/modules/auth/index.ts`

**功能**：管理认证状态。

### State

```typescript
{
  token: string
  isLogin: boolean
  userInfo: UserInfo | null
}
```

### UserInfo 类型

```typescript
interface UserInfo {
  id: string
  name: string
  avatar: string
  email: string
}
```

### Getters

| Getter | 返回类型 | 描述 |
|--------|----------|------|
| `isChatGPTAPI` | `boolean` | 是否使用 ChatGPT API |

### Actions

| Action | 参数 | 返回值 | 描述 |
|--------|------|--------|------|
| `setToken` | `token: string` | `void` | 设置令牌 |
| `setIsLogin` | `isLogin: boolean` | `void` | 设置登录状态 |
| `setUserInfo` | `userInfo: UserInfo` | `void` | 设置用户信息 |
| `logout` | - | `void` | 登出 |

### 使用示例

```typescript
import { useAuthStore } from '@/store'

const authStore = useAuthStore()

// 获取状态
const token = authStore.token
const isLogin = authStore.isLogin
const userInfo = authStore.userInfo

// 调用 action
authStore.setToken('your-token')
authStore.setIsLogin(true)
authStore.setUserInfo({
  id: '1',
  name: 'User',
  avatar: 'avatar.png',
  email: 'user@example.com'
})
authStore.logout()
```

---

## 3. Chat Store

**文件**：`src/store/modules/chat/index.ts`

**功能**：管理聊天状态。

### State

```typescript
{
  chat: Record<number, Chat[]>
  nodeData: NodeData
  nodeContextActive: boolean
}
```

### Chat 类型

```typescript
interface Chat {
  uuid: number
  dateTime: string
  text: string
  inversion: boolean
  error: boolean
  conversationOptions: {
    conversationId?: string
    parentMessageId?: string
  } | null
  requestOptions: {
    prompt: string
  }
}
```

### NodeData 类型

```typescript
interface NodeData {
  nodes: string
  filename: string
  version: string
  node_type: string
  tokens: number
}
```

### Getters

| Getter | 参数 | 返回类型 | 描述 |
|--------|------|----------|------|
| `getChatByUuid` | `uuid: number` | `Chat[]` | 根据 UUID 获取聊天 |

### Actions

| Action | 参数 | 返回值 | 描述 |
|--------|------|--------|------|
| `addChat` | `chat: Chat` | `void` | 添加聊天 |
| `updateChat` | `uuid: number, index: number, chat: Partial<Chat>` | `void` | 更新聊天 |
| `updateChatSome` | `uuid: number, index: number, chat: Partial<Chat>` | `void` | 部分更新聊天 |
| `deleteChat` | `uuid: number, index: number` | `void` | 删除聊天 |
| `clearChat` | `uuid: number` | `void` | 清空聊天 |
| `updateNodeData` | `data: NodeData` | `void` | 更新节点数据 |
| `setNodeContextActive` | `active: boolean` | `void` | 设置节点上下文激活状态 |

### 使用示例

```typescript
import { useChatStore } from '@/store'

const chatStore = useChatStore()

// 获取状态
const chat = chatStore.getChatByUuid(1)
const nodeData = chatStore.nodeData
const nodeContextActive = chatStore.nodeContextActive

// 调用 action
chatStore.addChat({
  uuid: 1,
  dateTime: new Date().toLocaleString(),
  text: 'Hello',
  inversion: true,
  error: false,
  conversationOptions: null,
  requestOptions: { prompt: 'Hello' }
})

chatStore.updateChat(1, 0, { text: 'Updated text' })

chatStore.updateNodeData({
  nodes: 'node data',
  filename: 'file.blend',
  version: '4.2.0',
  node_type: 'Geometry Nodes',
  tokens: 1000
})

chatStore.setNodeContextActive(true)
```

---

## 4. Prompt Store

**文件**：`src/store/modules/prompt/index.ts`

**功能**：管理提示词状态。

### State

```typescript
{
  prompts: Prompt[]
}
```

### Prompt 类型

```typescript
interface Prompt {
  id: string
  title: string
  content: string
  category: string
  createdAt: string
  updatedAt: string
}
```

### Getters

| Getter | 返回类型 | 描述 |
|--------|----------|------|
| `getPromptById` | `id: string` | `Prompt \| undefined` | 根据 ID 获取提示词 |
| `getPromptsByCategory` | `category: string` | `Prompt[]` | 根据分类获取提示词 |

### Actions

| Action | 参数 | 返回值 | 描述 |
|--------|------|--------|------|
| `addPrompt` | `prompt: Prompt` | `void` | 添加提示词 |
| `updatePrompt` | `id: string, prompt: Partial<Prompt>` | `void` | 更新提示词 |
| `deletePrompt` | `id: string` | `void` | 删除提示词 |
| `setPrompts` | `prompts: Prompt[]` | `void` | 设置提示词列表 |

### 使用示例

```typescript
import { usePromptStore } from '@/store'

const promptStore = usePromptStore()

// 获取状态
const prompts = promptStore.prompts
const prompt = promptStore.getPromptById('1')
const categoryPrompts = promptStore.getPromptsByCategory('Geometry')

// 调用 action
promptStore.addPrompt({
  id: '1',
  title: '提示词1',
  content: '提示词内容',
  category: 'Geometry',
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString()
})

promptStore.updatePrompt('1', { title: '更新的标题' })
promptStore.deletePrompt('1')
promptStore.setPrompts([])
```

---

## 5. Settings Store

**文件**：`src/store/modules/settings/index.ts`

**功能**：管理设置状态。

### State

```typescript
{
  systemMessage: string
  systemMessagePresets: SystemMessagePreset[]
  outputDetailLevel: 'simple' | 'medium' | 'detailed'
  outputDetailPresets: OutputDetailPresets
  defaultQuestionPresets: DefaultQuestionPreset[]
  temperature: number
  top_p: number
  ai: AIConfig
  assistantAvatar: string
}
```

### SystemMessagePreset 类型

```typescript
interface SystemMessagePreset {
  label: string
  value: string
}
```

### OutputDetailPresets 类型

```typescript
interface OutputDetailPresets {
  simple: string
  medium: string
  detailed: string
}
```

### DefaultQuestionPreset 类型

```typescript
interface DefaultQuestionPreset {
  label: string
  value: string
}
```

### AIConfig 类型

```typescript
interface AIConfig {
  provider: string | {
    name: string
    model: string
  }
  deepseek?: {
    url: string
    api_key: string
    model: string
    models: string[]
  }
  ollama?: {
    url: string
    model: string
    models: string[]
  }
  bigmodel?: {
    url: string
    api_key: string
    model: string
    models: string[]
  }
  generic?: {
    base_url: string
    api_key: string
    model: string
    models: string[]
  }
  thinking?: {
    enabled: boolean
  }
  web_search?: {
    enabled: boolean
  }
  memory?: {
    enabled: boolean
    target_k: number
  }
}
```

### Getters

| Getter | 返回类型 | 描述 |
|--------|----------|------|
| `currentProvider` | `string` | 当前服务商 |
| `currentModel` | `string` | 当前模型 |

### Actions

| Action | 参数 | 返回值 | 描述 |
|--------|------|--------|------|
| `updateSetting` | `settings: Partial<Settings>` | `void` | 更新设置 |
| `resetSettings` | - | `void` | 重置设置 |

### 使用示例

```typescript
import { useSettingStore } from '@/store'

const settingStore = useSettingStore()

// 获取状态
const systemMessage = settingStore.systemMessage
const outputDetailLevel = settingStore.outputDetailLevel
const temperature = settingStore.temperature
const ai = settingStore.ai

// 调用 action
settingStore.updateSetting({
  systemMessage: '新的系统提示词',
  outputDetailLevel: 'detailed',
  temperature: 0.8,
  ai: {
    provider: 'DEEPSEEK',
    deepseek: {
      url: 'https://api.deepseek.com',
      api_key: 'your-api-key',
      model: 'deepseek-chat',
      models: ['deepseek-chat', 'deepseek-reasoner']
    }
  }
})

settingStore.resetSettings()
```

---

## 6. User Store

**文件**：`src/store/modules/user/index.ts`

**功能**：管理用户状态。

### State

```typescript
{
  userInfo: UserInfo | null
}
```

### UserInfo 类型

```typescript
interface UserInfo {
  id: string
  name: string
  avatar: string
  email: string
}
```

### Getters

| Getter | 返回类型 | 描述 |
|--------|----------|------|
| `isLoggedIn` | `boolean` | 是否已登录 |

### Actions

| Action | 参数 | 返回值 | 描述 |
|--------|------|--------|------|
| `updateUserInfo` | `userInfo: UserInfo` | `void` | 更新用户信息 |
| `clearUserInfo` | - | `void` | 清空用户信息 |

### 使用示例

```typescript
import { useUserStore } from '@/store'

const userStore = useUserStore()

// 获取状态
const userInfo = userStore.userInfo
const isLoggedIn = userStore.isLoggedIn

// 调用 action
userStore.updateUserInfo({
  id: '1',
  name: 'User',
  avatar: 'avatar.png',
  email: 'user@example.com'
})

userStore.clearUserInfo()
```

---

## Store 持久化

### 配置

```typescript
import { createPinia } from 'pinia'
import { createPersistedState } from 'pinia-plugin-persistedstate'

const pinia = createPinia()
pinia.use(createPersistedState({
  key: 'ainode',
  storage: localStorage
}))
```

### 持久化配置

```typescript
export const useChatStore = defineStore('chat', {
  state: () => ({
    chat: {},
    nodeData: {},
    nodeContextActive: false
  }),
  persist: {
    key: 'ainode-chat',
    storage: localStorage,
    paths: ['chat']
  }
})
```

---

## Store 模块化

### 模块导入

```typescript
// src/store/index.ts
export * from './modules/app'
export * from './modules/auth'
export * from './modules/chat'
export * from './modules/prompt'
export * from './modules/settings'
export * from './modules/user'
```

### 统一导出

```typescript
// src/store/helper.ts
import { createPinia } from 'pinia'

const pinia = createPinia()

export function setupStore(app: App) {
  app.use(pinia)
}

export { pinia }
```

---

## Store 最佳实践

1. **命名规范**：使用 camelCase 命名 state 和 actions
2. **类型定义**：使用 TypeScript 定义类型
3. **模块化**：按功能拆分 store 模块
4. **持久化**：只持久化必要的数据
5. **Getter 使用**：使用 getter 计算派生状态
6. **Action 封装**：在 action 中处理复杂逻辑
7. **错误处理**：在 action 中添加错误处理

---

## Store 文档索引

- [01-主界面文档](./01-主界面文档.md)
- [02-组件文档](./02-组件文档.md)
- [03-Store 文档](./03-Store文档.md)
- [04-API 文档](./04-API文档.md)
- [05-Hooks 文档](./05-Hooks文档.md)
- [06-路由文档](./06-路由文档.md)