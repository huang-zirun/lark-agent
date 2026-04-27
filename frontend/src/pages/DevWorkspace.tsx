import React, { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Button, Card, Col, Row, Space, Spin, Typography, message } from 'antd'
import { ArrowLeftOutlined, ReloadOutlined, PauseOutlined, StopOutlined } from '@ant-design/icons'
import { pipelineApi, artifactApi, checkpointApi, deliveryApi, type PipelineRun, type StageRun, type ArtifactItem, type CheckpointRecord, type DeliveryInfo } from '../api/client'
import RunTimeline from '../components/RunTimeline'
import RunMetricsCard from '../components/RunMetricsCard'
import CheckpointPanel from '../components/CheckpointPanel'
import ArtifactViewer from '../components/ArtifactViewer'
import DeliveryPanel from '../components/DeliveryPanel'

const { Title, Paragraph } = Typography

const DevWorkspace: React.FC = () => {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const [run, setRun] = useState<PipelineRun | null>(null)
  const [stages, setStages] = useState<StageRun[]>([])
  const [artifacts, setArtifacts] = useState<ArtifactItem[]>([])
  const [pendingCheckpoint, setPendingCheckpoint] = useState<CheckpointRecord | null>(null)
  const [deliveryInfo, setDeliveryInfo] = useState<DeliveryInfo | null>(null)
  const [loading, setLoading] = useState(true)

  const fetchData = useCallback(async () => {
    if (!runId) return
    try {
      const [runRes, timelineRes, artifactsRes] = await Promise.all([
        pipelineApi.get(runId),
        pipelineApi.timeline(runId),
        artifactApi.listByRun(runId).catch(() => ({ data: [] })),
      ])
      setRun(runRes.data)
      setStages(timelineRes.data.stages)
      setArtifacts(artifactsRes.data as ArtifactItem[])
      try {
        const checkpointRes = await checkpointApi.getPending(runId)
        setPendingCheckpoint(checkpointRes.data)
      } catch {
        message.error('Failed to load checkpoint data')
      }
      if (runRes.data.status === 'succeeded' || runRes.data.status === 'failed') {
        try {
          const deliveryRes = await deliveryApi.get(runId)
          setDeliveryInfo(deliveryRes.data)
        } catch {
          // Delivery info may not be available yet
        }
      }
    } catch {
      message.error('Failed to load pipeline data')
    } finally {
      setLoading(false)
    }
  }, [runId])

  useEffect(() => {
    fetchData()
    const interval = setInterval(() => {
      if (run?.status === 'running' || run?.status === 'waiting_checkpoint') {
        fetchData()
      }
    }, 3000)
    return () => clearInterval(interval)
  }, [fetchData, run?.status])

  const checkpointArtifacts = pendingCheckpoint
    ? artifacts.filter((a) =>
        pendingCheckpoint.stage_key === 'checkpoint_design_approval'
          ? ['requirement_brief', 'design_spec'].includes(a.artifact_type)
          : ['change_set', 'review_report', 'test_report'].includes(a.artifact_type)
      )
    : []

  const completedStages = stages.filter((s) => s.status === 'succeeded').length
  const totalStages = stages.length

  if (loading) {
    return (
      <div style={{ textAlign: 'center', padding: 100 }}>
        <Spin size="large" />
      </div>
    )
  }

  if (!run) {
    return <div>Pipeline not found</div>
  }

  return (
    <div style={{ padding: 24, minHeight: '100vh', background: '#f0f2f5' }}>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/')}>
          Back
        </Button>
        <Button icon={<ReloadOutlined />} onClick={fetchData}>
          Refresh
        </Button>
        {run.status === 'running' && (
          <Button icon={<PauseOutlined />} onClick={async () => {
            try { await pipelineApi.pause(run.id); fetchData() } catch { message.error('Failed to pause') }
          }}>
            Pause
          </Button>
        )}
        {run.status === 'paused' && (
          <Button type="primary" onClick={async () => {
            try { await pipelineApi.resume(run.id); fetchData() } catch { message.error('Failed to resume') }
          }}>
            Resume
          </Button>
        )}
        {['running', 'paused', 'waiting_checkpoint'].includes(run.status) && (
          <Button danger icon={<StopOutlined />} onClick={async () => {
            try { await pipelineApi.terminate(run.id); fetchData() } catch { message.error('Failed to terminate') }
          }}>
            Terminate
          </Button>
        )}
      </Space>

      <RunMetricsCard
        status={run.status}
        currentStageKey={run.current_stage_key}
        createdAt={run.created_at}
        startedAt={run.started_at}
        endedAt={run.ended_at}
        stageCount={totalStages}
        completedStages={completedStages}
      />

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={10}>
          <Card title="Pipeline Timeline" style={{ marginBottom: 16 }}>
            <RunTimeline stages={stages} currentStageKey={run.current_stage_key} />
          </Card>
        </Col>
        <Col span={14}>
          {run.status === 'waiting_checkpoint' && pendingCheckpoint && (
            <CheckpointPanel
              checkpoint={pendingCheckpoint}
              artifacts={checkpointArtifacts}
              onAction={fetchData}
            />
          )}

          {(run.status === 'succeeded' || run.status === 'failed') && deliveryInfo && (
            <DeliveryPanel runId={run.id} deliveryInfo={deliveryInfo} onRefresh={fetchData} />
          )}

          <Card title="Artifacts" style={{ marginBottom: 16 }}>
            <ArtifactViewer artifacts={artifacts} />
          </Card>

          {run.failure_reason && (
            <Card title="Error" style={{ marginBottom: 16 }}>
              <Paragraph type="danger">{run.failure_reason}</Paragraph>
            </Card>
          )}

          <Card title="Requirement" size="small">
            <Paragraph>{run.requirement_text}</Paragraph>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default DevWorkspace
