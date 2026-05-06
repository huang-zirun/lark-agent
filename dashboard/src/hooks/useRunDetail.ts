import { useState, useEffect, useCallback } from "react";

const API_BASE = "";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export interface RunListItem {
  run_id: string;
  status: string;
  started_at: string | null;
  current_stage: string | null;
}

export interface StageInfo {
  name: string;
  status: string;
  duration_ms: number | null;
  started_at: string | null;
  ended_at: string | null;
}

export interface ArtifactSummary {
  [stage: string]: Record<string, unknown> | undefined;
}

export interface CheckpointRecord {
  run_id: string;
  stage: string;
  status: string;
  decision: string | null;
  reviewer: Record<string, unknown> | null;
  reject_reason: string | null;
  override_reason: string | null;
  quality_snapshot: Record<string, unknown> | null;
  updated_at: string;
}

export interface TokenStageInfo {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  provider?: string;
  model?: string;
}

export interface TokenSummary {
  [stage: string]: TokenStageInfo;
}

export interface LlmCallRecord {
  stage: string;
  system_prompt_summary: string | null;
  user_prompt_summary: string | null;
  content_summary: string | null;
  system_prompt: string | null;
  user_prompt: string | null;
  content: string | null;
  usage: Record<string, number> | null;
  duration_ms: number | null;
  provider: string | null;
  model: string | null;
  turn: number | null;
  started_at: string | null;
  ended_at: string | null;
  request_path: string | null;
  response_path: string | null;
}

export interface RunDetail {
  run: Record<string, unknown>;
  stages: StageInfo[];
  artifacts: ArtifactSummary;
  checkpoints: CheckpointRecord[];
  llm_calls: LlmCallRecord[];
  token_summary: TokenSummary;
  delivery: Record<string, unknown> | null;
}

export function useActiveRun() {
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJson<Record<string, unknown> | null>("/api/v1/metrics/active-run")
      .then((result) => { setData(result); setError(null); })
      .catch((err) => { setData(null); setError(err instanceof Error ? err.message : String(err)); })
      .finally(() => setLoading(false));
  }, []);

  return { data, loading, error };
}

export function useRunList(limit = 20) {
  const [data, setData] = useState<RunListItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const result = await fetchJson<{ runs: RunListItem[] }>(
        `/api/v1/metrics/recent-runs?limit=${limit}`
      );
      setData(result.runs);
      setError(null);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 5000);
    return () => clearInterval(id);
  }, [fetchData]);

  return { data, loading, refetch: fetchData, error };
}

export function useRunDetail(runId: string | null) {
  const [data, setData] = useState<RunDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    if (!runId) return;
    setLoading(true);
    try {
      const result = await fetchJson<RunDetail>(
        `/api/v1/metrics/runs/${runId}/detail`
      );
      setData(result);
      setError(null);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    fetchData();
    if (!runId) return;
    const isRunning = data?.run?.status === "running" || data?.run?.status === "paused";
    const interval = isRunning ? 2000 : 10000;
    const id = setInterval(fetchData, interval);
    return () => clearInterval(id);
  }, [fetchData, runId, data?.run?.status]);

  return { data, loading, refetch: fetchData, error };
}

export function useRunArtifactMarkdown(runId: string | null, stage: string | null) {
  const [data, setData] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!runId || !stage) {
      setData(null);
      return;
    }
    setLoading(true);
    try {
      const result = await fetchJson<{ content: string | null }>(
        `/api/v1/metrics/runs/${runId}/artifact-markdown?stage=${encodeURIComponent(stage)}`
      );
      setData(result.content);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [runId, stage]);

  useEffect(() => {
    fetchData();
    if (!runId || !stage) return;
    const id = setInterval(fetchData, 3000);
    return () => clearInterval(id);
  }, [fetchData, runId, stage]);

  return { data, loading, refetch: fetchData };
}

export function useRunLlmTrace(runId: string | null, isActive: boolean = false) {
  const [data, setData] = useState<LlmCallRecord[] | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchData = useCallback(async () => {
    if (!runId) return;
    setLoading(true);
    try {
      const r = await fetchJson<{ llm_trace: LlmCallRecord[] }>(`/api/v1/metrics/runs/${runId}/llm-trace`);
      setData(r.llm_trace);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    fetchData();
    if (!runId || !isActive) return;
    const id = setInterval(fetchData, 3000);
    return () => clearInterval(id);
  }, [fetchData, runId, isActive]);

  return { data, loading, refetch: fetchData };
}

export function useRunDiff(runId: string | null, type: string) {
  const [data, setData] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    fetchJson<{ content: string }>(`/api/v1/metrics/runs/${runId}/diff?type=${type}`)
      .then((r) => setData(r.content))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [runId, type]);

  return { data, loading };
}
