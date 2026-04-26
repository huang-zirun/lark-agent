import React, { useState } from 'react'
import { Card, Button, Input, Space, Typography, Tag, Descriptions, message } from 'antd'
import { CheckOutlined, CloseOutlined } from '@ant-design/icons'
import { checkpointApi } from '../api/client'

const { Title, Paragraph } = Typography
const { TextArea } = Input

interface CheckpointRecord {
  id: string
  run_id: string
  stage_key: string
  checkpoint_type: string
  status: string
  reason: string | null
}

interface CheckpointPanelProps {
  checkpoint: CheckpointRecord
  artifacts: Record<string, unknown>[]
  onAction: () => void
}

const CheckpointPanel: React.FC<CheckpointPanelProps> = ({ checkpoint, artifacts, onAction }) => {
  const [rejectReason, setRejectReason] = useState('')
  const [loading, setLoading] = useState(false)

  const handleApprove = async () => {
    setLoading(true)
    try {
      await checkpointApi.approve(checkpoint.id)
      message.success('Approved! Pipeline will continue.')
      onAction()
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Failed to approve')
    } finally {
      setLoading(false)
    }
  }

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      message.warning('Please provide a rejection reason')
      return
    }
    setLoading(true)
    try {
      await checkpointApi.reject(checkpoint.id, rejectReason.trim())
      message.info('Rejected. Pipeline will rollback.')
      onAction()
    } catch (err: any) {
      message.error(err.response?.data?.detail || 'Failed to reject')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card
      title={
        <Space>
          <Tag color="orange">Checkpoint</Tag>
          <span>{checkpoint.checkpoint_type === 'design_approval' ? 'Design Approval' : 'Final Approval'}</span>
        </Space>
      }
      style={{ marginBottom: 16 }}
    >
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {artifacts.map((artifact, idx) => (
          <Card key={idx} type="inner" title={String(artifact.artifact_type || 'Artifact')}>
            <pre style={{ maxHeight: 300, overflow: 'auto', fontSize: 12 }}>
              {JSON.stringify(artifact.data || artifact, null, 2)}
            </pre>
          </Card>
        ))}

        {checkpoint.status === 'pending' && (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <TextArea
              rows={3}
              placeholder="Rejection reason (required if rejecting)..."
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
            />
            <Space>
              <Button
                type="primary"
                icon={<CheckOutlined />}
                loading={loading}
                onClick={handleApprove}
              >
                Approve
              </Button>
              <Button
                danger
                icon={<CloseOutlined />}
                loading={loading}
                onClick={handleReject}
              >
                Reject
              </Button>
            </Space>
          </Space>
        )}

        {checkpoint.status !== 'pending' && (
          <Descriptions column={1} size="small">
            <Descriptions.Item label="Status">
              <Tag color={checkpoint.status === 'approved' ? 'green' : 'red'}>
                {checkpoint.status}
              </Tag>
            </Descriptions.Item>
            {checkpoint.reason && (
              <Descriptions.Item label="Reason">{checkpoint.reason}</Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Space>
    </Card>
  )
}

export default CheckpointPanel
