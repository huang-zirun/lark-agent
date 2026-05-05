import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Play, Pause, CheckCircle2, XCircle, AlertTriangle, Eye } from "lucide-react";
import type { RecentRun } from "@/hooks/useMetrics";

interface RecentRunsTableProps {
  data: RecentRun[] | null;
  loading: boolean;
  onViewDetail: (runId: string) => void;
}

function statusBadge(status: string) {
  switch (status) {
    case "running":
      return (
        <Badge variant="cyan" className="gap-1">
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-cyan-400" />
          </span>
          运行中
        </Badge>
      );
    case "paused":
      return (
        <Badge variant="warning" className="gap-1">
          <Pause className="h-3 w-3" />
          已暂停
        </Badge>
      );
    case "success":
    case "delivered":
      return (
        <Badge variant="success" className="gap-1">
          <CheckCircle2 className="h-3 w-3" />
          成功
        </Badge>
      );
    case "failed":
    case "error":
      return (
        <Badge variant="destructive" className="gap-1">
          <XCircle className="h-3 w-3" />
          失败
        </Badge>
      );
    default:
      return (
        <Badge variant="secondary" className="gap-1">
          <AlertTriangle className="h-3 w-3" />
          {status}
        </Badge>
      );
  }
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 3600000) return `${(ms / 60000).toFixed(1)}m`;
  return `${(ms / 3600000).toFixed(1)}h`;
}

function formatTime(iso: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function RecentRunsTable({ data, loading, onViewDetail }: RecentRunsTableProps) {
  return (
    <Card className="border-border bg-card/50 backdrop-blur-sm">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          最近 Pipeline 运行
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[400px]">
          {loading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-12 bg-muted/20 rounded animate-pulse" />
              ))}
            </div>
          ) : !data || data.length === 0 ? (
            <div className="p-12 text-center text-muted-foreground text-sm">
              暂无运行数据
            </div>
          ) : (
            <div className="min-w-[600px]">
              <div className="grid grid-cols-[1fr_100px_120px_100px_100px_80px] gap-4 px-6 py-3 text-xs font-medium text-muted-foreground bg-muted/30">
                <span>运行 ID</span>
                <span>状态</span>
                <span>阶段</span>
                <span>Provider</span>
                <span>耗时</span>
                <span className="text-right">操作</span>
              </div>
              <Separator />
              {data.map((run, index) => (
                <div
                  key={run.run_id}
                  className="grid grid-cols-[1fr_100px_120px_100px_100px_80px] gap-4 px-6 py-3 text-sm items-center hover:bg-muted/30 transition-colors border-l-[3px] border-transparent hover:border-cyan-400 animate-slide-up"
                  style={{ animationDelay: `${index * 30}ms` }}
                >
                  <div className="font-mono text-xs text-foreground truncate">
                    {run.run_id}
                  </div>
                  <div>{statusBadge(run.status)}</div>
                  <div className="text-muted-foreground text-xs truncate">
                    {run.current_stage || "-"}
                  </div>
                  <div className="text-muted-foreground text-xs">
                    {run.provider_override || "default"}
                  </div>
                  <div className="text-muted-foreground text-xs">
                    {formatDuration(run.duration_ms)}
                  </div>
                  <div className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 px-2 text-xs text-cyan-400 hover:text-cyan-300 hover:bg-cyan-400/10"
                      onClick={() => onViewDetail(run.run_id)}
                    >
                      <Eye className="h-3.5 w-3.5 mr-1" />
                      详情
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
