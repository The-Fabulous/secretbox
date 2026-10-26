import Brand from './Brand';

export default function Topbar({ displayName, logout, isGuest }) {
  return (
    <header className="topbar">
      <Brand />
      <div className="topbar-right">
        <span className="user-chip"><span className="user-dot" />{displayName || 'Cafe team'}</span>
        <button className="button button-quiet sign-out" onClick={logout}>{isGuest ? 'Sign in' : 'Sign out'} <span aria-hidden="true">↗</span></button>
      </div>
    </header>
  );
}
