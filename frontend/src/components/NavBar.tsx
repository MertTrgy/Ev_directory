import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

type Props = {
  onShowAuth: () => void;
  onShowAdmin: () => void;
};

export function NavBar({ onShowAuth, onShowAdmin }: Props) {
  const { user, logout } = useAuth();
  const { pathname } = useLocation();

  return (
    <nav className="navbar">
      <div className="navbar-content">
        <Link to="/" className="navbar-brand">
          <span className="navbar-brand-mono">OpenEV</span>
          <span className="navbar-brand-name">EV Directory</span>
        </Link>

        <div className="navbar-links">
          <Link to="/" className={`nav-link${pathname === '/' ? ' nav-link-active' : ''}`}>
            Home
          </Link>
          <Link to="/favorites" className={`nav-link${pathname === '/favorites' ? ' nav-link-active' : ''}`}>
            {user ? '♥ Favorites' : 'Favorites'}
          </Link>
        </div>

        <div className="navbar-actions">
          {user ? (
            <>
              {user.role === 'admin' ? (
                <button type="button" className="btn-ghost btn-sm" onClick={onShowAdmin}>
                  Admin
                </button>
              ) : null}
              <span className="user-email">{user.email}</span>
              <button type="button" className="btn-ghost btn-sm" onClick={logout}>
                Sign out
              </button>
            </>
          ) : (
            <button type="button" className="btn-primary btn-sm" onClick={onShowAuth}>
              Sign in
            </button>
          )}
        </div>
      </div>
    </nav>
  );
}
