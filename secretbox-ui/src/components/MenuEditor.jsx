
export default function MenuEditor({ manualText, setManualText, setUpdateMessage, savingMenu, selectedShop, importFile, saveMenu, isGuest }) {
  if (isGuest) return <p className="volume-note">Sign in to upload or edit cafe menus.</p>;
  return (
    <details className="update-panel">
      <summary><span className="update-summary-icon">＋</span><span><strong>Update this menu</strong><small>Paste a list or upload the latest cafe price file.</small></span><span className="summary-arrow">⌄</span></summary>
      <div className="update-tools">
        <div className="update-instructions">
          <p>Edit the menu JSON: each item has a name, size_ml and price in tenge. Use null when the volume is not listed.</p>
          <p>You can also import an older text list. It will be converted to JSON when saved.</p>
        </div>
        <label className="upload-button">
          <span aria-hidden="true">↑</span> Upload menu
          <input type="file" accept=".json,application/json,.txt,text/plain" onChange={importFile} disabled={savingMenu || !selectedShop} />
        </label>
        <textarea
          className="menu-editor"
          value={manualText}
          onChange={(event) => {
            setManualText(event.target.value);
            setUpdateMessage('');
          }}
          placeholder={'{"currency":"KZT","items":[{"name":"Latte","size_ml":350,"price":1190}]}'}
          aria-label="Cafe menu JSON"
        />
        <button className="button button-primary save-menu" onClick={() => saveMenu(manualText)} disabled={savingMenu || !selectedShop}>
          {savingMenu ? 'Saving menu…' : 'Save menu'} <span aria-hidden="true">↗</span>
        </button>
      </div>
    </details>
  );
}
