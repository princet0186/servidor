import React, { useState } from 'react';

export default function IncidentBriefing({ briefings }) {
  const [activeTab, setActiveTab] = useState('engineer');

  if (!briefings) return null;

  return (
    <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-md)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 className="text-section-header" style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-sm)' }}>
          Incident Briefings
        </h2>
        <span className="text-label-caps" style={{ color: 'var(--primary)' }}>
          MULTI-AUDIENCE
        </span>
      </div>
      
      <div style={{ display: 'flex', borderBottom: '1px solid var(--outline-variant)' }}>
        <button 
          onClick={() => setActiveTab('engineer')}
          style={{ 
            padding: 'var(--spacing-sm) var(--spacing-md)',
            background: 'none', border: 'none', cursor: 'pointer',
            color: activeTab === 'engineer' ? 'var(--primary)' : 'var(--on-surface-variant)',
            borderBottom: activeTab === 'engineer' ? '2px solid var(--primary)' : '2px solid transparent',
            fontWeight: activeTab === 'engineer' ? 600 : 400
          }}>
          Engineer
        </button>
        <button 
          onClick={() => setActiveTab('physician')}
          style={{ 
            padding: 'var(--spacing-sm) var(--spacing-md)',
            background: 'none', border: 'none', cursor: 'pointer',
            color: activeTab === 'physician' ? 'var(--primary)' : 'var(--on-surface-variant)',
            borderBottom: activeTab === 'physician' ? '2px solid var(--primary)' : '2px solid transparent',
            fontWeight: activeTab === 'physician' ? 600 : 400
          }}>
          Physician
        </button>
        <button 
          onClick={() => setActiveTab('administrator')}
          style={{ 
            padding: 'var(--spacing-sm) var(--spacing-md)',
            background: 'none', border: 'none', cursor: 'pointer',
            color: activeTab === 'administrator' ? 'var(--primary)' : 'var(--on-surface-variant)',
            borderBottom: activeTab === 'administrator' ? '2px solid var(--primary)' : '2px solid transparent',
            fontWeight: activeTab === 'administrator' ? 600 : 400
          }}>
          Administrator
        </button>
      </div>

      <div style={{ 
        padding: 'var(--spacing-md)', 
        background: 'var(--surface-container-lowest)', 
        borderRadius: 'var(--radius)',
        fontFamily: 'var(--font-inter)',
        fontSize: '14px',
        lineHeight: '1.5',
        color: 'var(--on-surface)'
      }}>
        {briefings[activeTab]}
      </div>
    </div>
  );
}
