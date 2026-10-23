import Brand from '../components/Brand';
import SlideTransition from '../components/SlideTransition';

export default function AuthPage({ authMode, username, password, authMessage, setUsername, setPassword, setAuthMode, setAuthMessage, submitAuth }) {
  return (
    <main className="auth-page">
      <section className="auth-story">
        <Brand />
        <div className="auth-copy">
          <p className="eyebrow">THE CAFE PRICE DESK</p>
          <h1>Good coffee.<br />Clear numbers.</h1>
          <p>Keep every cafe menu, cup size and price in one calm place.</p>
        </div>
        <div className="auth-cup" aria-hidden="true"><span /></div>
        <p className="auth-footnote">A better view of the coffee around you.</p>
      </section>
      <section className="auth-side">
        <SlideTransition className="auth-card" transitionKey={authMode} index={authMode === 'login' ? 0 : 1}>
          <p className="eyebrow">{authMode === 'login' ? 'WELCOME BACK' : 'GET STARTED'}</p>
          <h2>{authMode === 'login' ? 'Sign in to SecretBox' : 'Create your account'}</h2>
          <p className="auth-subtitle">Your cafe menu workspace is waiting.</p>
          <form onSubmit={submitAuth} className="auth-form">
            <label>
              Username
              <input
                autoComplete="username"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="Your username"
                required
              />
            </label>
            <label>
              Password
              <input
                autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                required
              />
            </label>
            {authMessage && <p className="form-message">{authMessage}</p>}
            <button className="button button-primary auth-submit" type="submit">
              {authMode === 'login' ? 'Sign in' : 'Create account'} <span aria-hidden="true">↗</span>
            </button>
          </form>
          <p className="auth-switch">
            {authMode === 'login' ? 'New to SecretBox?' : 'Already have an account?'}
            <button
              type="button"
              onClick={() => {
                setAuthMode(authMode === 'login' ? 'register' : 'login');
                setAuthMessage('');
              }}
            >
              {authMode === 'login' ? 'Create an account' : 'Sign in'}
            </button>
          </p>
        </SlideTransition>
        <span className="secure-note"><span aria-hidden="true">◈</span> Private menu workspace</span>
      </section>
    </main>
  );
}
