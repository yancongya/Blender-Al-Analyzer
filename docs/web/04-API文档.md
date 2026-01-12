# Web API 文档

## API 概述

Web 前端通过 Axios 与后端 Flask 服务器通信，API 函数位于 `src/api/index.ts`。

## API 函数列表

| 函数 | 方法 | 路径 | 功能 |
|------|------|------|------|
| `fetchChatAPI` | POST | `/chat` | 聊天 API |
| `fetchChatConfig` | POST | `/config` | 获取配置 |
| `fetchBlenderData` | GET | `/blender-data` | 获取 Blender 数据 |
| `fetchChatAPIProcess` | POST | `/stream-analyze` | 流式分析 |
| `fetchSession` | POST | `/session` | 获取会话 |
| `fetchVerify` | POST | `/verify` | 验证令牌 |
| `fetchUiConfig` | GET | `/ui-config` | 获取 UI 配置 |
| `triggerRefresh` | POST | `/trigger-refresh` | 触发刷新 |
| `updateSettings` | POST | `/save-ui-config` | 保存设置 |
| `fetchPromptTemplates` | GET | `/prompt-templates` | 获取提示词模板 |
| `savePromptTemplates` | POST | `/save-prompt-templates` | 保存提示词模板 |
| `importPromptTemplates` | POST | `/import-prompt-templates` | 导入提示词模板 |
| `fetchDefaultPromptTemplates` | GET | `/default-prompt-templates` | 获取默认提示词模板 |
| `sendSelectionToBlender` | POST | `/create-annotation` | 创建注释 |
| `updateBlenderAnnotation` | POST | `/update-annotation` | 更新注释 |
| `openBlenderAnnotationEditor` | POST | `/open-annotation-editor` | 打开注释编辑器 |
| `fitBlenderAnnotation` | POST | `/fit-annotation` | 适应注释 |
| `fetchProviderModels` | POST | `/provider-list-models` | 获取服务商模型列表 |

---

## 1. fetchChatAPI

**功能**：聊天 API，发送消息到 AI。

### 请求

```typescript
fetchChatAPI(prompt: string, options?: {
  conversationId?: string
  parentMessageId?: string
}, signal?: GenericAbortSignal)
```

### 参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `prompt` | `string` | 是 | 用户输入 |
| `options.conversationId` | `string` | 否 | 对话 ID |
| `options.parentMessageId` | `string` | 否 | 父消息 ID |
| `signal` | `GenericAbortSignal` | 否 | 中止信号 |

### 返回值

```typescript
Promise<ChatResponse>
```

### 使用示例

```typescript
import { fetchChatAPI } from '@/api'

const response = await fetchChatAPI('你好', {
  conversationId: 'conv-123'
})
```

---

## 2. fetchChatConfig

**功能**：获取聊天配置。

### 请求

```typescript
fetchChatConfig()
```

### 返回值

```typescript
Promise<ConfigResponse>
```

### 使用示例

```typescript
import { fetchChatConfig } from '@/api'

const config = await fetchChatConfig()
```

---

## 3. fetchBlenderData

**功能**：获取 Blender 节点数据。

### 请求

```typescript
fetchBlenderData()
```

### 返回值

```typescript
Promise<BlenderDataResponse>
```

### BlenderDataResponse 类型

```typescript
interface BlenderDataResponse {
  nodes: string
  filename: string
  version: string
  node_type: string
  tokens: number
}
```

### 使用示例

```typescript
import { fetchBlenderData } from '@/api'

const nodeData = await fetchBlenderData()
console.log(nodeData.nodes)
```

---

## 4. fetchChatAPIProcess

**功能**：流式分析 API，发送消息并接收流式响应。

### 请求

```typescript
fetchChatAPIProcess(params: {
  prompt: string
  options?: {
    conversationId?: string
    parentMessageId?: string
    content?: string
  }
  signal?: GenericAbortSignal
  onDownloadProgress?: (progressEvent: AxiosProgressEvent) => void
})
```

