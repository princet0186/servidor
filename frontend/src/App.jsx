import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import Dashboard from './pages/Dashboard';

const Incidents = () => (
  <div>
    <h2 className="text-page-title">Incidents</h2>
  </div>
);

const SafetyGate = () => (
  <div>
    <h2 className="text-page-title">Safety Gate</h2>
  </div>
);

const Reports = () => (
  <div>
    <h2 className="text-page-title">Reports</h2>
  </div>
);

const Settings = () => (
  <div>
    <h2 className="text-page-title">Settings</h2>
  </div>
);

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-layout">
        <Sidebar />
        <main className="main-content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/incidents" element={<Incidents />} />
            <Route path="/safety" element={<SafetyGate />} />
            <Route path="/reports" element={<Reports />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
