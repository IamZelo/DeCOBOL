import { Link, NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'
import { ThemeToggle } from './ThemeToggle'

const LINKS = [
  { to: '/workspace', label: 'Workspace' },
  { to: '/convert', label: 'Convert' },
  { to: '/pipeline', label: 'Pipeline' },
  { to: '/diff', label: 'Analysis' },
  { to: '/docs', label: 'Documentation' },
  { to: '/history', label: 'Job History' },
]

export function TopNav({ right }: { right?: ReactNode }) {
  return (
    <header className="nav">
      <div className="nav-left">
        <Link to="/" className="nav-brand">
          <span className="nav-word">DeCOBOL</span>
        </Link>
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
      <div className="nav-right">
        {right}
        <ThemeToggle />
      </div>
    </header>
  )
}
