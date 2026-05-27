import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from './providers/AuthProvider'
import { WebSocketProvider } from './providers/WebSocketProvider'
import { NotificationProvider } from './providers/NotificationProvider'
import { useAuthStore } from './stores/authStore'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import LoginPage from './pages/LoginPage'
import AuthCallbackPage from './pages/AuthCallbackPage'
import OpportunitiesPage from './pages/OpportunitiesPage'
import OpportunityDetail from './pages/OpportunityDetail'
import ChatPage from './pages/ChatPage'
import PortfolioPage from './pages/PortfolioPage'
import TradesPage from './pages/TradesPage'
import SettingsPage from './pages/SettingsPage'
import SystemStatusPage from './pages/SystemStatusPage'

const queryClient = new QueryClient()

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore(s => s.token)
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

function LoginRoute({ children }: { children: React.ReactNode }) {
  const token = useAuthStore(s => s.token)
  if (token) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <WebSocketProvider>
            <NotificationProvider>
              <Routes>
                <Route path="/login" element={<LoginRoute><LoginPage /></LoginRoute>} />
                <Route path="/auth/callback" element={<AuthCallbackPage />} />
                <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
                  <Route path="/" element={<Dashboard />} />
                  <Route path="/opportunities" element={<OpportunitiesPage />} />
                  <Route path="/opportunities/:id" element={<OpportunityDetail />} />
                  <Route path="/chat" element={<ChatPage />} />
                  <Route path="/portfolio" element={<PortfolioPage />} />
                  <Route path="/trades" element={<TradesPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="/status" element={<SystemStatusPage />} />
                </Route>
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </NotificationProvider>
          </WebSocketProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