### 参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `prompt` | `string` | 是 | 用户输入 |
| `options.conversationId` | `string` | 否 | 对话 ID |
| `options.parentMessageId` | `string` | 否 | 父消息 ID |
| `options.content` | `string` | 否 | 节点内容 |
| `signal` | `GenericAbortSignal` | 否 | 中止信号 |
| `onDownloadProgress` | `function` | 否 | 下载进度回调 |

### 返回值

```typescript
Promise<StreamResponse>
```

### 使用示例

```typescript
import { fetchChatAPIProcess } from '@/api'

const controller = new AbortController()

await fetchChatAPIProcess({
  prompt: '分析这个节点',
  signal: controller.signal,
  onDownloadProgress: (progressEvent) => {
    const xhr = progressEvent.event.target
    console.log(xhr.responseText)
  }
})
```

---

## 5. fetchSession

**功能**：获取会话信息。

### 请求

```typescript
fetchSession()
```

### 返回值

```typescript
Promise<SessionResponse>
```

### 使用示例

```typescript
import { fetchSession } from '@/api'

const session = await fetchSession()
```

---

## 6. fetchVerify

**功能**：验证令牌。

### 请求

```typescript
fetchVerify(token: string)
```

### 参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `token` | `string` | 是 | 令牌 |

### 返回值

```typescript
Promise<VerifyResponse>
```

### 使用示例

```typescript
import { fetchVerify } from '@/api'

const result = await fetchVerify('your-token')
```

---

## 7. fetchUiConfig

**功能**：获取 UI 配置。

### 请求

```typescript
fetchUiConfig()
```

### 返回值

```typescript
Promise<UiConfigResponse>
```

### UiConfigResponse 类型

```typescript
interface UiConfigResponse {
  title: string
  icon: string
  user: UserInfo
  assistant: AssistantInfo
  system_message_presets: SystemMessagePreset[]
  default_question_presets: DefaultQuestionPreset[]
  default_questions: string[]
  output_detail_presets: OutputDetailPresets
  output_detail_level: string
  system_prompt: string
  ai: AIConfig
}
```

### 使用示例

```typescript
import { fetchUiConfig } from '@/api'

const config = await fetchUiConfig()
console.log(config.title)
```

---

## 8. triggerRefresh

**功能**：触发 Blender 刷新。

### 请求

```typescript
triggerRefresh()
```

### 返回值

```typescript
Promise<RefreshResponse>
```

### 使用示例

```typescript
import { triggerRefresh } from '@/api'

await triggerRefresh()
```

---

## 9. updateSettings

**功能**：保存设置到后端。

### 请求

```typescript
updateSettings(settings: Record<string, any>)
```

### 参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `settings` | `Record<string, any>` | 是 | 设置对象 |

### 返回值

```typescript
Promise<UpdateSettingsResponse>
```

### 使用示例

```typescript
import { updateSettings } from '@/api'

await updateSettings({
  systemMessage: '新的系统提示词',
  outputDetailLevel: 'detailed'
})
```

---

## 10. fetchPromptTemplates

**功能**：获取提示词模板。

### 请求

```typescript
fetchPromptTemplates()
```

### 返回值

```typescript
Promise<PromptTemplatesResponse>
```

### 使用示例

```typescript
import { fetchPromptTemplates } from '@/api'

const templates = await fetchPromptTemplates()
```

---

## 11. savePromptTemplates

**功能**：保存提示词模板。

### 请求

```typescript
savePromptTemplates(templates: any)
```

### 参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `templates` | `any` | 是 | 提示词模板 |

### 返回值

```typescript
Promise<SavePromptTemplatesResponse>
```

### 使用示例

```typescript
import { savePromptTemplates } from '@/api'

await savePromptTemplates({
  templates: [
    { id: '1', title: '提示词1', content: '内容' }
  ]
})
```

---

## 12. importPromptTemplates

**功能**：从 URL 导入提示词模板。

### 请求

```typescript
importPromptTemplates(url: string)
```

