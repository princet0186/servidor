import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Search, Bell, Clock, UserCircle } from 'lucide-react';
import { getStatus } from '../api/servidor';

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
  
  const [searchQuery, setSearchQuery] = useState('');
  const [activeAlerts, setActiveAlerts] = useState(0);

  useEffect(() => {
    // Sync search input with URL if we are on incidents page
    if (location.pathname === '/incidents') {
      const params = new URLSearchParams(location.search);
      if (params.has('q')) {
        setSearchQuery(params.get('q'));
      } else {
        setSearchQuery('');
      }
    } else {
      setSearchQuery('');
    }
  }, [location]);

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
