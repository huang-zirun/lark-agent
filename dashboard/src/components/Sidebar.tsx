import { GitBranch } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { RunListItem } from "@/hooks/useRunDetail";

interface SidebarProps {
  runs: RunListItem[] | null;
  selectedRunId: string | null;
  loading: boolean;
  onSelectRun: (runId: string) => void;
}

function statusBadge(status: string) {
  switch (status) {
    case "running":
      return <Badge variant="cyan">运行中</Badge>;
    case "paused":
      return <Badge variant="warning">已暂停</Badge>;
    case "success":
    case "delivered":
      return <Badge variant="success">成功</Badge>;
    case "failed":
      return <Badge variant="destructive">失败</Badge>;
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function formatTime(iso: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

export function Sidebar({ runs, selectedRunId, loading, onSelectRun }: SidebarProps) {
  return (
    <aside className="w-[240px] h-full border-r border-border bg-card/50 backdrop-blur-sm flex flex-col shrink-0">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border">
        <GitBranch className="h-4 w-4 text-cyan-400" />
        <span className="text-sm font-semibold text-foreground">Pipeline 运行</span>
      </div>

      <ScrollArea className="flex-1">
        {loading ? (
          <div className="p-3 space-y-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <div
                key={i}
                className="h-14 bg-muted/20 rounded animate-pulse"
              />
            ))}
          </div>
        ) : !runs || runs.length === 0 ? (
          <div className="p-6 text-center text-muted-foreground text-sm">
            暂无运行数据
          </div>
        ) : (
          <div className="p-2 space-y-1">
            {runs.map((run) => {
              const isSelected = run.run_id === selectedRunId;
              const isActive = run.status === "running" || run.status === "paused";

              return (
                <button
                  key={run.run_id}
                  onClick={() => onSelectRun(run.run_id)}
                  className={`w-full text-left px-3 py-2.5 rounded-md transition-colors border-l-[3px] ${
                    isSelected
                      ? "border-l-cyan-400 bg-muted/40"
                      : "border-l-transparent hover:bg-muted/20"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono text-xs text-foreground truncate">
                      {run.run_id.length > 12
                        ? `${run.run_id.slice(0, 12)}...`
                        : run.run_id}
                    </span>
                    {isActive && (
                      <span className="relative flex h-2 w-2 shrink-0 ml-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                      </span>
                    )}
                  </div>
                  <div className="flex items-center justify-between">
                    {statusBadge(run.status)}
                    <span className="text-[10px] text-muted-foreground truncate ml-2">
                      {run.current_stage || "-"}
                    </span>
                  </div>
                  <div className="mt-1 text-[10px] text-muted-foreground">
                    {formatTime(run.started_at)}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </ScrollArea>
    </aside>
  );
}
