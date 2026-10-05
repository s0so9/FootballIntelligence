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
        <button
          className="header-icon-button"
          aria-label="Bildirimler"
          title="Bildirimler (yakında)"
        >
          🔔
        </button>
        <button
          className="header-icon-button"
          aria-label="Profil"
          title="Profil (yakında)"
        >
          👤
        </button>
      </div>
    </header>
  );
}
