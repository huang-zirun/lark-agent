import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

export interface PipelineRun {
  id: string
  template_id: string
  workspace_ref_id: string | null
  requirement_text: string
  status: string
  current_stage_key: string | null
  provider_selection_override: Record<string, unknown> | null
  resolved_provider_map: Record<string, unknown> | null
  failure_reason: string | null
  created_at: string
  started_at: string | null
  ended_at: string | null
}

export interface StageRun {
  id: string
  run_id: string
  stage_key: string
  agent_profile_id: string | null
  resolved_provider_id: string | null
  status: string
  attempt: number
  input_artifact_refs: Record<string, unknown> | null
  output_artifact_refs: Record<string, unknown> | null
  error_message: string | null
  started_at: string | null
  ended_at: string | null
}

export interface Timeline {
  run_id: string
  run_status: string
  stages: StageRun[]
}

export interface CheckpointRecord {
  id: string
  run_id: string
  stage_key: string
  checkpoint_type: string
  status: string
  decision_by: string | null
  decision_at: string | null
  reason: string | null
  next_stage_key: string | null
  created_at: string
}

export interface ArtifactItem {
  id: string
  run_id: string
  stage_run_id: string | null
  artifact_type: string
  schema_version: string
  content_summary: string | null
  data: Record<string, unknown> | null
  created_at: string | null
}

export const pipelineApi = {
  create: (data: { requirement_text: string; workspace_id?: string }) =>
    api.post<PipelineRun>('/pipelines', data),
  list: (status?: string) =>
    api.get<{ items: PipelineRun[]; total: number }>('/pipelines', { params: { status } }),
  get: (id: string) =>
    api.get<PipelineRun>(`/pipelines/${id}`),
  start: (id: string) =>
    api.post<PipelineRun>(`/pipelines/${id}/start`),
  pause: (id: string) =>
    api.post<PipelineRun>(`/pipelines/${id}/pause`),
  resume: (id: string) =>
    api.post<PipelineRun>(`/pipelines/${id}/resume`),
  terminate: (id: string) =>
    api.post<PipelineRun>(`/pipelines/${id}/terminate`),
  timeline: (id: string) =>
    api.get<Timeline>(`/pipelines/${id}/timeline`),
}

export const checkpointApi = {
  approve: (id: string, decision_by: string = 'user') =>
    api.post<CheckpointRecord>(`/checkpoints/${id}/approve`, { decision_by }),
  reject: (id: string, reason: string, decision_by: string = 'user', reject_target?: string) =>
    api.post<CheckpointRecord>(`/checkpoints/${id}/reject`, { reason, decision_by, reject_target }),
  getPending: (runId: string) =>
    api.get<CheckpointRecord | null>(`/pipelines/${runId}/pending-checkpoint`),
}

export const artifactApi = {
  get: (id: string) =>
    api.get<Record<string, unknown>>(`/artifacts/${id}`),
  listByRun: (runId: string) =>
    api.get<ArtifactItem[]>(`/pipelines/${runId}/artifacts`),
}

export const workspaceApi = {
  register: (sourceRepoPath: string) =>
    api.post('/workspaces', { source_repo_path: sourceRepoPath }),
  list: () =>
    api.get('/workspaces'),
  get: (id: string) =>
    api.get(`/workspaces/${id}`),
  diff: (id: string) =>
    api.get(`/workspaces/${id}/diff`),
}

export const providerApi = {
  list: () =>
    api.get('/providers'),
  create: (data: Record<string, unknown>) =>
    api.post('/providers', data),
  update: (id: string, data: Record<string, unknown>) =>
    api.put(`/providers/${id}`, data),
  validate: (id: string) =>
    api.post(`/providers/${id}/validate`),
}

export interface DeliveryInfo {
  run_id: string
  delivery_manifest: {
    commit_hash: string | null
    branch_name: string | null
    changed_files: string[]
    diff_stats: {
      files_changed: number
      insertions: number
      deletions: number
    }
    has_changes: boolean
    error: string | null
  } | null
  delivery_summary: {
    status: string
    deliverables: string[]
    test_summary: string
    known_risks: string[]
    next_steps: string[]
  } | null
}

export const deliveryApi = {
  get: (runId: string) =>
    api.get<DeliveryInfo>(`/pipelines/${runId}/delivery`),
  getPatch: (runId: string) =>
    api.get(`/pipelines/${runId}/delivery/patch`, { responseType: 'blob' }),
  push: (runId: string, data: { remote_url: string; remote_branch?: string }) =>
    api.post<{ success: boolean; remote_url?: string; branch?: string; error?: string }>(`/pipelines/${runId}/delivery/push`, data),
  createPR: (runId: string, data: { repo_owner: string; repo_name: string; base_branch?: string; github_token?: string }) =>
    api.post<{ success: boolean; pr_url?: string; error?: string }>(`/pipelines/${runId}/delivery/pr`, data),
}

export default api
