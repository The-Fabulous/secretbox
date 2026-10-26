import { formatDate } from '../utils/format';

export default function ChatPage({ chatError, chatMessages, sendChat, chatInput, setChatInput, isGuest, logout }) {
  if (isGuest) return (
    <section className="content-panel chat-panel">
      <div className="empty-state">
        <span aria-hidden="true">✉</span><h3>Join the team conversation</h3>
        <p>Sign in to read and send messages.</p>
        <button className="button button-primary" onClick={logout}>Sign in</button>
      </div>
    </section>
  );
  return (
    <section className="content-panel chat-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">STAY IN THE LOOP</p>
          <h2>Team chat</h2>
          <p className="panel-description">Share menu notes with everyone at the desk.</p>
        </div>
        <span className="live-badge"><span /> LIVE</span>
      </div>
      {chatError && <p className="notice notice-error">{chatError}</p>}
      <div className="chat-feed">
        {chatMessages.length ? chatMessages.map((message, index) => (
          <article className="chat-bubble" key={`${message.timestamp}-${index}`}>
            <div><strong>{message.username}</strong><time>{formatDate(`${message.timestamp}Z`)}</time></div>
            <p>{message.text}</p>
          </article>
        )) : <div className="empty-state"><span>✉</span><h3>Start the conversation</h3><p>Share a menu update or a note with your team.</p></div>}
      </div>
      <form className="chat-form" onSubmit={sendChat}>
        <input value={chatInput} onChange={(event) => setChatInput(event.target.value)} placeholder="Write a message…" aria-label="Chat message" />
        <button className="button button-primary" type="submit">Send <span aria-hidden="true">↗</span></button>
      </form>
    </section>
  );
}
