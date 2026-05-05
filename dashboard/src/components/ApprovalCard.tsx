import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { CheckCircle2, XCircle, Clock, AlertTriangle } from "lucide-react"
import type { CheckpointRecord } from "@/hooks/useRunDetail"

const STAGE_DISPLAY_NAMES: Record<string, string> = {
  solution_design: "方案设计审批",
  code_review: "代码评审审批",
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case "waiting_approval":
    case "waiting_approval_with_warnings":
      return (
        <Badge variant="warning" className="gap-1">
          <Clock className="h-3 w-3" />
          等待审批
        </Badge>
      )
    case "approved":
      return (
        <Badge variant="success" className="gap-1">
          <CheckCircle2 className="h-3 w-3" />
          已批准
        </Badge>
      )
    case "approved_with_override":
      return (
        <Badge variant="warning" className="gap-1">
          <AlertTriangle className="h-3 w-3" />
          强制通过
        </Badge>
      )
    case "rejected":
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" />
          已拒绝
        </Badge>
      )
    case "awaiting_reject_reason":
      return (
        <Badge variant="warning" className="gap-1">
          <Clock className="h-3 w-3" />
          等待拒绝理由
        </Badge>
      )
    default:
      return <Badge variant="outline">{status}</Badge>
  }
}

interface ApprovalCardProps {
  checkpoint: CheckpointRecord
}

export function ApprovalCard({ checkpoint }: ApprovalCardProps) {
  const isWaiting =
    checkpoint.status === "waiting_approval" ||
    checkpoint.status === "waiting_approval_with_warnings"
  const stageName = STAGE_DISPLAY_NAMES[checkpoint.stage] ?? checkpoint.stage
  const reviewerText = checkpoint.reviewer
    ? typeof checkpoint.reviewer === "string"
      ? checkpoint.reviewer
      : String((checkpoint.reviewer as Record<string, unknown>).source ?? JSON.stringify(checkpoint.reviewer))
    : null
  const warnings = (checkpoint.quality_snapshot?.warnings ?? []) as string[]

  return (
    <Card className={isWaiting ? "border-l-4 border-l-amber-500" : ""}>
      <CardContent className="p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="font-medium text-sm">{stageName}</span>
          <StatusBadge status={checkpoint.status} />
        </div>

        {reviewerText && (
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">审批人</span>
            <span>{reviewerText}</span>
          </div>
        )}

        {checkpoint.updated_at && (
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">审批时间</span>
            <span>{checkpoint.updated_at}</span>
          </div>
        )}

        {checkpoint.reject_reason && (
          <div className="text-sm">
            <span className="text-muted-foreground">拒绝理由：</span>
            <span>{checkpoint.reject_reason}</span>
          </div>
        )}

        {warnings.length > 0 && (
          <div className="text-sm">
            <span className="text-muted-foreground">质量警告：</span>
            <ul className="list-disc list-inside mt-1 space-y-0.5">
              {warnings.map((w: string, i: number) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        )}

        {checkpoint.override_reason && (
          <div className="text-sm">
            <span className="text-muted-foreground">强制通过理由：</span>
            <span>{checkpoint.override_reason}</span>
          </div>
        )}

        {isWaiting && (
          <p className="text-xs text-amber-500/80 font-mono">
            可通过 API 审批：POST /api/v1/pipelines/{checkpoint.run_id}/checkpoint
          </p>
        )}
      </CardContent>
    </Card>
  )
}
