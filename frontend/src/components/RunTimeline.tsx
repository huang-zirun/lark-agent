import React from 'react'
import { Steps, Tag, Tooltip } from 'antd'
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  SyncOutlined,
  MinusCircleOutlined,
} from '@ant-design/icons'

const STAGE_KEYS = [
  'requirement_analysis',
  'solution_design',
  'checkpoint_design_approval',
  'code_generation',
  'test_generation_and_execution',
  'code_review',
  'checkpoint_final_approval',
  'delivery_integration',
]

const STAGE_NAMES: Record<string, string> = {
  requirement_analysis: 'Requirement Analysis',
  solution_design: 'Solution Design',
  checkpoint_design_approval: 'Design Approval',
  code_generation: 'Code Generation',
  test_generation_and_execution: 'Test & Execution',
  code_review: 'Code Review',
  checkpoint_final_approval: 'Final Approval',
  delivery_integration: 'Delivery',
}

interface StageRun {
  stage_key: string
  status: string
  attempt: number
  started_at: string | null
  ended_at: string | null
  error_message: string | null
}

interface RunTimelineProps {
  stages: StageRun[]
  currentStageKey: string | null
}

const statusIcon = (status: string) => {
  switch (status) {
    case 'succeeded':
      return <CheckCircleOutlined style={{ color: '#52c41a' }} />
    case 'running':
      return <LoadingOutlined style={{ color: '#1677ff' }} />
    case 'failed':
      return <CloseCircleOutlined style={{ color: '#ff4d4f' }} />
    case 'retrying':
      return <SyncOutlined spin style={{ color: '#faad14' }} />
    case 'pending':
      return <ClockCircleOutlined style={{ color: '#d9d9d9' }} />
    case 'skipped':
      return <MinusCircleOutlined style={{ color: '#d9d9d9' }} />
    default:
      return <ClockCircleOutlined style={{ color: '#d9d9d9' }} />
  }
}

const RunTimeline: React.FC<RunTimelineProps> = ({ stages, currentStageKey }) => {
  const stageMap = new Map(stages.map((s) => [s.stage_key, s]))

  const items = STAGE_KEYS.map((key) => {
    const stage = stageMap.get(key)
    const status = stage?.status || 'pending'
    const isCheckpoint = key.startsWith('checkpoint_')

    return {
      title: (
        <span>
          {STAGE_NAMES[key] || key}
          {isCheckpoint && <Tag color="orange" style={{ marginLeft: 8 }}>Checkpoint</Tag>}
        </span>
      ),
      description: stage ? (
        <div>
          <Tag color={status === 'succeeded' ? 'green' : status === 'failed' ? 'red' : status === 'running' ? 'blue' : 'default'}>
            {status}
          </Tag>
          {stage.attempt > 1 && <Tag>Attempt {stage.attempt}</Tag>}
          {stage.error_message && (
            <Tooltip title={stage.error_message}>
              <Tag color="red">Error</Tag>
            </Tooltip>
          )}
        </div>
      ) : null,
      icon: statusIcon(status),
    }
  })

  const currentIdx = currentStageKey ? STAGE_KEYS.indexOf(currentStageKey) : 0

  return (
    <Steps
      direction="vertical"
      current={currentIdx}
      items={items}
      size="small"
    />
  )
}

export default RunTimeline
