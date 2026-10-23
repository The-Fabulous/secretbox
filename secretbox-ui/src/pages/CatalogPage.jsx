import { formatDate } from '../utils/format';
import { getCategory } from '../categories';
import MenuEditor from '../components/MenuEditor';
import SlideTransition from '../components/SlideTransition';

export default function CatalogPage({ shops, selectedShop, setMenuLoading, setMenuError, setSelectedShop, setSearch, setCategory, setUpdateMessage, visibleItems, menu, search, menuError, updateMessage, menuLoading, availableCategories, activeCategory, categoryCounts, sortState, toggleSort, sort, manualText, setManualText, savingMenu, importFile, saveMenu }) {
  return (
    <section className="content-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">YOUR NEIGHBOURHOOD</p>
          <h2>Cafe menus</h2>
          <p className="panel-description">Browse current drinks, cup sizes and listed prices.</p>
        </div>
        <span className="live-badge"><span /> MENU DESK</span>
      </div>
      <div className="catalog-layout">
        <aside className="cafe-list">
          <p className="section-label">YOUR CAFES <span>{shops.length}</span></p>
          {shops.length ? shops.map((shop, index) => (
            <button
              className={selectedShop === shop ? 'cafe-option selected' : 'cafe-option'}
              key={shop}
              onClick={() => {
                if (selectedShop !== shop) setMenuLoading(true);
                setMenuError('');
                setSelectedShop(shop);
                setSearch('');
                setCategory('all');
                setUpdateMessage('');
              }}
            >
              <span className={`cafe-avatar cafe-avatar-${index % 4}`}>{shop.slice(0, 1).toUpperCase()}</span>
              <span className="cafe-option-name">{shop}<small>Coffee menu</small></span>
              <span className="cafe-chevron">›</span>
            </button>
          )) : <p className="empty-note">No cafe menus found.</p>}
        </aside>

        <SlideTransition className="menu-content" transitionKey={selectedShop} index={shops.indexOf(selectedShop)}>
          <div className="menu-toolbar">
            <div>
              <h3>{selectedShop || 'Select a cafe'}</h3>
              <p>
                {visibleItems.length === menu.items.length
                  ? `${menu.items.length} drinks`
                  : `${visibleItems.length} of ${menu.items.length} drinks`}
                <span className="small-divider">·</span> Updated {formatDate(menu.updated_at)}
              </p>
            </div>
            <label className="search-field">
              <span aria-hidden="true">⌕</span>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Find a drink"
                aria-label="Search drinks"
              />
            </label>
          </div>
          {menuError && <p className="notice notice-error" role="alert">{menuError}</p>}
          {updateMessage && <p className="notice notice-success" role="status">{updateMessage}</p>}
          {!menuLoading && availableCategories.length > 0 && (
            <div className="category-bar" role="group" aria-label="Filter drinks by category">
              <button
                type="button"
                className={activeCategory === 'all' ? 'category-chip active' : 'category-chip'}
                aria-pressed={activeCategory === 'all'}
                onClick={() => setCategory('all')}
              >
                All <span className="chip-count">{menu.items.length}</span>
              </button>
              {availableCategories.map((entry) => (
                <button
                  type="button"
                  key={entry.id}
                  className={activeCategory === entry.id ? 'category-chip active' : 'category-chip'}
                  style={{ '--chip-color': entry.color }}
                  aria-pressed={activeCategory === entry.id}
                  onClick={() => setCategory(entry.id)}
                >
                  <span className="chip-dot" />{entry.label} <span className="chip-count">{categoryCounts[entry.id]}</span>
                </button>
              ))}
            </div>
          )}
          {menuLoading ? (
            <div className="loading-state"><span className="spinner" /> Loading menu...</div>
          ) : (
            <div className="table-wrap menu-reveal">
              <table className="menu-table">
                <thead>
                  <tr>
                    <th aria-sort={sortState('name')}>
                      <button type="button" className="sort-button" onClick={() => toggleSort('name')}>
                        DRINK <span className="sort-arrow" aria-hidden="true">{sort.key === 'name' ? (sort.dir === 'asc' ? '↑' : '↓') : '↕'}</span>
                      </button>
                    </th>
                    <th className="col-category">CATEGORY</th>
                    <th aria-sort={sortState('size')}>
                      <button type="button" className="sort-button" onClick={() => toggleSort('size')}>
                        VOLUME <span className="sort-arrow" aria-hidden="true">{sort.key === 'size' ? (sort.dir === 'asc' ? '↑' : '↓') : '↕'}</span>
                      </button>
                    </th>
                    <th className="price-heading" aria-sort={sortState('price')}>
                      <button type="button" className="sort-button" onClick={() => toggleSort('price')}>
                        PRICE <span className="sort-arrow" aria-hidden="true">{sort.key === 'price' ? (sort.dir === 'asc' ? '↑' : '↓') : '↕'}</span>
                      </button>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {visibleItems.map((item, index) => {
                    const itemCategory = getCategory(item.category);
                    return (
                      <tr key={`${item.name}-${item.size_ml}-${index}`}>
                        <td><span className="drink-dot" style={{ background: itemCategory.color }} />{item.name}</td>
                        <td className="col-category"><span className="category-tag" style={{ '--chip-color': itemCategory.color }}>{itemCategory.label}</span></td>
                        <td>{item.size_ml ? <span className="volume-pill">{item.size_ml} ml</span> : <span className="volume-missing">Not listed</span>}</td>
                        <td className="price-cell">{Number(item.price).toLocaleString()} <span>₸</span></td>
                      </tr>
                    );
                  })}
                  {!visibleItems.length && !menuLoading && (
                    <tr><td className="empty-row" colSpan="4">
                      {menu.items.length ? 'No drinks match your search.' : 'This menu does not have any drinks yet.'}
                    </td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
          <div className="volume-note"><span aria-hidden="true">ⓘ</span> Sizes show only when listed by the cafe. Missing sizes are never estimated.</div>
        </SlideTransition>
      </div>

      <MenuEditor
        manualText={manualText}
        setManualText={setManualText}
        setUpdateMessage={setUpdateMessage}
        savingMenu={savingMenu}
        selectedShop={selectedShop}
        importFile={importFile}
        saveMenu={saveMenu}
      />
    </section>
  );
}
