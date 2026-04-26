import { Routes, Route, Navigate } from 'react-router-dom'
import { ConfigProvider, theme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import RequirementEntry from './pages/RequirementEntry'
import DevWorkspace from './pages/DevWorkspace'

function App() {
  return (
    <ConfigProvider locale={zhCN} theme={{ algorithm: theme.defaultAlgorithm }}>
      <Routes>
        <Route path="/" element={<RequirementEntry />} />
        <Route path="/workspace/:runId" element={<DevWorkspace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </ConfigProvider>
  )
}

export default App
