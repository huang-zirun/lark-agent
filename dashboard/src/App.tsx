import { useState, useCallback, useEffect } from "react";
import { Sidebar } from "@/components/Sidebar";
import { PipelineStepper } from "@/components/PipelineStepper";
import { StageDetailPanel } from "@/components/StageDetailPanel";
import { LlmTracePanel } from "@/components/LlmTracePanel";
import { EmptyState } from "@/components/EmptyState";
import { Header } from "@/components/Header";
import { WifiOff, RefreshCw } from "lucide-react";
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

  const { data: activeRun, loading: activeLoading, error: activeError } = useActiveRun();
  const { data: runList, loading: listLoading, refetch: refetchList, error: listError } = useRunList();
  const { data: runDetail, loading: detailLoading, refetch: refetchDetail } = useRunDetail(selectedRunId);
  const isActive = runDetail?.run?.status === "running" || runDetail?.run?.status === "paused";
  const { data: llmCalls, loading: llmLoading } = useRunLlmTrace(selectedRunId, isActive);

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
  const apiError = (activeError || listError) && !activeLoading && !listLoading;

  if (apiError) {
    return (
      <div className="min-h-screen bg-background text-foreground flex flex-col">
        <Header onRefresh={handleRefresh} runId={null} />
        <div className="flex items-center justify-center min-h-[calc(100vh-4rem)]">
          <div className="text-center space-y-4">
            <WifiOff className="h-16 w-16 mx-auto text-destructive/60" />
            <h1 className="text-2xl font-semibold">API 服务连接失败</h1>
            <p className="text-sm text-muted-foreground">
              无法连接到后端 API 服务 (127.0.0.1:8080)，请确认服务已启动
            </p>
            <p className="text-xs text-muted-foreground/60 font-mono">
              {activeError || listError}
            </p>
            <button
              onClick={handleRefresh}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <RefreshCw className="h-4 w-4" />
              重试连接
            </button>
          </div>
        </div>
      </div>
    );
  }

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
            llmCalls={llmCalls}
            onArtifactViewDetail={() => {}}
            onDiffView={() => {}}
          />
        </main>
        {!rightPanelCollapsed && (
          <div className="w-[360px] shrink-0 border-l border-border overflow-y-auto">
            <LlmTracePanel llmCalls={llmCalls} loading={llmLoading} selectedStage={selectedStage} />
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
