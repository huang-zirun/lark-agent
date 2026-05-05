import { useState, useEffect, useCallback } from "react";

const API_BASE = "";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export interface RecentRun {
  run_id: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number;
  current_stage: string | null;
  checkpoint_status: string | null;
  provider_override: string | null;
}

export interface TimelineEvent {
  timestamp: string;
  stage: string | null;
  event_type: string;
  status: string | null;
  duration_ms: number | null;
  payload: Record<string, unknown> | null;
}

export function useRecentRuns(limit = 20, refreshInterval = 10000) {
  const [data, setData] = useState<RecentRun[] | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    const result = await fetchJson<{ runs: RecentRun[] }>(
      `/api/v1/metrics/recent-runs?limit=${limit}`
    );
    setData(result.runs);
    setLoading(false);
  }, [limit]);

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, refreshInterval);
    return () => clearInterval(id);
  }, [fetchData, refreshInterval]);

  return { data, loading, refetch: fetchData };
}
