export function stripMarkdown(input: string): string {
  let s = input || ''
  s = s.replace(/\r\n/g, '\n')
  s = s.replace(/```[\s\S]*?```/g, (m) => {
    const inner = m.replace(/```/g, '').trim()
    return '\n' + inner + '\n'
  })
  s = s.replace(/`([^`]+)`/g, '$1')
  s = s.replace(/^#{1,6}\s+/gm, '')
  s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (m, alt, url) => `[image: ${alt} ${url}]`)
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1 ($2)')
  s = s.replace(/^\s*>\s?/gm, '')
  s = s.replace(/^\s*-\s+/gm, '- ')
  s = s.replace(/^\s*\*\s+/gm, '- ')
  s = s.replace(/^\s*\d+\.\s+/gm, (m) => m.trim() + ' ')
  s = s.replace(/^\s*\|.+\|\s*$/gm, (m) => m.replace(/\|/g, ' ').trim())
  s = s.replace(/\*\*([^*]+)\*\*/g, '$1')
  s = s.replace(/\*([^*]+)\*/g, '$1')
  s = s.replace(/__([^_]+)__/g, '$1')
  s = s.replace(/_([^_]+)_/g, '$1')
  s = s.replace(/\n{3,}/g, '\n\n')
  return s.trim()
}
