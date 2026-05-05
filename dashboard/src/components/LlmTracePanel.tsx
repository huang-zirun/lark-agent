import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import {
  Brain,
  ChevronDown,
  Cpu,
  MessageSquare,
  Sparkles,
  Clock,
} from "lucide-react";
import type { LlmCallRecord } from "@/hooks/useRunDetail";

interface LlmTracePanelProps {
  llmCalls: LlmCallRecord[] | null;
  loading: boolean;
}

const STAGE_DISPLAY_NAMES: Record<string, string> = {
  requirement_intake: "需求分析",
  solution_design: "方案设计",
  code_generation: "代码生成",
  test_generation: "测试生成",
  code_review: "代码评审",
  delivery: "交付",
};

function getStageName(stage: string): string {
  return STAGE_DISPLAY_NAMES[stage] || stage;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 3600000) return `${(ms / 60000).toFixed(1)}m`;
  return `${(ms / 3600000).toFixed(1)}h`;
}

function tryFormatJson(text: string): string {
  try {
    const parsed = JSON.parse(text);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return text;
  }
}

function PromptSection({
  label,
  icon: Icon,
  content,
  truncateLen,
}: {
  label: string;
  icon: React.ElementType;
  content: string;
  truncateLen: number;
}) {
  const [expanded, setExpanded] = useState(false);
  const isTruncated = content.length > truncateLen;

  return (
    <Collapsible open={expanded} onOpenChange={setExpanded}>
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-between h-7 px-2 text-xs"
        >
          <span className="flex items-center gap-1.5">
            <Icon className="h-3.5 w-3.5 text-muted-foreground" />
            {label}
          </span>
          {isTruncated && (
            <ChevronDown
              className={`h-3.5 w-3.5 text-muted-foreground transition-transform ${
                expanded ? "rotate-180" : ""
              }`}
            />
          )}
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <pre className="mt-1 p-3 bg-muted/30 rounded-md text-xs font-mono text-muted-foreground whitespace-pre-wrap break-all max-h-[300px] overflow-auto">
          {expanded || !isTruncated
            ? label === "模型输出"
              ? tryFormatJson(content)
              : content
            : content.slice(0, truncateLen) + "..."}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  );
}

function LlmCallItem({
  record,
  index,
  totalInStage,
}: {
  record: LlmCallRecord;
  index: number;
  totalInStage: number;
}) {
  return (
    <Collapsible>
      <CollapsibleTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="w-full justify-between h-auto py-2 px-3 hover:bg-muted/30"
        >
          <span className="flex items-center gap-2">
            <Badge variant="cyan" className="text-[10px] h-4">
              {getStageName(record.stage)}
            </Badge>
            {totalInStage > 1 && (
              <span className="text-[10px] text-muted-foreground">
                #{index + 1}
              </span>
            )}
          </span>
          <span className="flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {record.duration_ms != null ? formatDuration(record.duration_ms) : "-"}
            </span>
            <span>{record.usage?.total_tokens ?? 0} tokens</span>
            <ChevronDown className="h-3.5 w-3.5 transition-transform" />
          </span>
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="px-3 pb-3 space-y-2">
          <PromptSection
            label="System Prompt"
            icon={MessageSquare}
            content={record.system_prompt_summary || ""}
            truncateLen={200}
          />
          <PromptSection
            label="User Prompt"
            icon={MessageSquare}
            content={record.user_prompt_summary || ""}
            truncateLen={200}
          />
          <PromptSection
            label="模型输出"
            icon={Sparkles}
            content={record.content_summary || record.content || ""}
            truncateLen={500}
          />

          <div className="grid grid-cols-3 gap-2 text-xs pt-1">
            <div className="p-2 bg-muted/20 rounded">
              <div className="text-muted-foreground">prompt_tokens</div>
              <div className="font-mono">{record.usage?.prompt_tokens ?? "-"}</div>
            </div>
            <div className="p-2 bg-muted/20 rounded">
              <div className="text-muted-foreground">completion_tokens</div>
              <div className="font-mono">{record.usage?.completion_tokens ?? "-"}</div>
            </div>
            <div className="p-2 bg-muted/20 rounded">
              <div className="text-muted-foreground">total_tokens</div>
              <div className="font-mono">{record.usage?.total_tokens ?? "-"}</div>
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground pt-1">
            <span>
              调用耗时: <span className="font-mono">{record.duration_ms != null ? formatDuration(record.duration_ms) : "-"}</span>
            </span>
            <span>
              Provider: <span className="font-mono">{record.provider ?? "-"}</span>
            </span>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

export function LlmTracePanel({ llmCalls, loading }: LlmTracePanelProps) {
  const grouped = (() => {
    if (!llmCalls) return [];
    const map = new Map<string, LlmCallRecord[]>();
    for (const call of llmCalls) {
      const existing = map.get(call.stage) || [];
      existing.push(call);
      map.set(call.stage, existing);
    }
    return Array.from(map.entries()).map(([stage, calls]) => ({
      stage,
      calls,
    }));
  })();

  return (
    <Card className="border-border bg-card/50 backdrop-blur-sm h-full">
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium flex items-center gap-2">
          <Brain className="h-4 w-4 text-violet-400" />
          LLM 推理过程
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <ScrollArea className="h-[calc(100vh-12rem)]">
          {loading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div
                  key={i}
                  className="h-16 bg-muted/20 rounded animate-pulse"
                />
              ))}
            </div>
          ) : !llmCalls || llmCalls.length === 0 ? (
            <div className="p-12 text-center text-muted-foreground">
              <Cpu className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">本阶段无 LLM 调用</p>
            </div>
          ) : (
            <div className="space-y-1 px-2 pb-4">
              {grouped.map(({ stage, calls }) => (
                <div key={stage}>
                  <div className="px-3 py-1.5 text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                    {getStageName(stage)}
                  </div>
                  {calls.map((call, i) => (
                    <LlmCallItem
                      key={i}
                      record={call}
                      index={i}
                      totalInStage={calls.length}
                    />
                  ))}
                </div>
              ))}
            </div>
          )}
        </ScrollArea>
      </CardContent>
    </Card>
  );
}
