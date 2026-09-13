import { Navigate, Route, Routes } from 'react-router-dom'
import { ConversionProvider } from './hooks/useConversion'
import { ThemeProvider } from './hooks/useTheme'
import { WorkspaceProvider } from './hooks/useWorkspace'
import { ConvertPage } from './pages/ConvertPage'
import { DocsPage } from './pages/DocsPage'
import { DiffPage } from './pages/DiffPage'
import { HistoryPage } from './pages/HistoryPage'
import { LandingPage } from './pages/LandingPage'
import { PipelinePage } from './pages/PipelinePage'
import { WorkspacePage } from './pages/WorkspacePage'

export default function App() {
  return (
    <ThemeProvider>
      <WorkspaceProvider>
        <ConversionProvider>
          <Routes>
            <Route path="/" element={<LandingPage />} />
            <Route path="/workspace" element={<WorkspacePage />} />
            <Route path="/convert" element={<ConvertPage />} />
            <Route path="/pipeline" element={<PipelinePage />} />
            <Route path="/diff" element={<DiffPage />} />
            <Route path="/graph" element={<Navigate to="/diff" replace />} />
            <Route path="/docs" element={<DocsPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ConversionProvider>
      </WorkspaceProvider>
    </ThemeProvider>
  )
}
