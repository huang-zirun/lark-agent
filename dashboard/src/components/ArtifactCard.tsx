import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { FileText, Eye } from "lucide-react"

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

export function ArtifactCard({ stage, artifact, onViewDetail }: ArtifactCardProps) {
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
