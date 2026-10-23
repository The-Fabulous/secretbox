import { useLayoutEffect, useRef } from 'react';

export default function Navigation({ activeView, setActiveView, setAnalyticsLoading, setAnalyticsError }) {
  const navigation = useRef(null);
  useLayoutEffect(() => {
    const nav = navigation.current;
    const updateIndicator = () => {
      const active = nav.querySelector('.view-tab.active');
      if (!active) return;
      nav.style.setProperty('--tab-left', `${active.offsetLeft + 5}px`);
      nav.style.setProperty('--tab-width', `${active.offsetWidth - 10}px`);
    };
    updateIndicator();
    const observer = new ResizeObserver(updateIndicator);
    observer.observe(nav);
    nav.querySelectorAll('.view-tab').forEach((tab) => observer.observe(tab));
    return () => observer.disconnect();
  }, [activeView]);

  return (
    <nav ref={navigation} className="view-tabs" aria-label="Main navigation">
      <span className="view-tab-indicator" aria-hidden="true" />
      <button aria-current={activeView === 'catalog' ? 'page' : undefined} className={activeView === 'catalog' ? 'view-tab active' : 'view-tab'} onClick={() => setActiveView('catalog')}>
        <span aria-hidden="true">▤</span> Cafe menus
      </button>
      <button aria-current={activeView === 'analytics' ? 'page' : undefined} className={activeView === 'analytics' ? 'view-tab active' : 'view-tab'} onClick={() => {
        if (activeView !== 'analytics') setAnalyticsLoading(true);
        setAnalyticsError('');
        setActiveView('analytics');
      }}>
        <span aria-hidden="true">↗</span> Price comparison
      </button>
      <button aria-current={activeView === 'chat' ? 'page' : undefined} className={activeView === 'chat' ? 'view-tab active' : 'view-tab'} onClick={() => setActiveView('chat')}>
        <span aria-hidden="true">◌</span> Team chat
      </button>
    </nav>
  );
}
