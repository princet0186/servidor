import React from 'react';
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, AlertTriangle, Shield, FileText, Settings, Activity } from 'lucide-react';

export default function Sidebar() {
  const isConnected = true; // In the future, this can be dynamic

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <Activity size={24} color="var(--primary-container)" />
        <h1 className="text-section-header">Servidor</h1>
      </div>
      
      <nav className="sidebar-nav">
        <NavLink 
          to="/" 
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

      <div className="sidebar-footer">
        <div className={`status-dot ${isConnected ? 'safe' : 'critical'}`}></div>
        <span>Status: {isConnected ? 'Online' : 'Offline'}</span>
      </div>
    </aside>
  );
}
