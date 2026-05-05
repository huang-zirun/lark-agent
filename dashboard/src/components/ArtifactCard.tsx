import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible"
import { FileText, Eye, ChevronDown } from "lucide-react"
import { useRunArtifactMarkdown } from "@/hooks/useRunDetail"

const STAGE_DISPLAY_NAMES: Record<string, string> = {
  requirement_intake: "需求分析",
  solution_design: "方案设计",
  code_generation: "代码生成",
  test_generation: "测试生成",
  code_review: "代码评审",
  delivery: "交付",
}

interface ArtifactCardProps {
  stage: string
  artifact: Record<string, unknown> | undefined
  runId: string | null
  onViewDetail: () => void
}

function RequirementIntakeContent({ artifact }: { artifact: Record<string, unknown> }) {
  return (
    <>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">标题</span>
        <span>{String(artifact.title ?? "-")}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">验收标准数</span>
        <span>{String(artifact.acceptance_criteria_count ?? "-")}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">质量评分</span>
        <span>{String(artifact.quality_score ?? "-")}</span>
      </div>
    </>
  )
}

function SolutionDesignContent({ artifact }: { artifact: Record<string, unknown> }) {
  const ready = artifact.ready_for_code_generation
  return (
    <>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">摘要</span>
        <span className="max-w-[200px] truncate">{String(artifact.summary ?? "-")}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">变更计划数</span>
        <span>{String(artifact.change_plan_count ?? "-")}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">风险等级</span>
        <span>{String(artifact.risk_level ?? "-")}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">代码生成就绪</span>
        <Badge variant={ready ? "success" : "destructive"}>
          {ready ? "就绪" : "未就绪"}
        </Badge>
      </div>
    </>
  )
}

function CodeGenerationContent({ artifact }: { artifact: Record<string, unknown> }) {
  const changedFiles = (artifact.changed_files as string[]) ?? []
  const diffStats = artifact.diff_stats as { additions?: number; deletions?: number } | undefined
  return (
    <>
      <div className="text-sm text-muted-foreground">变更文件</div>
      <ul className="text-xs space-y-0.5 mt-1">
        {changedFiles.slice(0, 5).map((f, i) => (
          <li key={i} className="truncate font-mono">{f}</li>
        ))}
        {changedFiles.length > 5 && (
          <li className="text-muted-foreground">...还有 {changedFiles.length - 5} 个文件</li>
        )}
      </ul>
      <div className="flex justify-between text-sm mt-2">
        <span className="text-muted-foreground">Diff 统计</span>
        <span>
          <span className="text-emerald-400">+{diffStats?.additions ?? 0}</span>{" "}
          <span className="text-red-400">-{diffStats?.deletions ?? 0}</span>
        </span>
      </div>
    </>
  )
}

function TestGenerationContent({ artifact }: { artifact: Record<string, unknown> }) {
  return (
    <>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">技术栈</span>
        <span>{String(artifact.detected_stack ?? "-")}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">测试数量</span>
        <span>{String(artifact.test_count ?? "-")}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">测试结果</span>
        <span>{String(artifact.test_results_summary ?? "-")}</span>
      </div>
    </>
  )
}

function CodeReviewContent({ artifact }: { artifact: Record<string, unknown> }) {
  return (
    <>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">评审状态</span>
        <span>{String(artifact.review_status ?? "-")}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">阻断发现</span>
        <span>{String(artifact.blocking_findings ?? "-")}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">风险等级</span>
        <span>{String(artifact.risk_level ?? "-")}</span>
      </div>
    </>
  )
}

function DeliveryContent({ artifact }: { artifact: Record<string, unknown> }) {
  const mergeReadiness = artifact.merge_readiness
  return (
    <>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">变更摘要</span>
        <span className="max-w-[200px] truncate">{String(artifact.change_summary ?? "-")}</span>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">合并就绪</span>
        <Badge variant={mergeReadiness ? "success" : "destructive"}>
          {mergeReadiness ? "是" : "否"}
        </Badge>
      </div>
      <div className="flex justify-between text-sm">
        <span className="text-muted-foreground">Git 分支</span>
        <span className="font-mono text-xs">{String(artifact.git_branch ?? "-")}</span>
      </div>
    </>
  )
}

const STAGE_CONTENT_MAP: Record<string, React.ComponentType<{ artifact: Record<string, unknown> }>> = {
  requirement_intake: RequirementIntakeContent,
  solution_design: SolutionDesignContent,
  code_generation: CodeGenerationContent,
  test_generation: TestGenerationContent,
  code_review: CodeReviewContent,
  delivery: DeliveryContent,
}

function simpleMarkdownToHtml(md: string): string {
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

function ArtifactMarkdownSection({ runId, stage }: { runId: string; stage: string }) {
  const { data, loading } = useRunArtifactMarkdown(runId, stage)
  const [expanded, setExpanded] = useState(false)

  if (loading) return <div className="h-8 bg-muted/20 rounded animate-pulse mt-2" />
  if (!data) return null

  const lines = data.split('\n')
  const previewLines = lines.slice(0, 10)
  const needsExpand = lines.length > 10

  return (
    <Collapsible open={expanded} onOpenChange={setExpanded} className="mt-3">
      <div className="border rounded-md p-3 bg-muted/10">
        <div
          className="prose prose-sm dark:prose-invert max-w-none text-xs"
          dangerouslySetInnerHTML={{ __html: simpleMarkdownToHtml(expanded ? data : previewLines.join('\n')) }}
        />
      </div>
      {needsExpand && (
        <CollapsibleTrigger asChild>
          <Button variant="ghost" size="sm" className="w-full mt-1 h-7 text-xs">
            <ChevronDown className={`h-3.5 w-3.5 mr-1 transition-transform ${expanded ? "rotate-180" : ""}`} />
            {expanded ? "收起" : "展开全文"}
          </Button>
        </CollapsibleTrigger>
      )}
    </Collapsible>
  )
}

export function ArtifactCard({ stage, artifact, runId, onViewDetail }: ArtifactCardProps) {
  const displayName = STAGE_DISPLAY_NAMES[stage] ?? stage
  const ContentComponent = STAGE_CONTENT_MAP[stage]

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base">
          <FileText className="h-4 w-4" />
          {displayName}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {artifact && ContentComponent ? (
          <div className="space-y-2">
            <ContentComponent artifact={artifact} />
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">暂无产物</p>
        )}
        {runId && (
          <ArtifactMarkdownSection runId={runId} stage={stage} />
        )}
        <div className="flex justify-end mt-4">
          <Button variant="outline" size="sm" onClick={onViewDetail}>
            <Eye className="h-3.5 w-3.5 mr-1" />
            查看详情
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
