import { useState } from "react"
import { Button } from "@/components/ui/button"
import { ChevronDown, ChevronUp, FileCode } from "lucide-react"

interface DiffViewerProps {
  content: string | null
  loading: boolean
  defaultExpanded?: boolean
}

function getLineStyle(line: string) {
  if (line.startsWith("@@")) return "text-cyan-400"
  if (line.startsWith("+")) return "text-emerald-400 bg-emerald-400/5"
  if (line.startsWith("-")) return "text-red-400 bg-red-400/5"
  return ""
}

export function DiffViewer({ content, loading, defaultExpanded = false }: DiffViewerProps) {
  const [expanded, setExpanded] = useState(defaultExpanded)

  if (loading) {
    return (
      <div className="rounded-lg border border-border bg-card p-4 space-y-2">
        <div className="h-4 w-32 bg-muted animate-pulse rounded" />
        <div className="space-y-1">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-3 bg-muted animate-pulse rounded" />
          ))}
        </div>
      </div>
    )
  }

  if (!content) {
    return (
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">暂无 Diff 数据</p>
      </div>
    )
  }

  const lines = content.split("\n")
  const previewLines = lines.slice(0, 20)
  const hasMore = lines.length > 20
  const displayLines = expanded ? lines : previewLines

  return (
    <div className="rounded-lg border border-border bg-card">
      <div className="flex items-center justify-between p-3 border-b border-border">
        <div className="flex items-center gap-2 text-sm font-medium">
          <FileCode className="h-4 w-4" />
          Diff 预览
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? (
            <>
              <ChevronUp className="h-3.5 w-3.5 mr-1" />
              收起
            </>
          ) : (
            <>
              <ChevronDown className="h-3.5 w-3.5 mr-1" />
              展开全部
            </>
          )}
        </Button>
      </div>
      <div className="p-3 overflow-x-auto">
        <pre className="font-mono text-xs leading-5 space-y-0">
          {displayLines.map((line, i) => (
            <div key={i} className={`px-2 rounded ${getLineStyle(line)}`}>
              {line}
            </div>
          ))}
        </pre>
      </div>
      {!expanded && hasMore && (
        <div className="flex justify-center p-2 border-t border-border">
          <Button variant="ghost" size="sm" onClick={() => setExpanded(true)}>
            <ChevronDown className="h-3.5 w-3.5 mr-1" />
            展开全部
          </Button>
        </div>
      )}
    </div>
  )
}
