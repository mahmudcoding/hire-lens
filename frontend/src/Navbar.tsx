import { cn } from '@heroui/react'
import { Link, NavLink } from 'react-router'

const pages = [
  { to: '/', label: 'Home' },
  { to: '/check', label: 'Check' },
  { to: '/history', label: 'History' },
  { to: '/profile', label: 'Profile' },
]

const navLink = ({ isActive }: { isActive: boolean }) =>
  cn(
    'rounded-full px-3 py-1.5 text-sm font-medium transition-colors',
    isActive ? 'bg-surface-secondary text-foreground' : 'text-muted hover:text-foreground',
  )

export function Navbar() {
  return (
    <header className="sticky top-0 z-10 border-b border-border bg-background/85 backdrop-blur">
      <nav
        className="mx-auto flex min-h-14 max-w-[1040px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-2"
        aria-label="Main"
      >
        <Link to="/" className="text-lg font-semibold tracking-tight text-foreground">
          HireLens<span className="text-success">.</span>
        </Link>
        <ul className="m-0 flex list-none items-center gap-1 p-0">
          {pages.map(({ to, label }) => (
            <li key={to}>
              {/* `end` keeps Home from lighting up on every page, since every path starts with "/". */}
              <NavLink to={to} end={to === '/'} className={navLink}>
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
        <Link to="/check" className="button button--primary button--sm ml-auto font-semibold">
          Check my resume
        </Link>
      </nav>
    </header>
  )
}
