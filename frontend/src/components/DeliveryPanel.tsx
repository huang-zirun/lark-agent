import React, { useState } from 'react'
import { Card, Button, Space, Tag, Typography, Descriptions, Modal, Input, message, Spin } from 'antd'
import { DownloadOutlined, CloudUploadOutlined, PullRequestOutlined, CheckCircleOutlined, ExclamationCircleOutlined, FileTextOutlined } from '@ant-design/icons'
import { deliveryApi, type DeliveryInfo } from '../api/client'

const { Title, Text, Paragraph } = Typography

interface DeliveryPanelProps {
  runId: string
  deliveryInfo: DeliveryInfo | null
  onRefresh: () => void
}

const DeliveryPanel: React.FC<DeliveryPanelProps> = ({ runId, deliveryInfo, onRefresh }) => {
  const [pushModalOpen, setPushModalOpen] = useState(false)
  const [prModalOpen, setPrModalOpen] = useState(false)
  const [remoteUrl, setRemoteUrl] = useState('')
  const [remoteBranch, setRemoteBranch] = useState('')
  const [repoOwner, setRepoOwner] = useState('')
  const [repoName, setRepoName] = useState('')
  const [baseBranch, setBaseBranch] = useState('main')
  const [githubToken, setGithubToken] = useState('')
  const [loading, setLoading] = useState(false)

  if (!deliveryInfo) {
    return (
      <Card title="Delivery" style={{ marginBottom: 16 }}>
        <Spin size="small" />
        <Text style={{ marginLeft: 8 }}>Loading delivery info...</Text>
      </Card>
    )
  }

  const { delivery_manifest, delivery_summary } = deliveryInfo

  const handleDownloadPatch = async () => {
    try {
      const response = await deliveryApi.getPatch(runId)
      const blob = new Blob([response.data], { type: 'text/x-diff' })
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `delivery-${runId}.patch`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      message.success('Patch downloaded')
    } catch {
      message.error('Failed to download patch')
    }
  }

  const handlePush = async () => {
    if (!remoteUrl) {
      message.error('Please enter remote URL')
      return
    }
    setLoading(true)
    try {
      const res = await deliveryApi.push(runId, { remote_url: remoteUrl, remote_branch: remoteBranch || undefined })
      if (res.data.success) {
        message.success(`Pushed to ${res.data.remote_url}`)
        setPushModalOpen(false)
        onRefresh()
      } else {
        message.error(res.data.error || 'Push failed')
      }
    } catch {
      message.error('Failed to push')
    } finally {
      setLoading(false)
    }
  }

  const handleCreatePR = async () => {
    if (!repoOwner || !repoName) {
      message.error('Please enter repo owner and name')
      return
    }
    setLoading(true)
    try {
      const res = await deliveryApi.createPR(runId, {
        repo_owner: repoOwner,
        repo_name: repoName,
        base_branch: baseBranch,
        github_token: githubToken || undefined,
      })
      if (res.data.success) {
        message.success('PR created successfully')
        Modal.success({
          title: 'Pull Request Created',
          content: (
            <div>
              <p>Your PR is ready:</p>
              <a href={res.data.pr_url} target="_blank" rel="noopener noreferrer">{res.data.pr_url}</a>
            </div>
          ),
        })
        setPrModalOpen(false)
        onRefresh()
      } else {
        message.error(res.data.error || 'Failed to create PR')
      }
    } catch {
      message.error('Failed to create PR')
    } finally {
      setLoading(false)
    }
  }

  const hasDelivery = delivery_manifest?.has_changes

  return (
    <>
      <Card
        title={
          <Space>
            <CheckCircleOutlined style={{ color: '#52c41a' }} />
            <span>Delivery Ready</span>
            {hasDelivery ? (
              <Tag color="success">Has Changes</Tag>
            ) : (
              <Tag color="default">No Changes</Tag>
            )}
          </Space>
        }
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button icon={<FileTextOutlined />} onClick={handleDownloadPatch}>
              Download Patch
            </Button>
            <Button icon={<CloudUploadOutlined />} type="primary" onClick={() => setPushModalOpen(true)}>
              Push to Remote
            </Button>
            <Button icon={<PullRequestOutlined />} onClick={() => setPrModalOpen(true)}>
              Create PR
            </Button>
          </Space>
        }
      >
        {delivery_manifest && (
          <Descriptions bordered size="small" column={2} style={{ marginBottom: 16 }}>
            <Descriptions.Item label="Commit">
              <Text code copyable>{delivery_manifest.commit_hash?.slice(0, 8) || 'N/A'}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="Branch">
              <Tag color="blue">{delivery_manifest.branch_name || 'N/A'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Files Changed">
              {delivery_manifest.diff_stats?.files_changed || 0}
            </Descriptions.Item>
            <Descriptions.Item label="Lines">
              <Text type="success">+{delivery_manifest.diff_stats?.insertions || 0}</Text>
              {' / '}
              <Text type="danger">-{delivery_manifest.diff_stats?.deletions || 0}</Text>
            </Descriptions.Item>
          </Descriptions>
        )}

        {delivery_summary && (
          <div style={{ marginTop: 16 }}>
            <Title level={5}>Summary</Title>
            <Paragraph>
              <Text strong>Status: </Text>
              <Tag color={delivery_summary.status === 'ready' ? 'success' : 'warning'}>
                {delivery_summary.status}
              </Tag>
            </Paragraph>
            {delivery_summary.deliverables?.length > 0 && (
              <Paragraph>
                <Text strong>Deliverables: </Text>
                {delivery_summary.deliverables.map((d, i) => (
                  <Tag key={i}>{d}</Tag>
                ))}
              </Paragraph>
            )}
            {delivery_summary.test_summary && (
              <Paragraph>
                <Text strong>Test: </Text>
                {delivery_summary.test_summary}
              </Paragraph>
            )}
            {delivery_summary.known_risks?.length > 0 && (
              <Paragraph>
                <ExclamationCircleOutlined style={{ color: '#faad14', marginRight: 8 }} />
                <Text strong>Risks: </Text>
                {delivery_summary.known_risks.join(', ')}
              </Paragraph>
            )}
            {delivery_summary.next_steps?.length > 0 && (
              <Paragraph>
                <Text strong>Next Steps: </Text>
                <ul style={{ marginTop: 8, paddingLeft: 20 }}>
                  {delivery_summary.next_steps.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ul>
              </Paragraph>
            )}
          </div>
        )}

        {delivery_manifest?.error && (
          <div style={{ marginTop: 16, padding: 12, background: '#fff2f0', borderRadius: 4 }}>
            <ExclamationCircleOutlined style={{ color: '#ff4d4f', marginRight: 8 }} />
            <Text type="danger">{delivery_manifest.error}</Text>
          </div>
        )}
      </Card>

      <Modal
        title="Push to Remote Repository"
        open={pushModalOpen}
        onOk={handlePush}
        onCancel={() => setPushModalOpen(false)}
        confirmLoading={loading}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text strong>Remote URL</Text>
            <Input
              placeholder="https://github.com/username/repo.git"
              value={remoteUrl}
              onChange={(e) => setRemoteUrl(e.target.value)}
            />
          </div>
          <div>
            <Text strong>Remote Branch (optional)</Text>
            <Input
              placeholder="main"
              value={remoteBranch}
              onChange={(e) => setRemoteBranch(e.target.value)}
            />
          </div>
        </Space>
      </Modal>

      <Modal
        title="Create GitHub Pull Request"
        open={prModalOpen}
        onOk={handleCreatePR}
        onCancel={() => setPrModalOpen(false)}
        confirmLoading={loading}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <div>
            <Text strong>Repository Owner</Text>
            <Input
              placeholder="username or organization"
              value={repoOwner}
              onChange={(e) => setRepoOwner(e.target.value)}
            />
          </div>
          <div>
            <Text strong>Repository Name</Text>
            <Input
              placeholder="repo-name"
              value={repoName}
              onChange={(e) => setRepoName(e.target.value)}
            />
          </div>
          <div>
            <Text strong>Base Branch</Text>
            <Input
              placeholder="main"
              value={baseBranch}
              onChange={(e) => setBaseBranch(e.target.value)}
            />
          </div>
          <div>
            <Text strong>GitHub Token (optional)</Text>
            <Input.Password
              placeholder="ghp_xxxxxxxxxxxx"
              value={githubToken}
              onChange={(e) => setGithubToken(e.target.value)}
            />
          </div>
        </Space>
      </Modal>
    </>
  )
}

export default DeliveryPanel
