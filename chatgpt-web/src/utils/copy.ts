export function copyToClip(text: string) {
  return new Promise((resolve, reject) => {
    // 优先使用 Clipboard API
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text)
        .then(() => resolve(text))
        .catch((err) => {
          // Clipboard API 失败，尝试降级方案
          fallbackCopy(text, resolve, reject)
        })
    } else {
      fallbackCopy(text, resolve, reject)
    }
  })
}

function fallbackCopy(text: string, resolve: (val: any) => void, reject: (reason: any) => void) {
  try {
    const input = document.createElement('textarea')
    input.setAttribute('readonly', 'readonly')
    input.value = text
    // 防止页面滚动和闪烁
    input.style.position = 'fixed'
    input.style.left = '-9999px'
    input.style.top = '0'
    document.body.appendChild(input)
    
    input.focus()
    input.select()
    input.setSelectionRange(0, 99999) // 适配移动端
    
    const successful = document.execCommand('copy')
    document.body.removeChild(input)
    
    if (successful)
      resolve(text)
    else
      reject(new Error('Copy command failed'))
  } catch (error) {
    reject(error)
  }
}
