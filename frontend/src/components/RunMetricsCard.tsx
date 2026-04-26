import React from 'react'
import { Card, Statistic, Tag, Space } from 'antd'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  PauseCircleOutlined,
  SyncOutlined,
} from '@ant-design/icons'

interface RunMetricsCardProps {
  status: string
  currentStageKey: string | null
  createdAt: string | null
  startedAt: string | null
  endedAt: string | null
  stageCount: number
  completedStages: number
}

const STATUS_CONFIG: Record<string, { color: string; icon: React.ReactNode }> = {
  draft: { color: 'default', icon: <ClockCircleOutlined /> },
  ready: { color: 'blue', icon: <ClockCircleOutlined /> },
  running: { color: 'processing', icon: <SyncOutlined spin /> },
  paused: { color: 'warning', icon: <PauseCircleOutlined /> },
  waiting_checkpoint: { color: 'orange', icon: <ClockCircleOutlined /> },
  succeeded: { color: 'success', icon: <CheckCircleOutlined /> },
  failed: { color: 'error', icon: <CloseCircleOutlined /> },
  terminated: { color: 'default', icon: <CloseCircleOutlined /> },
}

const RunMetricsCard: React.FC<RunMetricsCardProps> = ({
  status,
  currentStageKey,
  createdAt,
  startedAt,
  endedAt,
  stageCount,
  completedStages,
}) => {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.draft

  const duration = startedAt
    ? endedAt
      ? ((new Date(endedAt).getTime() - new Date(startedAt).getTime()) / 1000).toFixed(1) + 's'
      : ((Date.now() - new Date(startedAt).getTime()) / 1000).toFixed(1) + 's'
    : '-'

  return (
    <Card>
      <Space size="large" wrap>
        <Statistic
          title="Status"
          value={status}
          valueRender={() => (
            <Tag icon={config.icon} color={config.color} style={{ fontSize: 14 }}>
              {status.replace(/_/g, ' ')}
            </Tag>
          )}
        />
        <Statistic title="Progress" value={`${completedStages}/${stageCount}`} />
        <Statistic title="Duration" value={duration} />
        <Statistic title="Current Stage" value={currentStageKey || '-'} />
      </Space>
    </Card>
  )
}

export default RunMetricsCard
