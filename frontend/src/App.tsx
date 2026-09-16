import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import { CompanyProvider } from './context/CompanyContext'
import { Layout } from './components/Layout'
import { RequireAuth, RequireCompany } from './components/ProtectedRoute'
import { LoginPage } from './pages/LoginPage'
import { RegisterPage } from './pages/RegisterPage'
import { CompanyPage } from './pages/CompanyPage'
import { ChatPage } from './pages/ChatPage'
import { ProductsPage } from './pages/ProductsPage'
import { SalesPage } from './pages/SalesPage'
import { PurchasesPage } from './pages/PurchasesPage'
import { CashboxPage } from './pages/CashboxPage'
import { DocumentsPage } from './pages/DocumentsPage'
import { DocumentDetailPage } from './pages/DocumentDetailPage'

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <CompanyProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />

            <Route element={<RequireAuth />}>
              <Route path="/companies" element={<CompanyPage />} />

              <Route element={<RequireCompany />}>
                <Route element={<Layout />}>
                  <Route path="/" element={<ChatPage />} />
                  <Route path="/products" element={<ProductsPage />} />
                  <Route path="/sales" element={<SalesPage />} />
                  <Route path="/purchases" element={<PurchasesPage />} />
                  <Route path="/cashbox" element={<CashboxPage />} />
                  <Route path="/documents" element={<DocumentsPage />} />
                  <Route path="/documents/:id" element={<DocumentDetailPage />} />
                </Route>
              </Route>
            </Route>

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </CompanyProvider>
      </AuthProvider>
    </BrowserRouter>
  )
}

export default App
