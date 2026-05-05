import {
  FileSearch,
  Lightbulb,
  Code2,
  TestTube,
  ShieldCheck,
  Package,
  Check,
} from "lucide-react";
import type { StageInfo } from "@/hooks/useRunDetail";

interface PipelineStepperProps {
  stages: StageInfo[];
  onStageClick: (stageName: string) => void;
}

const STAGE_DEFS = [
  { name: "requirement_intake", label: "需求分析", Icon: FileSearch },
  { name: "solution_design", label: "方案设计", Icon: Lightbulb },
  { name: "code_generation", label: "代码生成", Icon: Code2 },
  { name: "test_generation", label: "测试生成", Icon: TestTube },
  { name: "code_review", label: "代码评审", Icon: ShieldCheck },
  { name: "delivery", label: "交付", Icon: Package },
] as const;

function matchStage(defName: string, stageName: string): boolean {
  return stageName.startsWith(defName) || defName.startsWith(stageName);
}

function getCircleStyle(status: string | undefined) {
  switch (status) {
    case "running":
      return "border-cyan-400 text-cyan-400";
    case "success":
      return "border-emerald-400 text-emerald-400";
    case "failed":
      return "border-red-400 text-red-400";
    case "blocked":
      return "border-amber-400 text-amber-400";
    default:
      return "border-muted-foreground/30 text-muted-foreground";
  }
}

function formatDuration(ms: number | null | undefined): string {
  if (!ms) return "";
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 3600000) return `${(ms / 60000).toFixed(1)}m`;
  return `${(ms / 3600000).toFixed(1)}h`;
}

export function PipelineStepper({ stages, onStageClick }: PipelineStepperProps) {
  return (
    <div className="overflow-x-auto pb-2">
      <div className="flex items-center min-w-max">
        {STAGE_DEFS.map((def, index) => {
          const matched = stages.find((s) => matchStage(def.name, s.name));
          const status = matched?.status;
          const duration = matched?.duration_ms;
          const isLast = index === STAGE_DEFS.length - 1;
          const isRunning = status === "running";
          const isSuccess = status === "success";
          const prevStage = index > 0 ? stages.find((s) => matchStage(STAGE_DEFS[index - 1].name, s.name)) : null;
          const prevSuccess = prevStage?.status === "success";

          return (
            <div key={def.name} className="flex items-center">
              <button
                onClick={() => onStageClick(def.name)}
                className="flex flex-col items-center gap-1.5 group"
              >
                <div
                  className={`relative w-12 h-12 rounded-full border-2 flex items-center justify-center bg-card transition-colors ${getCircleStyle(
                    status
                  )} ${isRunning ? "animate-pulse" : ""}`}
                >
                  {isSuccess ? (
                    <Check className="h-6 w-6 absolute" />
                  ) : (
                    <def.Icon className="h-6 w-6" />
                  )}
                </div>
                <span className="text-[11px] text-muted-foreground group-hover:text-foreground transition-colors">
                  {def.label}
                </span>
                {isSuccess && duration != null && (
                  <span className="text-[10px] text-muted-foreground">
                    {formatDuration(duration)}
                  </span>
                )}
              </button>

              {!isLast && (
                <div
                  className={`w-10 h-[2px] mx-1 ${
                    isSuccess && prevSuccess
                      ? "bg-emerald-400"
                      : "border-t-2 border-dashed border-muted-foreground/30"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
