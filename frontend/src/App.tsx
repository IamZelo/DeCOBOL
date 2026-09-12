import { Navigate, Route, Routes } from 'react-router-dom'
import { ConversionProvider } from './hooks/useConversion'
import { ConvertPage } from './pages/ConvertPage'
import { DiffPage } from './pages/DiffPage'
import { HistoryPage } from './pages/HistoryPage'
import { PipelinePage } from './pages/PipelinePage'
import { WorkspacePage } from './pages/WorkspacePage'

export default function App() {
  return (
    <ConversionProvider>
      <Routes>
        <Route path="/" element={<Navigate to="/workspace" replace />} />
        <Route path="/workspace" element={<WorkspacePage />} />
        <Route path="/convert" element={<ConvertPage />} />
        <Route path="/pipeline" element={<PipelinePage />} />
        <Route path="/diff" element={<DiffPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="*" element={<Navigate to="/workspace" replace />} />
      </Routes>
    </ConversionProvider>
  )
}
