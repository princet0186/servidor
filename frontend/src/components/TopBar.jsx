import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Search, Bell, Clock, UserCircle, Zap, Cloud } from 'lucide-react';
import { getStatus, getConfigStatus } from '../api/servidor';

const PAGE_TITLES = {
  '/': 'Dashboard',
  '/incidents': 'Incidents',
  '/safety': 'Safety Gate',
  '/reports': 'Reports',
  '/settings': 'Settings',
};

export default function TopBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const title = PAGE_TITLES[location.pathname] || 'Servidor';
  
  // Sync the search input with ?q= on the incidents page (adjusting state during render)
  const urlQuery = location.pathname === '/incidents' ? new URLSearchParams(location.search).get('q') || '' : '';
  const [searchQuery, setSearchQuery] = useState(urlQuery);
  const [prevUrlQuery, setPrevUrlQuery] = useState(urlQuery);
  if (urlQuery !== prevUrlQuery) {
    setPrevUrlQuery(urlQuery);
    setSearchQuery(urlQuery);
  }
  const [activeAlerts, setActiveAlerts] = useState(0);
  const [engines, setEngines] = useState(null);

  useEffect(() => {
    getConfigStatus().then(setEngines).catch(() => setEngines(null));
  }, []);

  const engineLabel = (id) => (id ? id.split(':')[0].replace(/^./, (c) => c.toUpperCase()) : null);
  const primary = engineLabel(engines?.llm_engines?.primary) || engineLabel(engines?.llm_engines?.secondary);
  const fallback = engines?.llm_engines?.primary ? engineLabel(engines?.llm_engines?.secondary) : null;

  useEffect(() => {
    // Fetch active alerts for the bell badge
    async function fetchAlerts() {
      try {
        const status = await getStatus();
        setActiveAlerts(status.active_incident ? 1 : 0);
      } catch (e) {
        console.error('Failed to fetch status for topbar', e);
      }
    }
    fetchAlerts();
    // Refresh periodically
    const interval = setInterval(fetchAlerts, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleSearch = (e) => {
    if (e.key === 'Enter') {
      if (searchQuery.trim()) {
        navigate(`/incidents?q=${encodeURIComponent(searchQuery.trim())}`);
      } else {
        navigate('/incidents');
      }
    }
  };

  return (
    <header className="topbar">
      <h2 className="topbar-title text-page-title">{title}</h2>
      <div className="topbar-actions">
        {primary && (
          <span className="topbar-chip" title="Reasoning engines (primary → fallback)">
            <Zap size={13} /> {primary}{fallback ? ` → ${fallback}` : ''}
          </span>
        )}
        {engines?.platform && (
          <span className="topbar-chip" title="Where the hospital services run">
            <Cloud size={13} /> {engines.platform === 'cloud_run' ? 'Cloud Run' : 'Local'}
          </span>
        )}
        <div className="topbar-search">
          <Search size={15} className="topbar-search-icon" />
          <input
            id="global-search"
            type="text"
            className="topbar-search-input"
            placeholder="Search incidents..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={handleSearch}
          />
        </div>
        <button className="topbar-icon-btn" id="notifications-btn" title="Notifications">
          <Bell size={18} />
          {activeAlerts > 0 && <span className="topbar-badge">{activeAlerts}</span>}
        </button>
        <button className="topbar-icon-btn" id="history-btn" title="Recent Activity" onClick={() => navigate('/incidents')}>
          <Clock size={18} />
        </button>
        <button className="topbar-icon-btn topbar-avatar" id="profile-btn" title="Profile">
          <UserCircle size={22} />
        </button>
      </div>
    </header>
  );
}