### 参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `url` | `string` | 是 | 模板 URL |

### 返回值

```typescript
Promise<ImportPromptTemplatesResponse>
```

### 使用示例

```typescript
import { importPromptTemplates } from '@/api'

await importPromptTemplates('https://example.com/templates.json')
```

---

## 13. fetchDefaultPromptTemplates

**功能**：获取默认提示词模板。

### 请求

```typescript
fetchDefaultPromptTemplates()
```

### 返回值

```typescript
Promise<DefaultPromptTemplatesResponse>
```

### 使用示例

```typescript
import { fetchDefaultPromptTemplates } from '@/api'

const templates = await fetchDefaultPromptTemplates()
```

---

## 14. sendSelectionToBlender

**功能**：将选中的文本发送到 Blender 创建注释。

### 请求

```typescript
sendSelectionToBlender(text: string)
```

### 参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `text` | `string` | 是 | 要发送的文本 |

### 返回值

```typescript
Promise<SendSelectionResponse>
```

### 使用示例

```typescript
import { sendSelectionToBlender } from '@/api'

await sendSelectionToBlender('要创建的注释内容')
```

---

## 15. updateBlenderAnnotation

**功能**：更新 Blender 中的注释。

### 请求

```typescript
updateBlenderAnnotation(text: string)
```

### 参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `text` | `string` | 是 | 更新的文本 |

### 返回值

```typescript
Promise<UpdateAnnotationResponse>
```

### 使用示例

```typescript
import { updateBlenderAnnotation } from '@/api'

await updateBlenderAnnotation('更新的注释内容')
```

---

## 16. openBlenderAnnotationEditor

**功能**：在 Blender 中打开注释编辑器。

### 请求

```typescript
openBlenderAnnotationEditor()
```

### 返回值

```typescript
Promise<OpenEditorResponse>
```

### 使用示例

```typescript
import { openBlenderAnnotationEditor } from '@/api'

await openBlenderAnnotationEditor()
```

---

## 17. fitBlenderAnnotation

**功能**：适应 Blender 注释大小。

### 请求

```typescript
fitBlenderAnnotation()
```

### 返回值

```typescript
Promise<FitAnnotationResponse>
```

### 使用示例

```typescript
import { fitBlenderAnnotation } from '@/api'

await fitBlenderAnnotation()
```

---

## 18. fetchProviderModels

**功能**：获取服务商的模型列表。

### 请求

```typescript
fetchProviderModels(provider: string)
```

### 参数

| 参数 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `provider` | `string` | 是 | 服务商名称 |

### 返回值

```typescript
Promise<ProviderModelsResponse>
```

### 使用示例

```typescript
import { fetchProviderModels } from '@/api'

const models = await fetchProviderModels('DEEPSEEK')
console.log(models)
```

---

## 请求工具

### get

```typescript
get<T = any>(config: AxiosRequestConfig)
```

### post

```typescript
post<T = any>(config: AxiosRequestConfig)
```

### 使用示例

```typescript
import { get, post } from '@/utils/request'

// GET 请求
const data = await get({ url: '/api/data' })

// POST 请求
const result = await post({
  url: '/api/create',
  data: { name: 'test' }
})
```

---

## 错误处理

### 统一错误处理

```typescript
import { fetchChatAPI } from '@/api'

try {
  const response = await fetchChatAPI('你好')
  console.log(response)
}
catch (error) {
  console.error('请求失败:', error)
}
```

### 错误类型

| 错误类型 | 描述 |
|----------|------|
| `AxiosError` | Axios 请求错误 |
| `NetworkError` | 网络错误 |
| `TimeoutError` | 超时错误 |
| `ServerError` | 服务器错误 |

---

## API 文档索引

- [01-主界面文档](./01-主界面文档.md)
- [02-组件文档](./02-组件文档.md)
- [03-Store 文档](./03-Store文档.md)
- [04-API 文档](./04-API文档.md)
- [05-Hooks 文档](./05-Hooks文档.md)
- [06-路由文档](./06-路由文档.md)