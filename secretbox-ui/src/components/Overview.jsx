import { formatDate, getGreeting } from '../utils/format';

export default function Overview({ displayName, shops, menu, selectedShop }) {
  return (
    <>
    <section className="welcome-row">
      <div>
        <p className="eyebrow">CAFE MENU INTELLIGENCE</p>
        <h1>{getGreeting()}{displayName ? `, ${displayName}` : ''}<span className="heading-period">.</span></h1>
        <p className="welcome-subtitle">A clear look at the drinks, sizes and prices on your watch.</p>
      </div>
      <div className="coffee-stamp" aria-hidden="true">
        <span className="stamp-steam">〰</span><span className="stamp-cup">▱</span>
        <span className="stamp-caption">BREW<br />BETTER</span>
      </div>
    </section>

    <section className="stat-grid" aria-label="Cafe menu overview">
      <article className="stat-card">
        <span className="stat-icon icon-peach">⌂</span>
        <span className="stat-label">CAFES TRACKED</span>
        <strong>{shops.length.toString().padStart(2, '0')}</strong>
        <span className="stat-note">In your price list</span>
      </article>
      <article className="stat-card">
        <span className="stat-icon icon-green">☕</span>
        <span className="stat-label">DRINKS IN VIEW</span>
        <strong>{(menu.items || []).length.toString().padStart(2, '0')}</strong>
        <span className="stat-note">{selectedShop || 'Choose a cafe'}</span>
      </article>
      <article className="stat-card stat-card-update">
        <span className="stat-icon icon-gold">↻</span>
        <span className="stat-label">MENU LAST UPDATED</span>
        <strong className="stat-date">{formatDate(menu.updated_at)}</strong>
        <span className="stat-note">From the latest cafe list</span>
      </article>
    </section>
    </>
  );
}
