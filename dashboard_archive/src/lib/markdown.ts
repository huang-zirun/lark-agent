export function simpleMarkdownToHtml(md: string): string {
  let html = md
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  html = html.replace(/```[\s\S]*?```/g, (match) => {
    const code = match.replace(/```\w*\n?/, '').replace(/\n?```$/, '')
    return `<pre><code>${code}</code></pre>`
  })
  html = html.replace(/^(#{1,3}) (.+)$/gm, (_, hashes: string, text: string) => {
    const level = hashes.length
    return `<h${level}>${text}</h${level}>`
  })
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>')
  html = html.replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
  html = html.replace(/^(\d+)\. (.+)$/gm, '<li>$2</li>')
  const tableBlockRegex = /(^|\n)((?:\|.+\|\n)+)/g
  html = html.replace(tableBlockRegex, (_: string, prefix: string, block: string) => {
    const rows = block.trim().split('\n')
    let tableHtml = '<table>'
    rows.forEach((row: string, idx: number) => {
      if (/^\|[\s\-:|]+\|$/.test(row)) return
      const cells = row.split('|').filter((c: string) => c.trim() !== '')
      const tag = idx === 0 ? 'th' : 'td'
      tableHtml += '<tr>' + cells.map((c: string) => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>'
    })
    tableHtml += '</table>'
    return prefix + tableHtml
  })
  html = html.replace(/\n\n/g, '</p><p>')
  html = html.replace(/\n/g, '<br/>')
  return `<p>${html}</p>`
}
