import React, { useState } from 'react';

export default function IncidentBriefing({ briefings }) {
  const [activeTab, setActiveTab] = useState('engineer');

  if (!briefings) return null;

  return (
    <div className="card briefing-card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
      <div className="briefing-header">
        <h2 className="text-section-header" style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
          Incident Briefings
        </h2>
        <span className="text-label-caps" style={{ color: 'var(--primary)' }}>
          MULTI-AUDIENCE
        </span>
      </div>
      
      <div className="briefing-tabs">
        <button 
          onClick={() => setActiveTab('engineer')}
          className={`briefing-tab ${activeTab === 'engineer' ? 'active' : ''}`}
        >
          Engineer
        </button>
        <button 
          onClick={() => setActiveTab('physician')}
          className={`briefing-tab ${activeTab === 'physician' ? 'active' : ''}`}
        >
          Physician
        </button>
        <button 
          onClick={() => setActiveTab('administrator')}
          className={`briefing-tab ${activeTab === 'administrator' ? 'active' : ''}`}
        >
          Administrator
        </button>
      </div>

      <div className="briefing-body" key={activeTab}>
        {briefings[activeTab]}
      </div>
    </div>
  );
}
