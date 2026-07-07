import { Link, useLocation } from 'react-router-dom'
import { useTheme } from '../ThemeContext'

export default function Layout({ children }: { children: React.ReactNode }) {
  const loc = useLocation()
  const { theme, toggle } = useTheme()
  const links = [
    { to: '/', label: 'Bible' },
    { to: '/commentary', label: 'Commentary' },
  ]

  return (
    <div>
      <header style={{
        background: 'var(--bg-card)',
        borderBottom: '1px solid var(--border)',
        padding: '0 16px',
        position: 'sticky',
        top: 0,
        zIndex: 100,
      }}>
        <div style={{
          maxWidth: 1200, margin: '0 auto',
          display: 'flex', alignItems: 'center', gap: 20,
          height: 52,
        }}>
          <Link to="/" style={{
            fontSize: 18, fontWeight: 700, color: 'var(--accent)',
            textDecoration: 'none', whiteSpace: 'nowrap',
          }}>
            Bible A1
          </Link>
          <nav style={{ display: 'flex', gap: 8, fontSize: 14 }}>
            {links.map(l => (
              <Link
                key={l.to}
                to={l.to}
                style={{
                  color: loc.pathname === l.to ? 'var(--accent)' : 'var(--text-secondary)',
                  textDecoration: 'none',
                  padding: '6px 10px',
                  borderRadius: 6,
                  background: loc.pathname === l.to ? 'var(--bg-elevated)' : 'transparent',
                  transition: 'background 0.15s',
                }}
              >
                {l.label}
              </Link>
            ))}
          </nav>
          <div style={{ marginLeft: 'auto' }}>
            <button
              onClick={toggle}
              className="secondary"
              style={{ padding: '6px 10px', fontSize: 16, lineHeight: 1 }}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              {theme === 'dark' ? '☀' : '☾'}
            </button>
          </div>
        </div>
      </header>
      {children}
    </div>
  )
}
