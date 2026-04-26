import React from 'react'
import { Card, Collapse, Tag } from 'antd'

interface ArtifactViewerProps {
  artifacts: {
    id: string
    artifact_type: string
    content_summary: string | null
    data: Record<string, unknown> | null
  }[]
}

const TYPE_COLORS: Record<string, string> = {
  requirement_brief: 'blue',
  design_spec: 'purple',
  change_set: 'green',
  diff_manifest: 'cyan',
  test_report: 'orange',
  review_report: 'magenta',
  delivery_summary: 'gold',
}

const ArtifactViewer: React.FC<ArtifactViewerProps> = ({ artifacts }) => {
  if (!artifacts || artifacts.length === 0) {
    return <Card><p style={{ color: '#999' }}>No artifacts yet</p></Card>
  }

  const items = artifacts.map((artifact, idx) => ({
    key: String(idx),
    label: (
      <Space>
        <Tag color={TYPE_COLORS[artifact.artifact_type] || 'default'}>
          {artifact.artifact_type}
        </Tag>
        <span>{artifact.content_summary || ''}</span>
      </Space>
    ),
    children: (
      <pre style={{ maxHeight: 400, overflow: 'auto', fontSize: 12, background: '#f5f5f5', padding: 12, borderRadius: 4 }}>
        {JSON.stringify(artifact.data, null, 2)}
      </pre>
    ),
  }))

  return <Collapse items={items} />
}

export default ArtifactViewer

function Space({ children }: { children: React.ReactNode }) {
  return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>{children}</span>
}
