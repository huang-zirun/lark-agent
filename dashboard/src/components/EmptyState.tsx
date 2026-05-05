import { Workflow, Rocket } from "lucide-react";

export function EmptyState() {
  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
      <div className="text-center space-y-4">
        <Workflow className="h-16 w-16 mx-auto text-muted-foreground/40" />
        <h1 className="text-2xl font-semibold">Pipeline 执行监控</h1>
        <p className="text-sm text-muted-foreground">
          启动 DevFlow 后，Pipeline 运行将在此处实时展示
        </p>
        <p className="text-xs text-muted-foreground/60 flex items-center justify-center gap-1.5">
          <Rocket className="h-3.5 w-3.5" />
          使用 devflow start 启动流程
        </p>
      </div>
    </div>
  );
}
