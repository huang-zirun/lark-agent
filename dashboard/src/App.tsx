import { useState, useCallback, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { PipelineStepper } from "@/components/PipelineStepper";
import { StageDetailPanel } from "@/components/StageDetailPanel";
import { LlmTracePanel } from "@/components/LlmTracePanel";
import { EmptyState } from "@/components/EmptyState";
import { Header } from "@/components/Header";
import {
  useActiveRun,
  useRunList,
  useRunDetail,
  useRunLlmTrace,
} from "@/hooks/useRunDetail";

function App() {
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedStage, setSelectedStage] = useState<string | null>(null);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(false);

  const { data: activeRun, loading: activeLoading } = useActiveRun();
  const { data: runList, loading: listLoading, refetch: refetchList } = useRunList();
  const { data: runDetail, loading: detailLoading, refetch: refetchDetail } = useRunDetail(selectedRunId);
  const { data: llmCalls, loading: llmLoading } = useRunLlmTrace(selectedRunId);

  useEffect(() => {
    if (activeLoading || listLoading) return;
    if (selectedRunId) return;
    if (activeRun && typeof activeRun.run_id === "string") {
      setSelectedRunId(activeRun.run_id as string);
    } else if (runList && runList.length > 0) {
      setSelectedRunId(runList[0].run_id);
    }
  }, [activeRun, runList, activeLoading, listLoading, selectedRunId]);

  const handleSelectRun = useCallback((runId: string) => {
    setSelectedRunId(runId);
    setSelectedStage(null);
  }, []);

  const handleStageClick = useCallback((stageName: string) => {
    setSelectedStage(stageName);
    const el = document.getElementById(`stage-${stageName}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, []);

  const handleRefresh = useCallback(() => {
    refetchList();
    refetchDetail();
  }, [refetchList, refetchDetail]);

  const noRuns = !runList || runList.length === 0;
  const isInitializing = listLoading && !runList;

  if (!isInitializing && noRuns) {
    return (
      <div className="min-h-screen bg-background text-foreground flex flex-col">
        <Header onRefresh={handleRefresh} runId={null} />
        <EmptyState />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      <Header onRefresh={handleRefresh} runId={selectedRunId} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar
          runs={runList}
          selectedRunId={selectedRunId}
          loading={listLoading}
          onSelectRun={handleSelectRun}
        />
        <main className="flex-1 overflow-y-auto p-6 space-y-6">
          <PipelineStepper
            stages={runDetail?.stages ?? []}
            onStageClick={handleStageClick}
          />
          <StageDetailPanel
            stages={runDetail?.stages ?? []}
            artifacts={runDetail?.artifacts ?? {}}
            checkpoints={runDetail?.checkpoints ?? []}
            tokenSummary={runDetail?.token_summary ?? {}}
            delivery={runDetail?.delivery ?? null}
            selectedStage={selectedStage}
            runId={selectedRunId}
            onArtifactViewDetail={() => {}}
            onDiffView={() => {}}
          />
        </main>
        {!rightPanelCollapsed && (
          <div className="w-[360px] shrink-0 border-l border-border overflow-y-auto">
            <LlmTracePanel llmCalls={llmCalls} loading={llmLoading} />
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
