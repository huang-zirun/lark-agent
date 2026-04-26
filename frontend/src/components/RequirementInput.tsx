import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input, Button, Card, Typography, Space, message } from 'antd'
import { RocketOutlined } from '@ant-design/icons'
import { pipelineApi } from '../api/client'

const { Title, Paragraph } = Typography
const { TextArea } = Input

const RequirementInput: React.FC = () => {
  const [requirement, setRequirement] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async () => {
    if (!requirement.trim()) {
      message.warning('Please enter a requirement')
      return
    }
    setLoading(true)
    try {
      const res = await pipelineApi.create({ requirement_text: requirement.trim() })
      const runId = res.data.id
      message.success('Pipeline created! Starting...')
      try {
        await pipelineApi.start(runId)
      } catch (err: any) {
        const isTimeout = err.code === 'ECONNABORTED' || err.message?.includes('timeout')
        if (!isTimeout) {
          message.error('Failed to start pipeline')
        }
      }
      navigate(`/workspace/${runId}`)
    } catch (err) {
      message.error('Failed to create pipeline')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card style={{ maxWidth: 720, margin: '80px auto' }}>
      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        <div style={{ textAlign: 'center' }}>
          <Title level={2}>DevFlow Engine</Title>
          <Paragraph type="secondary">
            AI-driven requirement-to-code delivery pipeline
          </Paragraph>
        </div>
        <TextArea
          rows={6}
          placeholder="Enter your requirement in natural language, e.g.: Add GET /api/health endpoint to the API"
          value={requirement}
          onChange={(e) => setRequirement(e.target.value)}
        />
        <Button
          type="primary"
          icon={<RocketOutlined />}
          loading={loading}
          onClick={handleSubmit}
          size="large"
          block
        >
          Create Pipeline
        </Button>
      </Space>
    </Card>
  )
}

export default RequirementInput
