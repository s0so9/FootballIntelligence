import './Header.css';

interface HeaderProps {
  onToggleMobileMenu: () => void;
}

export function Header({ onToggleMobileMenu }: HeaderProps) {
  return (
    <header className="app-header">
      <div className="header-left">
        <button
          className="mobile-menu-button"
          onClick={onToggleMobileMenu}
          aria-label="Menüyü aç"
        >
          <span>☰</span>
        </button>
        <h1 className="header-title">MENSIONE</h1>
      </div>

      <div className="header-right">
        <div className="header-info">
          <span className="status-dot"></span>
          <span>Sistem Aktif</span>
        </div>
      </div>
    </header>
  );
}
