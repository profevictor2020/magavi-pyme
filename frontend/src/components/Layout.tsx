import { Link, Outlet } from 'react-router-dom'
import { useCompany } from '../context/CompanyContext'
import { BottomNav } from './BottomNav'

export function Layout() {
  const { activeCompany } = useCompany()

  return (
    <div className="app-shell">
      <header className="top-bar">
        <span className="top-bar-title">MAGAVI</span>
        <Link to="/companies" className="top-bar-company">
          {activeCompany?.name ?? 'Elegir empresa'}
        </Link>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
      <BottomNav />
    </div>
  )
}
