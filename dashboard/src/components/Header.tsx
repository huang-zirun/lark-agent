import { RefreshCw, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";

interface HeaderProps {
  onRefresh: () => void;
  runId: string | null;
}

export function Header({ onRefresh, runId }: HeaderProps) {
  return (
    <header className="h-14 border-b border-border bg-card/50 backdrop-blur-sm flex items-center justify-between px-6 sticky top-0 z-40">
      <div className="flex items-center gap-2">
        <h1 className="text-lg font-bold text-white tracking-tight">
          DevFlow
          <span className="text-cyan-400"> Monitor</span>
        </h1>
        <Activity className="h-4 w-4 text-cyan-400" />
      </div>

      <div className="flex-1 flex items-center justify-center">
        {runId && (
          <span className="font-mono text-xs text-muted-foreground">
            {runId}
          </span>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={onRefresh}
          className="h-8 w-8 text-muted-foreground hover:text-foreground"
        >
          <RefreshCw className="h-4 w-4" />
        </Button>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
          </span>
          实时监控
        </div>
      </div>
    </header>
  );
}
