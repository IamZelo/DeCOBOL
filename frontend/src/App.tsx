import { Navigate, Route, Routes } from 'react-router-dom'
import { ConversionProvider } from './hooks/useConversion'
import { WorkspaceProvider } from './hooks/useWorkspace'
import { ConvertPage } from './pages/ConvertPage'
import { DiffPage } from './pages/DiffPage'
import { GraphPage } from './pages/GraphPage'
import { HistoryPage } from './pages/HistoryPage'
import { PipelinePage } from './pages/PipelinePage'
import { WorkspacePage } from './pages/WorkspacePage'

export default function App() {
  return (
    <WorkspaceProvider>
      <ConversionProvider>
        <Routes>
          <Route path="/" element={<Navigate to="/workspace" replace />} />
          <Route path="/workspace" element={<WorkspacePage />} />
          <Route path="/convert" element={<ConvertPage />} />
          <Route path="/pipeline" element={<PipelinePage />} />
          <Route path="/diff" element={<DiffPage />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/history" element={<HistoryPage />} />
          <Route path="*" element={<Navigate to="/workspace" replace />} />
        </Routes>
      </ConversionProvider>
    </WorkspaceProvider>
  )
}
