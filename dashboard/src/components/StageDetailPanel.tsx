import type {
  StageInfo,
  TokenSummary,
  LlmCallRecord,
} from "@/hooks/useRunDetail";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Clock, Cpu, Zap, Activity } from "lucide-react";

// eslint-disable-next-line react-refresh/only-export-components
export const STAGE_DISPLAY_NAMES: Record<string, string> = {
  requirement_intake: "需求分析",
  solution_design: "方案设计",
  code_generation: "代码生成",
  test_generation: "测试生成",
  code_review: "代码评审",
  delivery: "交付",
};

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainSeconds}s`;
  const hours = Math.floor(minutes / 60);
  const remainMinutes = minutes % 60;
  return `${hours}h ${remainMinutes}m`;
}

function getStatusBadgeVariant(
  status: string
): "default" | "success" | "destructive" | "warning" | "cyan" | "secondary" | "outline" {
  switch (status) {
    case "running":
      return "cyan";
    case "success":
      return "success";
    case "failed":
      return "destructive";
    case "blocked":
      return "warning";
    default:
      return "secondary";
  }
}

function getStatusLabel(status: string): string {
  switch (status) {
    case "running":
      return "运行中";
    case "success":
      return "已完成";
    case "failed":
      return "失败";
    case "blocked":
      return "已阻塞";
    case "pending":
      return "等待中";
    default:
      return status;
  }
}

interface StageDetailPanelProps {
  stages: StageInfo[];
  tokenSummary: TokenSummary | Record<string, never>;
  selectedStage: string | null;
  llmCalls: LlmCallRecord[] | null;
}

export function StageDetailPanel({
  stages,
  tokenSummary,
  selectedStage: _selectedStage,
  llmCalls,
}: StageDetailPanelProps) {
  void _selectedStage;

  return (
    <div className="space-y-4">
      {stages.map((stage) => {
        const displayName = STAGE_DISPLAY_NAMES[stage.name] ?? stage.name;
        const tokenInfo = tokenSummary[stage.name];

        return (
          <Card key={stage.name}>
              <CardHeader className="pb-3">
                <CardTitle className="flex items-center justify-between text-base">
                  <span className="flex items-center gap-2">
                    <Activity className="h-4 w-4" />
                    {displayName}
                  </span>
                  <Badge variant={getStatusBadgeVariant(stage.status)}>
                    {getStatusLabel(stage.status)}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  {stage.duration_ms != null && (
                    <div className="flex items-center gap-2">
                      <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="text-muted-foreground">耗时</span>
                      <span>{formatDuration(stage.duration_ms)}</span>
                    </div>
                  )}
                  {tokenInfo?.model && (
                    <div className="flex items-center gap-2">
                      <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
                      <span className="text-muted-foreground">模型</span>
                      <span className="font-mono text-xs">{tokenInfo.model}</span>
                    </div>
                  )}
                  {(() => {
                    const stageLlmDuration = llmCalls
                      ?.filter(c => c.stage === stage.name || stage.name.startsWith(c.stage) || c.stage.startsWith(stage.name))
                      .reduce((sum, c) => sum + (c.duration_ms ?? 0), 0);
                    return stageLlmDuration && stageLlmDuration > 0 ? (
                      <div className="flex items-center gap-2">
                        <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="text-muted-foreground">LLM 耗时</span>
                        <span>{formatDuration(stageLlmDuration)}</span>
                      </div>
                    ) : null;
                  })()}
                  {tokenInfo && (
                    <>
                      <div className="flex items-center gap-2">
                        <Zap className="h-3.5 w-3.5 text-muted-foreground" />
                        <span className="text-muted-foreground">Token</span>
                        <span>
                          prompt: {tokenInfo.prompt_tokens} / completion:{" "}
                          {tokenInfo.completion_tokens} / total:{" "}
                          {tokenInfo.total_tokens}
                        </span>
                      </div>
                      {tokenInfo.provider && (
                        <div className="flex items-center gap-2">
                          <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
                          <span className="text-muted-foreground">Provider</span>
                          <span>{tokenInfo.provider}</span>
                        </div>
                      )}
                    </>
                  )}
                </div>
              </CardContent>
            </Card>
        );
      })}
    </div>
  );
}
