import { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, AlertTriangle, Shield, FileText, Settings, Activity, Megaphone, HelpCircle, LogOut } from 'lucide-react';
import { getStatus } from '../api/servidor';

export default function Sidebar() {
  const [isConnected, setIsConnected] = useState(false);

  useEffect(() => {
    async function checkConnection() {
      try {
        await getStatus();
        setIsConnected(true);
      } catch (e) {
        setIsConnected(false);
      }
    }
    checkConnection();
    const interval = setInterval(checkConnection, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <Activity size={24} color="var(--primary-container)" />
        <h1 className="text-section-header">Servidor</h1>
      </div>
      
      <nav className="sidebar-nav">
        <NavLink 
          to="/" end
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <LayoutDashboard size={18} />
          Dashboard
        </NavLink>
        <NavLink 
          to="/incidents" 
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <AlertTriangle size={18} />
          Incidents
        </NavLink>
        <NavLink 
          to="/safety" 
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <Shield size={18} />
          Safety Gate
        </NavLink>
        <NavLink 
          to="/reports" 
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <FileText size={18} />
          Reports
        </NavLink>
        <NavLink 
          to="/settings" 
          className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
        >
          <Settings size={18} />
          Settings
        </NavLink>
      </nav>

      <div className="sidebar-bottom">
        <button className="emergency-btn" id="emergency-alert-btn">
          <Megaphone size={18} />
          Emergency Alert
        </button>

        <div className="sidebar-bottom-links">
          <a href="#" className="nav-item" id="support-link">
            <HelpCircle size={18} />
            Support
          </a>
          <a href="#" className="nav-item" id="signout-link">
            <LogOut size={18} />
            Sign Out
          </a>
        </div>

        <div className="sidebar-footer">
          <div className={`status-dot ${isConnected ? 'safe' : 'critical'}`}></div>
          <span>Status: {isConnected ? 'Online' : 'Offline'}</span>
        </div>
      </div>
    </aside>
  );
}
