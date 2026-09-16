import { NavLink } from 'react-router-dom'

const ITEMS = [
  { to: '/', label: 'Chat', icon: '💬', end: true },
  { to: '/products', label: 'Productos', icon: '📦' },
  { to: '/sales', label: 'Ventas', icon: '🧾' },
  { to: '/purchases', label: 'Compras', icon: '🛒' },
  { to: '/documents', label: 'Docs', icon: '📸' },
  { to: '/cashbox', label: 'Caja', icon: '💰' },
]

export function BottomNav() {
  return (
    <nav className="bottom-nav" aria-label="Navegación principal">
      {ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => `bottom-nav-item${isActive ? ' active' : ''}`}
        >
          <span aria-hidden="true">{item.icon}</span>
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
