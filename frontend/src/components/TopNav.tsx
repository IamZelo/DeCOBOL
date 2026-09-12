import { NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'

const LINKS = [
  { to: '/workspace', label: 'Workspace' },
  { to: '/convert', label: 'Convert' },
  { to: '/pipeline', label: 'Pipeline' },
  { to: '/diff', label: 'Diff & Delivery' },
  { to: '/graph', label: 'Structure' },
  { to: '/history', label: 'Job History' },
]

export function TopNav({ right }: { right?: ReactNode }) {
  return (
    <header className="nav">
      <div className="nav-left">
        <div className="nav-brand">
          <span className="nav-word">DeCOBOL</span>
          <span className="nav-badge">EBCDIC &rarr; JVM 21</span>
        </div>
        <nav className="nav-links">
          {LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                isActive ? 'nav-link is-active' : 'nav-link'
              }
            >
              {link.label}
            </NavLink>
          ))}
        </nav>
      </div>
      <div className="nav-right">{right}</div>
    </header>
  )
}
