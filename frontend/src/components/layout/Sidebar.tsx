import { NavLink } from 'react-router-dom';
import './Sidebar.css';

interface SidebarProps {
  collapsed: boolean;
  mobileOpen: boolean;
  onCollapse: () => void;
  onCloseMobile: () => void;
}

interface NavItem {
  path: string;
  label: string;
  icon: string;
}

const navigationItems: NavItem[] = [
  { path: '/', label: 'Ana Sayfa', icon: '🏠' },
  { path: '/matches', label: 'Maçlar', icon: '⚽' },
  { path: '/predictions', label: 'Tahminler', icon: '🎯' },
  { path: '/easy-matches', label: 'Kolay Maçlar', icon: '✅' },
  { path: '/analytics', label: 'Analiz', icon: '📈' },
  { path: '/settings', label: 'Ayarlar', icon: '⚙️' },
];

export function Sidebar({ collapsed, mobileOpen, onCollapse, onCloseMobile }: SidebarProps) {
  const handleNavClick = () => {
    // Close mobile menu on navigation
    if (window.innerWidth <= 768) {
      onCloseMobile();
    }
  };

  return (
    <aside
      className={`sidebar ${collapsed ? 'sidebar--collapsed' : ''} ${
        mobileOpen ? 'sidebar--mobile-open' : ''
      }`}
      aria-label="Ana navigasyon"
    >
      {/* Logo / Brand */}
      <div className="sidebar__brand">
        <div className="sidebar__logo">
          <span className="sidebar__logo-icon">⚡</span>
          {!collapsed && <span className="sidebar__logo-text">MENSIONE</span>}
        </div>
        {!collapsed && (
          <p className="sidebar__tagline">Football Intelligence</p>
        )}
      </div>

      {/* Navigation */}
      <nav className="sidebar__nav">
        <ul className="sidebar__nav-list" role="list">
          {navigationItems.map((item) => (
            <li key={item.path}>
              <NavLink
                to={item.path}
                className={({ isActive }) =>
                  `sidebar__nav-link ${isActive ? 'sidebar__nav-link--active' : ''}`
                }
                onClick={handleNavClick}
                aria-label={item.label}
                end={item.path === '/'}
              >
                <span className="sidebar__nav-icon" aria-hidden="true">
                  {item.icon}
                </span>
                {!collapsed && (
                  <span className="sidebar__nav-label">{item.label}</span>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      {/* Collapse Toggle - Desktop Only */}
      <button
        className="sidebar__collapse-btn"
        onClick={onCollapse}
        aria-label={collapsed ? 'Kenar çubuğunu genişlet' : 'Kenar çubuğunu daralt'}
        aria-expanded={!collapsed}
      >
        <span className="sidebar__collapse-icon">{collapsed ? '→' : '←'}</span>
      </button>
    </aside>
  );
}
