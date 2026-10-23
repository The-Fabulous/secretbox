
export default function AnalyticsPage({ analytics, analyticsError, analyticsLoading, analyticsColumns }) {
  return (
    <section className="content-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">COMPARE THE POUR</p>
          <h2>Price comparison</h2>
          <p className="panel-description">See how listed prices compare for the same drink and size.</p>
        </div>
        <span className="comparison-count">{analytics.length} matched drinks</span>
      </div>
      {analyticsError && <p className="notice notice-error">{analyticsError}</p>}
      {analyticsLoading ? (
        <div className="loading-state"><span className="spinner" /> Comparing cafe menus...</div>
      ) : analytics.length ? (
        <div className="table-wrap">
          <table className="menu-table analytics-table">
            <thead><tr>{analyticsColumns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
            <tbody>{analytics.map((row, index) => (
              <tr key={`${row['Напиток']}-${row['Объём']}-${index}`}>
                {analyticsColumns.map((column) => (
                  <td key={column}>{row[column] ?? '—'}{column === 'Разброс' ? ' ₸' : ''}</td>
                ))}
              </tr>
            ))}</tbody>
          </table>
        </div>
      ) : !analyticsError && (
        <div className="empty-state"><span>☕</span><h3>More menus, better comparisons</h3><p>Matching drinks from at least two cafes will appear here.</p></div>
      )}
      <p className="volume-note"><span aria-hidden="true">ⓘ</span> Only exact drink-name and volume matches are compared.</p>
    </section>
  );
}
