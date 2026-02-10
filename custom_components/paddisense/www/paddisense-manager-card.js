/**
 * PaddiSense Manager Card
 *
 * A custom Lovelace card for managing PaddiSense installation,
 * modules, updates, and backups.
 */

class PaddiSenseManagerCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = {};
    this._hass = null;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define entity (sensor.paddisense_version)');
    }
    this._config = config;
  }

  getCardSize() {
    return 6;
  }

  static getConfigElement() {
    return document.createElement('paddisense-manager-card-editor');
  }

  static getStubConfig() {
    return {
      entity: 'sensor.paddisense_version',
    };
  }

  _render() {
    if (!this._hass || !this._config.entity) return;

    const entity = this._hass.states[this._config.entity];
    if (!entity) {
      this.shadowRoot.innerHTML = `
        <ha-card header="PaddiSense Manager">
          <div class="card-content">
            <p>Entity not found: ${this._config.entity}</p>
          </div>
        </ha-card>
      `;
      return;
    }

    const attrs = entity.attributes || {};
    const installedVersion = attrs.installed_version || entity.state || 'unknown';
    const latestVersion = attrs.latest_version || null;
    const updateAvailable = attrs.update_available || false;
    const lastChecked = attrs.last_checked || null;
    const installedModules = attrs.installed_modules || [];
    const availableModules = attrs.available_modules || [];

    // RTR sensor data
    const rtrEntity = this._hass.states['sensor.paddisense_rtr'];
    const rtrAttrs = rtrEntity ? (rtrEntity.attributes || {}) : {};
    const rtrConfigured = rtrAttrs.rtr_url_set || false;
    const rtrLastUpdated = rtrAttrs.rtr_last_updated || null;
    const rtrPaddockCount = rtrAttrs.rtr_paddock_count || 0;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          --card-bg: var(--card-background-color, #1c1c1c);
          --primary-color: var(--primary-color, #03a9f4);
          --success-color: #28a745;
          --warning-color: #ffc107;
          --danger-color: #dc3545;
          --text-primary: var(--primary-text-color, #fff);
          --text-secondary: var(--secondary-text-color, #aaa);
        }

        ha-card {
          background: var(--card-bg);
          padding: 16px;
        }

        .header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
        }

        .header h2 {
          margin: 0;
          font-size: 1.5em;
          color: var(--text-primary);
        }

        .section {
          margin-bottom: 24px;
        }

        .section-title {
          font-size: 0.85em;
          font-weight: 600;
          text-transform: uppercase;
          color: var(--text-secondary);
          margin-bottom: 12px;
          letter-spacing: 0.5px;
        }

        .status-card {
          background: rgba(255,255,255,0.05);
          border-radius: 12px;
          padding: 16px;
        }

        .status-row {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: 8px;
        }

        .status-row:last-child {
          margin-bottom: 0;
        }

        .status-label {
          color: var(--text-secondary);
        }

        .status-value {
          color: var(--text-primary);
          font-weight: 500;
        }

        .status-value.current {
          color: var(--success-color);
        }

        .status-value.update {
          color: var(--warning-color);
        }

        .button-row {
          display: flex;
          gap: 8px;
          margin-top: 16px;
        }

        button {
          flex: 1;
          padding: 12px 16px;
          border: none;
          border-radius: 8px;
          font-size: 0.9em;
          font-weight: 500;
          cursor: pointer;
          transition: opacity 0.2s;
        }

        button:hover {
          opacity: 0.9;
        }

        button:active {
          opacity: 0.7;
        }

        button:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        button.loading {
          position: relative;
          color: transparent;
        }

        button.loading::after {
          content: '';
          position: absolute;
          width: 16px;
          height: 16px;
          top: 50%;
          left: 50%;
          margin-left: -8px;
          margin-top: -8px;
          border: 2px solid rgba(255,255,255,0.3);
          border-radius: 50%;
          border-top-color: white;
          animation: spin 0.8s linear infinite;
        }

        @keyframes spin {
          to { transform: rotate(360deg); }
        }

        .toast {
          position: fixed;
          bottom: 20px;
          left: 50%;
          transform: translateX(-50%);
          padding: 12px 24px;
          border-radius: 8px;
          color: white;
          font-weight: 500;
          z-index: 9999;
          animation: slideUp 0.3s ease;
        }

        .toast.success {
          background: var(--success-color);
        }

        .toast.error {
          background: var(--danger-color);
        }

        .toast.info {
          background: var(--primary-color);
        }

        @keyframes slideUp {
          from {
            opacity: 0;
            transform: translateX(-50%) translateY(20px);
          }
          to {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
          }
        }

        button.primary {
          background: var(--primary-color);
          color: white;
        }

        button.secondary {
          background: rgba(255,255,255,0.1);
          color: var(--text-primary);
        }

        button.success {
          background: var(--success-color);
          color: white;
        }

        button.danger {
          background: var(--danger-color);
          color: white;
        }

        .modules-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
          gap: 12px;
        }

        .module-card {
          background: rgba(255,255,255,0.05);
          border-radius: 12px;
          padding: 16px;
          text-align: center;
        }

        .module-card.installed {
          border-left: 3px solid var(--success-color);
        }

        .module-card.required {
          border-left: 3px solid var(--primary-color);
        }

        .module-deps-info {
          font-size: 0.75em;
          color: var(--primary-color);
          margin: 4px 0;
          padding: 4px 8px;
          background: rgba(3, 169, 244, 0.1);
          border-radius: 4px;
        }

        .module-card.available {
          border-left: 3px solid var(--text-secondary);
        }

        .module-card.blocked {
          opacity: 0.7;
          border-left: 3px solid var(--warning-color);
        }

        .module-deps-warning {
          font-size: 0.75em;
          color: var(--warning-color);
          margin: 4px 0;
          padding: 4px 8px;
          background: rgba(255, 193, 7, 0.1);
          border-radius: 4px;
        }

        .module-icon {
          font-size: 2em;
          margin-bottom: 8px;
        }

        .module-name {
          font-weight: 600;
          color: var(--text-primary);
          margin-bottom: 4px;
        }

        .module-version {
          font-size: 0.85em;
          color: var(--text-secondary);
          margin-bottom: 8px;
        }

        .module-status {
          font-size: 0.8em;
          padding: 4px 8px;
          border-radius: 12px;
          display: inline-block;
        }

        .module-status.current {
          background: rgba(40, 167, 69, 0.2);
          color: var(--success-color);
        }

        .module-status.update {
          background: rgba(255, 193, 7, 0.2);
          color: var(--warning-color);
        }

        .module-actions {
          margin-top: 12px;
        }

        .module-actions button {
          padding: 8px 12px;
          font-size: 0.8em;
        }

        .empty-state {
          text-align: center;
          padding: 24px;
          color: var(--text-secondary);
        }

        .tools-grid {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
        }

        .tools-grid button {
          flex: none;
          padding: 10px 16px;
        }

        .input-group {
          display: flex;
          gap: 8px;
          margin-bottom: 12px;
        }

        .input-group input {
          flex: 1;
          padding: 12px;
          border: 1px solid rgba(255,255,255,0.2);
          border-radius: 8px;
          background: rgba(255,255,255,0.05);
          color: var(--text-primary);
          font-size: 0.9em;
        }

        .input-group input::placeholder {
          color: var(--text-secondary);
        }

        .input-group input:focus {
          outline: none;
          border-color: var(--primary-color);
        }

        .input-group button {
          flex: none;
        }

        .status-badge {
          display: inline-flex;
          align-items: center;
          gap: 6px;
          padding: 4px 10px;
          border-radius: 12px;
          font-size: 0.8em;
          font-weight: 500;
        }

        .status-badge.configured {
          background: rgba(40, 167, 69, 0.2);
          color: var(--success-color);
        }

        .status-badge.not-configured {
          background: rgba(255,255,255,0.1);
          color: var(--text-secondary);
        }

        .rtr-icon {
          font-size: 1.2em;
        }
      </style>

      <ha-card>
        <div class="header">
          <h2>PaddiSense Manager</h2>
        </div>

        <!-- System Status Section -->
        <div class="section">
          <div class="section-title">System Status</div>
          <div class="status-card">
            <div class="status-row">
              <span class="status-label">Installed Version</span>
              <span class="status-value">${installedVersion}</span>
            </div>
            ${latestVersion ? `
            <div class="status-row">
              <span class="status-label">Latest Version</span>
              <span class="status-value ${updateAvailable ? 'update' : 'current'}">
                ${latestVersion} ${updateAvailable ? '(Update Available)' : '(Current)'}
              </span>
            </div>
            ` : ''}
            ${lastChecked ? `
            <div class="status-row">
              <span class="status-label">Last Checked</span>
              <span class="status-value">${this._formatDate(lastChecked)}</span>
            </div>
            ` : ''}
            <div class="button-row">
              <button class="secondary" onclick="this.getRootNode().host._checkUpdates(event)">
                Check for Updates
              </button>
              ${updateAvailable ? `
              <button class="primary" onclick="this.getRootNode().host._updatePaddisense(event)">
                Update Now
              </button>
              ` : ''}
            </div>
          </div>
        </div>

        <!-- Installed Modules Section -->
        <div class="section">
          <div class="section-title">Installed Modules</div>
          ${installedModules.length > 0 ? `
          <div class="modules-grid">
            ${installedModules.map(m => {
              const hasDependents = m.dependents && m.dependents.length > 0;
              return `
              <div class="module-card installed ${hasDependents ? 'required' : ''}">
                <div class="module-icon">${this._getModuleIcon(m.id)}</div>
                <div class="module-name">${m.name || m.id}</div>
                <div class="module-version">v${m.version || 'unknown'}</div>
                <div class="module-status current">Installed</div>
                ${hasDependents ? `
                  <div class="module-deps-info">Required by: ${m.dependents.join(', ')}</div>
                ` : ''}
                <div class="module-actions">
                  <button class="danger" onclick="this.getRootNode().host._removeModule('${m.id}', event)">
                    Remove
                  </button>
                </div>
              </div>
            `}).join('')}
          </div>
          ` : `
          <div class="empty-state">No modules installed</div>
          `}
        </div>

        <!-- Available Modules Section -->
        ${availableModules.length > 0 ? `
        <div class="section">
          <div class="section-title">Available Modules</div>
          <div class="modules-grid">
            ${availableModules.map(m => {
              const hasMissingDeps = m.missing_dependencies && m.missing_dependencies.length > 0;
              return `
              <div class="module-card available ${hasMissingDeps ? 'blocked' : ''}">
                <div class="module-icon">${this._getModuleIcon(m.id)}</div>
                <div class="module-name">${m.name || m.id}</div>
                <div class="module-version">v${m.version || 'unknown'}</div>
                ${hasMissingDeps ? `
                  <div class="module-deps-warning">Requires: ${m.missing_dependencies.join(', ')}</div>
                ` : ''}
                <div class="module-actions">
                  <button class="${hasMissingDeps ? 'secondary' : 'success'}"
                          onclick="this.getRootNode().host._installModule('${m.id}', event)"
                          ${hasMissingDeps ? 'disabled title="Install required modules first"' : ''}>
                    ${hasMissingDeps ? 'Blocked' : 'Install'}
                  </button>
                </div>
              </div>
            `}).join('')}
          </div>
        </div>
        ` : ''}

        <!-- Tools Section -->
        <div class="section">
          <div class="section-title">Tools</div>
          <div class="tools-grid">
            <button class="secondary" onclick="this.getRootNode().host._createBackup(event)">
              Create Backup
            </button>
            <button class="secondary" onclick="this.getRootNode().host._openOptions()">
              Restore Backup
            </button>
            <button class="secondary" onclick="this.getRootNode().host._exportConfig(event)">
              Export Registry
            </button>
          </div>
        </div>

        <!-- Real Time Rice Section -->
        <div class="section">
          <div class="section-title">
            <span class="rtr-icon">🌾</span> Real Time Rice
          </div>
          <div class="status-card">
            <div class="status-row">
              <span class="status-label">Status</span>
              <span class="status-badge ${rtrConfigured ? 'configured' : 'not-configured'}">
                ${rtrConfigured ? '✓ Configured' : 'Not configured'}
              </span>
            </div>
            ${rtrConfigured ? `
            <div class="status-row">
              <span class="status-label">Paddocks</span>
              <span class="status-value">${rtrPaddockCount}</span>
            </div>
            <div class="status-row">
              <span class="status-label">Last Updated</span>
              <span class="status-value">${rtrLastUpdated ? this._formatDate(rtrLastUpdated) : 'Never'}</span>
            </div>
            ` : ''}
            <div class="input-group" style="margin-top: 12px;">
              <input
                type="text"
                id="rtr-url-input"
                placeholder="Paste Real Time Rice dashboard URL..."
                value=""
              />
              <button class="primary" onclick="this.getRootNode().host._saveRtrUrl(event)">
                Save
              </button>
            </div>
            ${rtrConfigured ? `
            <div class="button-row">
              <button class="secondary" onclick="this.getRootNode().host._refreshRtrData(event)">
                Refresh Data
              </button>
            </div>
            ` : ''}
          </div>
        </div>
      </ha-card>
    `;
  }

  _getModuleIcon(moduleId) {
    const icons = {
      'ipm': '📦',
      'asm': '🚜',
      'weather': '🌤️',
      'pwm': '💧',
      'rtr': '🌾',
      'str': '🐄',
      'wss': '👷',
      'hfm': '🎤',
    };
    return icons[moduleId] || '📦';
  }

  _formatDate(isoString) {
    if (!isoString) return 'Never';
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minutes ago`;
    if (diffHours < 24) return `${diffHours} hours ago`;
    return date.toLocaleDateString();
  }

  _showToast(message, type = 'info') {
    // Remove any existing toast
    const existing = this.shadowRoot.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    this.shadowRoot.appendChild(toast);

    setTimeout(() => toast.remove(), 4000);
  }

  _setButtonLoading(button, loading) {
    if (loading) {
      button.classList.add('loading');
      button.disabled = true;
    } else {
      button.classList.remove('loading');
      button.disabled = false;
    }
  }

  async _callService(domain, service, data = {}, button = null) {
    if (button) this._setButtonLoading(button, true);

    try {
      await this._hass.callService(domain, service, data);
      return { success: true };
    } catch (e) {
      console.error(`Failed to call ${domain}.${service}:`, e);
      return { success: false, error: e.message || 'Unknown error' };
    } finally {
      if (button) this._setButtonLoading(button, false);
    }
  }

  async _checkUpdates(event) {
    const button = event?.target;
    this._showToast('Checking for updates...', 'info');
    const result = await this._callService('paddisense', 'check_for_updates', {}, button);
    if (result.success) {
      this._showToast('Update check complete', 'success');
    } else {
      this._showToast(`Failed: ${result.error}`, 'error');
    }
  }

  async _updatePaddisense(event) {
    if (!confirm('Update PaddiSense? A backup will be created first. Home Assistant will restart.')) {
      return;
    }
    const button = event?.target;
    this._showToast('Starting update... HA will restart', 'info');
    const result = await this._callService('paddisense', 'update_paddisense', { backup_first: true }, button);
    if (!result.success) {
      this._showToast(`Update failed: ${result.error}`, 'error');
    }
  }

  async _installModule(moduleId, event) {
    // Get module info for better messaging
    const attrs = this._hass.states[this._config.entity]?.attributes || {};
    const availableModules = attrs.available_modules || [];
    const moduleInfo = availableModules.find(m => m.id === moduleId);
    const moduleName = moduleInfo?.name || moduleId;
    const deps = moduleInfo?.dependencies || [];

    let confirmMsg = `Install ${moduleName}?`;
    if (deps.length > 0) {
      confirmMsg += `\n\nRequires: ${deps.join(', ')}`;
    }
    confirmMsg += '\n\nHome Assistant will restart.';

    if (!confirm(confirmMsg)) {
      return;
    }
    const button = event?.target;
    this._showToast(`Installing ${moduleName}...`, 'info');
    const result = await this._callService('paddisense', 'install_module', { module_id: moduleId }, button);
    if (result.success) {
      this._showToast(`${moduleName} installed! Restarting HA...`, 'success');
    } else {
      this._showToast(`Install failed: ${result.error}`, 'error');
    }
  }

  async _removeModule(moduleId, event) {
    // Get module info for better messaging
    const attrs = this._hass.states[this._config.entity]?.attributes || {};
    const installedModules = attrs.installed_modules || [];
    const moduleInfo = installedModules.find(m => m.id === moduleId);
    const moduleName = moduleInfo?.name || moduleId;
    const dependents = moduleInfo?.dependents || [];

    let confirmMsg = `Remove ${moduleName}?`;
    if (dependents.length > 0) {
      confirmMsg += `\n\n⚠️ Warning: Required by ${dependents.join(', ')}`;
    }
    confirmMsg += '\n\nYour data will be preserved. Home Assistant will restart.';

    if (!confirm(confirmMsg)) {
      return;
    }
    const button = event?.target;
    this._showToast(`Removing ${moduleName}...`, 'info');

    // If there are dependents, use force removal
    const data = { module_id: moduleId };
    if (dependents.length > 0) {
      data.force = true;
    }

    const result = await this._callService('paddisense', 'remove_module', data, button);
    if (result.success) {
      this._showToast(`${moduleName} removed! Restarting HA...`, 'success');
    } else {
      this._showToast(`Remove failed: ${result.error}`, 'error');
    }
  }

  async _createBackup(event) {
    const button = event?.target;
    this._showToast('Creating backup...', 'info');
    const result = await this._callService('paddisense', 'create_backup', {}, button);
    if (result.success) {
      this._showToast('Backup created successfully', 'success');
    } else {
      this._showToast(`Backup failed: ${result.error}`, 'error');
    }
  }

  async _exportConfig(event) {
    const button = event?.target;
    this._showToast('Exporting registry...', 'info');
    const result = await this._callService('paddisense', 'export_registry', {}, button);
    if (result.success) {
      this._showToast('Registry exported to backup folder', 'success');
    } else {
      this._showToast(`Export failed: ${result.error}`, 'error');
    }
  }

  _openOptions() {
    // Navigate to integration options
    const event = new Event('hass-more-info', { bubbles: true, composed: true });
    event.detail = { entityId: this._config.entity };
    this.dispatchEvent(event);
  }

  async _saveRtrUrl(event) {
    const input = this.shadowRoot.getElementById('rtr-url-input');
    if (!input || !input.value.trim()) {
      this._showToast('Please enter a Real Time Rice dashboard URL', 'error');
      return;
    }
    const button = event?.target;
    this._showToast('Saving RTR URL...', 'info');
    const result = await this._callService('paddisense', 'set_rtr_url', { url: input.value.trim() }, button);
    if (result.success) {
      input.value = '';
      this._showToast('RTR URL saved. Data refreshing...', 'success');
    } else {
      this._showToast(`Failed: ${result.error}`, 'error');
    }
  }

  async _refreshRtrData(event) {
    const button = event?.target;
    this._showToast('Refreshing RTR data...', 'info');
    const result = await this._callService('paddisense', 'refresh_rtr_data', {}, button);
    if (result.success) {
      this._showToast('RTR data refreshed', 'success');
    } else {
      this._showToast(`Refresh failed: ${result.error}`, 'error');
    }
  }
}

// Register the card
customElements.define('paddisense-manager-card', PaddiSenseManagerCard);

// Register with HACS card picker
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'paddisense-manager-card',
  name: 'PaddiSense Manager',
  description: 'Manage PaddiSense installation, modules, and updates',
  preview: true,
});

console.info('%c PADDISENSE-MANAGER-CARD %c v1.3.0 ',
  'background:#0066cc;color:white;font-weight:bold;padding:2px 6px;border-radius:3px 0 0 3px;',
  'background:#333;color:white;padding:2px 6px;border-radius:0 3px 3px 0;'
);
