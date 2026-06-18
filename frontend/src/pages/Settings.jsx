import { useState, useEffect } from 'react';
import { Settings as SettingsIcon, Key, Database, Bell, Globe, Save, Eye, EyeOff, CheckCircle, Server, Loader, XCircle } from 'lucide-react';
import { getConfigStatus } from '../api/servidor';
import './Settings.css';

export default function Settings() {
  const [activeTab, setActiveTab] = useState('general');
  const [showApiKey, setShowApiKey] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  const [config, setConfig] = useState({
    geminiModel: 'gemini-2.5-pro',
    geminiConfigured: false,
    apiKey: '••••••••••••••••••••',
    mongoConnected: false,
    mongoUri: '••••••••••••••••••••',
    mongoDb: 'servidor',
    dynatraceConfigured: false,
    dynatraceUrl: '',
    dynatraceToken: '',
    dynatracePollInterval: 30,
    notifySlack: true,
    notifyEmail: true,
    notifyPager: false,
    autoApprove: false,
  });

  useEffect(() => {
    async function load() {
      try {
        const status = await getConfigStatus();
        setConfig(prev => ({
          ...prev,
          geminiModel: status.gemini_model || prev.geminiModel,
          geminiConfigured: status.gemini_configured || false,
          mongoConnected: status.mongodb_connected || false,
          mongoDb: status.mongodb_db || prev.mongoDb,
          dynatraceConfigured: status.dynatrace_configured || false,
          dynatraceUrl: status.dynatrace_url || '',
          dynatracePollInterval: status.dynatrace_poll_interval || 30,
        }));
      } catch (e) {
        console.error('Failed to load config status', e);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleSave = () => {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const updateConfig = (key, value) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  const tabs = [
    { id: 'general', label: 'General', icon: Globe },
    { id: 'integrations', label: 'Integrations', icon: Key },
    { id: 'database', label: 'Database', icon: Database },
    { id: 'notifications', label: 'Notifications', icon: Bell },
  ];

  return (
    <div className="settings-page">
      {/* Header */}
      <div className="settings-header">
        <div className="settings-title-row">
          <SettingsIcon size={22} color="var(--on-surface-variant)" />
          <h2 className="text-page-title">Settings</h2>
          {loading && <Loader size={16} className="spin" color="var(--on-surface-variant)" />}
        </div>
        <p className="settings-subtitle">Configure your Servidor agent, integrations, and notification preferences.</p>
      </div>

      <div className="settings-body">
        {/* Tab Sidebar */}
        <nav className="settings-tabs">
          {tabs.map(tab => (
            <button
              key={tab.id}
              id={`settings-tab-${tab.id}`}
              className={`settings-tab ${activeTab === tab.id ? 'tab-active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              <tab.icon size={16} />
              {tab.label}
            </button>
          ))}
        </nav>

        {/* Tab Content */}
        <div className="settings-content">

          {/* General */}
          {activeTab === 'general' && (
            <div className="settings-section" id="settings-section-general">
              <h3 className="text-section-header">General Configuration</h3>
              <div className="settings-form">
                <div className="form-group">
                  <label className="form-label text-label-caps" htmlFor="gemini-model">Gemini Model</label>
                  <select
                    id="gemini-model"
                    className="input-field settings-select"
                    value={config.geminiModel}
                    onChange={(e) => updateConfig('geminiModel', e.target.value)}
                  >
                    <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
                    <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                    <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
                  </select>
                  <span className="form-hint">The LLM model used for reasoning and remediation planning.</span>
                </div>

                <div className="form-group">
                  <label className="form-label text-label-caps" htmlFor="poll-interval">Dynatrace Poll Interval (seconds)</label>
                  <input
                    id="poll-interval"
                    type="number"
                    className="input-field"
                    value={config.dynatracePollInterval}
                    onChange={(e) => updateConfig('dynatracePollInterval', e.target.value)}
                  />
                  <span className="form-hint">How frequently Servidor polls Dynatrace for new anomalies.</span>
                </div>

                <div className="form-group">
                  <div className="toggle-row">
                    <div className="toggle-info">
                      <span className="form-label text-label-caps">Auto-approve low-risk actions</span>
                      <span className="form-hint">Automatically approve remediation steps classified as LOW risk.</span>
                    </div>
                    <label className="toggle" htmlFor="auto-approve-toggle">
                      <input
                        id="auto-approve-toggle"
                        type="checkbox"
                        checked={config.autoApprove}
                        onChange={(e) => updateConfig('autoApprove', e.target.checked)}
                      />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Integrations */}
          {activeTab === 'integrations' && (
            <div className="settings-section" id="settings-section-integrations">
              <h3 className="text-section-header">API Keys & Integrations</h3>

              <div className="settings-form">
                <div className="form-group">
                  <label className="form-label text-label-caps" htmlFor="api-key-input">Google API Key</label>
                  <div className="input-with-action">
                    <input
                      id="api-key-input"
                      type={showApiKey ? 'text' : 'password'}
                      className="input-field"
                      value={config.apiKey}
                      onChange={(e) => updateConfig('apiKey', e.target.value)}
                    />
                    <button className="input-action-btn" onClick={() => setShowApiKey(!showApiKey)}>
                      {showApiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  <div className="form-status-row">
                    {config.geminiConfigured
                      ? <><CheckCircle size={14} color="var(--status-safe)" /> <span style={{ color: 'var(--status-safe)', fontSize: '12px' }}>Gemini API configured</span></>
                      : <><XCircle size={14} color="var(--status-critical)" /> <span style={{ color: 'var(--status-critical)', fontSize: '12px' }}>Gemini API not configured</span></>
                    }
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label text-label-caps" htmlFor="dynatrace-url-input">Dynatrace Environment URL</label>
                  <input
                    id="dynatrace-url-input"
                    type="text"
                    className="input-field"
                    placeholder="https://abc12345.live.dynatrace.com"
                    value={config.dynatraceUrl}
                    onChange={(e) => updateConfig('dynatraceUrl', e.target.value)}
                  />
                  <div className="form-status-row">
                    {config.dynatraceConfigured
                      ? <><CheckCircle size={14} color="var(--status-safe)" /> <span style={{ color: 'var(--status-safe)', fontSize: '12px' }}>Dynatrace connected</span></>
                      : <><XCircle size={14} color="var(--on-surface-variant)" /> <span style={{ color: 'var(--on-surface-variant)', fontSize: '12px' }}>Not configured (running in mock mode)</span></>
                    }
                  </div>
                </div>

                <div className="form-group">
                  <label className="form-label text-label-caps" htmlFor="dynatrace-token-input">Dynatrace API Token</label>
                  <input
                    id="dynatrace-token-input"
                    type="password"
                    className="input-field"
                    placeholder="dt0c01.XXXXXXXX..."
                    value={config.dynatraceToken}
                    onChange={(e) => updateConfig('dynatraceToken', e.target.value)}
                  />
                  <span className="form-hint">Requires scopes: entities.read, problems.read, events.ingest</span>
                </div>
              </div>
            </div>
          )}

          {/* Database */}
          {activeTab === 'database' && (
            <div className="settings-section" id="settings-section-database">
              <h3 className="text-section-header">Database Configuration</h3>

              <div className="db-status-card card">
                <Server size={18} color={config.mongoConnected ? 'var(--status-safe)' : 'var(--status-warning)'} />
                <div className="db-status-info">
                  <span className="db-status-label">MongoDB Atlas</span>
                  <span className="db-status-value text-data-mono" style={{ color: config.mongoConnected ? 'var(--status-safe)' : 'var(--status-warning)' }}>
                    {config.mongoConnected ? 'Connected' : 'Using JSON fallback'}
                  </span>
                </div>
              </div>

              <div className="settings-form">
                <div className="form-group">
                  <label className="form-label text-label-caps" htmlFor="mongo-uri-input">MongoDB URI</label>
                  <input
                    id="mongo-uri-input"
                    type="password"
                    className="input-field"
                    value={config.mongoUri}
                    onChange={(e) => updateConfig('mongoUri', e.target.value)}
                  />
                  <span className="form-hint">Falls back to local JSON files if unavailable.</span>
                </div>

                <div className="form-group">
                  <label className="form-label text-label-caps" htmlFor="mongo-db-input">Database Name</label>
                  <input
                    id="mongo-db-input"
                    type="text"
                    className="input-field"
                    value={config.mongoDb}
                    onChange={(e) => updateConfig('mongoDb', e.target.value)}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Notifications */}
          {activeTab === 'notifications' && (
            <div className="settings-section" id="settings-section-notifications">
              <h3 className="text-section-header">Notification Channels</h3>
              <div className="settings-form">
                <div className="form-group">
                  <div className="toggle-row">
                    <div className="toggle-info">
                      <span className="toggle-title">Slack Notifications</span>
                      <span className="form-hint">Send incident alerts to configured Slack channels.</span>
                    </div>
                    <label className="toggle" htmlFor="notify-slack">
                      <input id="notify-slack" type="checkbox" checked={config.notifySlack} onChange={(e) => updateConfig('notifySlack', e.target.checked)} />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                </div>
                <div className="form-group">
                  <div className="toggle-row">
                    <div className="toggle-info">
                      <span className="toggle-title">Email Notifications</span>
                      <span className="form-hint">Deliver incident briefings via email to clinical staff.</span>
                    </div>
                    <label className="toggle" htmlFor="notify-email">
                      <input id="notify-email" type="checkbox" checked={config.notifyEmail} onChange={(e) => updateConfig('notifyEmail', e.target.checked)} />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                </div>
                <div className="form-group">
                  <div className="toggle-row">
                    <div className="toggle-info">
                      <span className="toggle-title">PagerDuty Integration</span>
                      <span className="form-hint">Trigger PagerDuty alerts for CRITICAL severity incidents.</span>
                    </div>
                    <label className="toggle" htmlFor="notify-pager">
                      <input id="notify-pager" type="checkbox" checked={config.notifyPager} onChange={(e) => updateConfig('notifyPager', e.target.checked)} />
                      <span className="toggle-slider"></span>
                    </label>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Save Button */}
          <div className="settings-actions">
            <button className={`btn btn-save ${saved ? 'btn-saved' : ''}`} id="settings-save-btn" onClick={handleSave}>
              {saved ? <><CheckCircle size={16} /> Saved</> : <><Save size={16} /> Save Changes</>}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
