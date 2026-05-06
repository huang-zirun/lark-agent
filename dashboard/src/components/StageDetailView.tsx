import { useEffect, useState } from "react";
import { useRunArtifactMarkdown, type LlmCallRecord } from "@/hooks/useRunDetail";
import { simpleMarkdownToHtml } from "@/lib/markdown";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FileText, Brain, Cpu } from "lucide-react";
import { LlmCallItem } from "@/components/LlmTracePanel";

interface StageDetailViewProps {
  selectedStage: string | null;
  runId: string | null;
  llmCalls: LlmCallRecord[] | null;
  llmLoading: boolean;
}

export function StageDetailView({
  selectedStage,
  runId,
  llmCalls,
  llmLoading,
}: StageDetailViewProps) {
  const [activeTab, setActiveTab] = useState<"artifact" | "llm">("artifact");

  useEffect(() => {
    setActiveTab("artifact");
  }, [selectedStage]);

  const { data: artifactMarkdown, loading: artifactLoading } =
    useRunArtifactMarkdown(runId, selectedStage);

  if (!selectedStage) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
        <Cpu className="h-8 w-8 mb-2 opacity-50" />
        <p className="text-sm">点击左侧阶段查看详情</p>
      </div>
    );
  }

  const filteredCalls = llmCalls?.filter(
    (c) =>
      c.stage === selectedStage ||
      selectedStage.startsWith(c.stage) ||
      c.stage.startsWith(selectedStage)
  );

  return (
    <div className="flex flex-col h-full">
      <div className="flex border-b border-border shrink-0">
        <button
          onClick={() => setActiveTab("artifact")}
          className={`flex items-center gap-1.5 px-4 py-2 text-sm transition-colors ${
            activeTab === "artifact"
              ? "border-b-2 border-primary text-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <FileText className="h-3.5 w-3.5" />
          阶段产物
        </button>
        <button
          onClick={() => setActiveTab("llm")}
          className={`flex items-center gap-1.5 px-4 py-2 text-sm transition-colors ${
            activeTab === "llm"
              ? "border-b-2 border-primary text-foreground"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Brain className="h-3.5 w-3.5" />
          LLM 推理
        </button>
      </div>

      <ScrollArea className="flex-1">
        {activeTab === "artifact" ? (
          artifactLoading ? (
            <div className="p-6 space-y-3">
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="h-4 bg-muted/20 rounded animate-pulse"
                  style={{ width: `${60 + Math.random() * 40}%` }}
                />
              ))}
            </div>
          ) : artifactMarkdown ? (
            <div
              className="prose prose-sm dark:prose-invert max-w-none text-sm p-4"
              dangerouslySetInnerHTML={{
                __html: simpleMarkdownToHtml(artifactMarkdown),
              }}
            />
          ) : (
            <div className="p-12 text-center text-muted-foreground">
              <Cpu className="h-8 w-8 mx-auto mb-2 opacity-50" />
              <p className="text-sm">暂无产物</p>
            </div>
          )
        ) : llmLoading ? (
          <div className="p-6 space-y-3">
            {Array.from({ length: 4 }).map((_, i) => (
              <div
                key={i}
                className="h-16 bg-muted/20 rounded animate-pulse"
              />
            ))}
          </div>
        ) : !filteredCalls || filteredCalls.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground">
            <Cpu className="h-8 w-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">本阶段无 LLM 调用</p>
          </div>
        ) : (
          <div className="space-y-1 px-2 pb-4">
            {filteredCalls.map((call, i) => (
              <LlmCallItem
                key={i}
                record={call}
                index={i}
                totalInStage={filteredCalls.length}
              />
            ))}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
