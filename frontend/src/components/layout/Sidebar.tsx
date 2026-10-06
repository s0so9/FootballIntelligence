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
  icon: JSX.Element;
  isPrimary?: boolean;
}

// SVG Icon Components
const HomeIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M3 10L10 3L17 10V17C17 17.5304 16.7893 18.0391 16.4142 18.4142C16.0391 18.7893 15.5304 19 15 19H5C4.46957 19 3.96086 18.7893 3.58579 18.4142C3.21071 18.0391 3 17.5304 3 17V10Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="M8 19V11H12V19" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const LiveIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="2"/>
    <circle cx="10" cy="10" r="3" fill="currentColor"/>
  </svg>
);

const MatchesIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="2"/>
    <path d="M3 10H17M10 3C7.5 5 7.5 15 10 17M10 3C12.5 5 12.5 15 10 17" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
  </svg>
);

const PredictionsIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M10 2L12.5 7L18 8L14 12L15 18L10 15L5 18L6 12L2 8L7.5 7L10 2Z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const EasyMatchIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M16 6L8 14L4 10" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const AnalyticsIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <path d="M3 17V11M10 17V3M17 17V7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>
);

const SettingsIcon = () => (
  <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="10" cy="10" r="2" stroke="currentColor" strokeWidth="2"/>
    <path d="M10 2V4M10 16V18M18 10H16M4 10H2M15.5 4.5L14 6M6 14L4.5 15.5M15.5 15.5L14 14M6 6L4.5 4.5" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
  </svg>
);

const navigationItems: NavItem[] = [
  { path: '/', label: 'Ana Sayfa', icon: <HomeIcon />, isPrimary: true },
  { path: '/matches', label: 'Canlı', icon: <LiveIcon />, isPrimary: true },
  { path: '/matches', label: 'Maçlar', icon: <MatchesIcon />, isPrimary: true },
  { path: '/predictions', label: 'Tahminler', icon: <PredictionsIcon />, isPrimary: true },
  { path: '/easy-matches', label: 'Easy Match', icon: <EasyMatchIcon />, isPrimary: true },
  { path: '/analytics', label: 'Analiz', icon: <AnalyticsIcon />, isPrimary: true },
  { path: '/settings', label: 'Ayarlar', icon: <SettingsIcon />, isPrimary: false },
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
      aria-label="Main navigation"
    >
      {/* MENSIONE Brand */}
      <div className="sidebar__brand">
        <div className="sidebar__logo">
          <div className="sidebar__logo-image-container">
            <img 
              src="/torres.jpg" 
              alt="MENSIONE" 
              className="sidebar__logo-image"
            />
          </div>
        </div>
        {!collapsed && (
          <p className="sidebar__tagline">Football Intelligence</p>
        )}
      </div>

      {/* Navigation */}
      <nav className="sidebar__nav">
        {!collapsed && (
          <div className="sidebar__section-label">ANA MENÜ</div>
        )}
        
        <ul className="sidebar__nav-list" role="list">
          {navigationItems.map((item, index) => {
            // Add divider before Settings (last non-primary item)
            const showDivider = !item.isPrimary && index > 0 && navigationItems[index - 1].isPrimary;
            
            return (
              <li key={`${item.path}-${item.label}`}>
                {showDivider && (
                  <>
                    <div className="sidebar__nav-divider" />
                    {!collapsed && (
                      <div className="sidebar__section-label sidebar__section-label--secondary">
                        AYARLAR
                      </div>
                    )}
                  </>
                )}
                <NavLink
                  to={item.path}
                  className={({ isActive }) =>
                    `sidebar__nav-link ${isActive ? 'sidebar__nav-link--active' : ''} ${!item.isPrimary ? 'sidebar__nav-link--secondary' : ''}`
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
            );
          })}
        </ul>
      </nav>

      {/* Footer */}
      {!collapsed && (
        <div className="sidebar__footer">
          <p className="sidebar__footer-text">Developed by Orkun Acar</p>
        </div>
      )}

      {/* Collapse Toggle - Desktop Only */}
      <button
        className="sidebar__collapse-btn"
        onClick={onCollapse}
        aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        aria-expanded={!collapsed}
      >
        <span className="sidebar__collapse-icon">{collapsed ? '→' : '←'}</span>
      </button>
    </aside>
  );
}
