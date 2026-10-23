import { Link, NavLink } from 'react-router'
import './Navbar.css'

const pages = [
  { to: '/', label: 'Home' },
  { to: '/history', label: 'History' },
  { to: '/profile', label: 'Profile' },
]

export function Navbar() {
  return (
    <header className="navbar">
      <nav className="navbar-inner" aria-label="Main">
        <Link to="/" className="navbar-brand">
          HireLens
        </Link>
        <ul className="navbar-links">
          {pages.map(({ to, label }) => (
            <li key={to}>
              {/* `end` keeps Home from lighting up on every page, since every path starts with "/". */}
              <NavLink to={to} end={to === '/'}>
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </header>
  )
}
