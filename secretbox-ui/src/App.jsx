import useWorkspace from './hooks/useWorkspace';
import Topbar from './components/Topbar';
import Overview from './components/Overview';
import Navigation from './components/Navigation';
import SlideTransition from './components/SlideTransition';
import AuthPage from './pages/AuthPage';
import CatalogPage from './pages/CatalogPage';
import AnalyticsPage from './pages/AnalyticsPage';
import ChatPage from './pages/ChatPage';
import './App.css';

export default function App() {
  const workspace = useWorkspace();
  if (!workspace.token && !workspace.isGuest) return <AuthPage {...workspace} />;

  return (
    <div className="app-shell">
      <Topbar {...workspace} />
      <main className="dashboard">
        {workspace.isGuest && <p className="notice guest-notice" role="status">Guest mode · Saved menus included with this version of SecretBox. Prices may have changed. Sign in to edit menus or use team chat.</p>}
        <Overview {...workspace} />
        <Navigation {...workspace} />
        <div className="view-stage">
          <SlideTransition transitionKey={workspace.activeView} index={['catalog', 'analytics', 'chat'].indexOf(workspace.activeView)}>
            {workspace.activeView === 'catalog' && <CatalogPage {...workspace} />}
            {workspace.activeView === 'analytics' && <AnalyticsPage {...workspace} />}
            {workspace.activeView === 'chat' && <ChatPage {...workspace} />}
          </SlideTransition>
        </div>
        <footer className="footer"><span>secretbox<span className="brand-period">.</span></span><span>Made for the love of a good cup.</span></footer>
      </main>
    </div>
  );
}
