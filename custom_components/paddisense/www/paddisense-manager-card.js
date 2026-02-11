/**
 * PaddiSense Manager Card v1.5.0
 *
 * A custom Lovelace card for managing PaddiSense installation,
 * modules, updates, and backups.
 *
 * NO SHADOW DOM - uses light DOM like paddisense-registry-card
 */

class PaddiSenseManagerCard extends HTMLElement {
  static get properties() {
    return {
      hass: {},
      config: {},
    };
  }

  static getConfigElement() {
    return document.createElement('paddisense-manager-card-editor');
  }

  static getStubConfig() {
    return {
      entity: 'sensor.paddisense_version',
    };
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error('Please define entity (sensor.paddisense_version)');
    }
    this._config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  getCardSize() {
    return 6;
  }

  _render() {
    if (!this._hass || !this._config.entity) return;

    const entity = this._hass.states[this._config.entity];
    if (!entity) {
      this.innerHTML = `
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

    this.innerHTML = `
      <ha-card>
        <div class="pds-header">
          <h2>PaddiSense Manager</h2>
        </div>

        <div class="pds-content">
          <!-- System Status Section -->
          <div class="pds-section">
            <div class="pds-section-title">System Status</div>
            <div class="pds-status-card">
              <div class="pds-status-row">
                <span class="pds-status-label">Installed Version</span>
                <span class="pds-status-value">${installedVersion}</span>
              </div>
              ${latestVersion ? `
              <div class="pds-status-row">
                <span class="pds-status-label">Latest Version</span>
                <span class="pds-status-value ${updateAvailable ? 'pds-update' : 'pds-current'}">
                  ${latestVersion} ${updateAvailable ? '(Update Available)' : '(Current)'}
                </span>
              </div>
              ` : ''}
              ${lastChecked ? `
              <div class="pds-status-row">
                <span class="pds-status-label">Last Checked</span>
                <span class="pds-status-value">${this._formatDate(lastChecked)}</span>
              </div>
              ` : ''}
              <div class="pds-button-row">
                <button class="pds-btn pds-btn-secondary" data-action="check-updates">
                  Check for Updates
                </button>
                ${updateAvailable ? `
                <button class="pds-btn pds-btn-primary" data-action="update">
                  Update Now
                </button>
                ` : ''}
              </div>
            </div>
          </div>

          <!-- Modules Section -->
          <div class="pds-section">
            <div class="pds-section-title">Modules</div>
            <div class="pds-module-list">
              ${this._renderModules(installedModules, availableModules)}
            </div>
          </div>

          <!-- Tools Section -->
          <div class="pds-section">
            <div class="pds-section-title">Tools</div>
            <div class="pds-tools-grid">
              <button class="pds-btn pds-btn-secondary" data-action="backup">
                Create Backup
              </button>
              <button class="pds-btn pds-btn-secondary" data-action="options">
                Restore Backup
              </button>
              <button class="pds-btn pds-btn-secondary" data-action="export">
                Export Registry
              </button>
            </div>
          </div>

          <!-- Real Time Rice Section -->
          <div class="pds-section">
            <div class="pds-section-title">
              <span class="pds-rtr-icon">🌾</span> Real Time Rice
            </div>
            <div class="pds-status-card">
              <div class="pds-status-row">
                <span class="pds-status-label">Status</span>
                <span class="pds-status-badge ${rtrConfigured ? 'pds-configured' : 'pds-not-configured'}">
                  ${rtrConfigured ? '✓ Configured' : 'Not configured'}
                </span>
              </div>
              ${rtrConfigured ? `
              <div class="pds-status-row">
                <span class="pds-status-label">Paddocks</span>
                <span class="pds-status-value">${rtrPaddockCount}</span>
              </div>
              <div class="pds-status-row">
                <span class="pds-status-label">Last Updated</span>
                <span class="pds-status-value">${rtrLastUpdated ? this._formatDate(rtrLastUpdated) : 'Never'}</span>
              </div>
              ` : ''}
              <div class="pds-input-group">
                <input
                  type="text"
                  id="pds-rtr-url-input"
                  placeholder="Paste Real Time Rice dashboard URL..."
                />
                <button class="pds-btn pds-btn-primary" data-action="configure-rtr">
                  Save
                </button>
              </div>
              ${rtrConfigured ? `
              <div class="pds-button-row">
                <button class="pds-btn pds-btn-secondary" data-action="refresh-rtr">
                  Refresh Data
                </button>
              </div>
              ` : ''}
            </div>
          </div>
        </div>
      </ha-card>

      <style>
        ${this._getStyles()}
      </style>
    `;

    // Attach event listeners
    this._attachEventListeners();
  }

  _renderModules(installed, available) {
    const all = this._getAllModules(installed, available);

    if (all.length === 0) {
      return '<div class="pds-empty-state">No modules found</div>';
    }

    return all.map(m => `
      <div class="pds-module-row ${m.installed ? 'pds-installed' : 'pds-available'}">
        <div class="pds-module-icon">${this._getModuleIcon(m.id)}</div>
        <div class="pds-module-info">
          <div class="pds-module-name">${m.name || m.id}</div>
          <div class="pds-module-version">v${m.version || 'unknown'}</div>
        </div>
        <div class="pds-module-status ${m.installed ? 'pds-installed' : 'pds-available'}">
          ${m.installed ? 'Installed' : 'Available'}
        </div>
        <button class="pds-btn ${m.installed ? 'pds-btn-danger' : 'pds-btn-success'}"
                data-action="${m.installed ? 'remove' : 'install'}"
                data-module-id="${m.id}"
                ${m.blocked ? 'disabled' : ''}>
          ${m.installed ? 'Remove' : (m.blocked ? 'Blocked' : 'Install')}
        </button>
      </div>
    `).join('');
  }

  _getAllModules(installed, available) {
    const all = [];

    for (const m of installed) {
      all.push({ ...m, installed: true, blocked: false });
    }

    for (const m of available) {
      const hasMissingDeps = m.missing_dependencies && m.missing_dependencies.length > 0;
      all.push({ ...m, installed: false, blocked: hasMissingDeps });
    }

    return all;
  }

  _getModuleIcon(moduleId) {
    const icons = {
      'ipm': '📦', 'asm': '🚜', 'weather': '🌤️', 'pwm': '💧',
      'rtr': '🌾', 'str': '🐄', 'wss': '👷', 'hfm': '🌿',
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

  _getStyles() {
    return `
      .pds-header {
        background: #1e1e1e;
        padding: 16px;
        border-radius: 12px 12px 0 0;
      }

      .pds-header h2 {
        margin: 0;
        font-size: 1.3em;
        color: #fff;
      }

      .pds-content {
        padding: 16px;
      }

      .pds-section {
        margin-bottom: 24px;
      }

      .pds-section-title {
        font-size: 0.85em;
        font-weight: 600;
        text-transform: uppercase;
        color: var(--secondary-text-color, #aaa);
        margin-bottom: 12px;
        letter-spacing: 0.5px;
      }

      .pds-status-card {
        background: rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 16px;
      }

      .pds-status-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
      }

      .pds-status-row:last-child {
        margin-bottom: 0;
      }

      .pds-status-label {
        color: var(--secondary-text-color, #aaa);
      }

      .pds-status-value {
        color: var(--primary-text-color, #fff);
        font-weight: 500;
      }

      .pds-current { color: #28a745; }
      .pds-update { color: #ffc107; }

      .pds-button-row {
        display: flex;
        gap: 8px;
        margin-top: 16px;
      }

      .pds-btn {
        flex: 1;
        padding: 12px 16px;
        border: none;
        border-radius: 8px;
        font-size: 0.9em;
        font-weight: 500;
        cursor: pointer;
        transition: opacity 0.2s, transform 0.1s;
        font-family: inherit;
      }

      .pds-btn:hover {
        opacity: 0.9;
      }

      .pds-btn:active {
        opacity: 0.7;
        transform: scale(0.98);
      }

      .pds-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
      }

      .pds-btn-primary {
        background: var(--primary-color, #03a9f4);
        color: white;
      }

      .pds-btn-secondary {
        background: rgba(255,255,255,0.1);
        color: var(--primary-text-color, #fff);
      }

      .pds-btn-success {
        background: #28a745;
        color: white;
      }

      .pds-btn-danger {
        background: #dc3545;
        color: white;
      }

      .pds-btn.loading {
        position: relative;
        color: transparent !important;
        pointer-events: none;
      }

      .pds-btn.loading::after {
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
        animation: pds-spin 0.8s linear infinite;
      }

      @keyframes pds-spin {
        to { transform: rotate(360deg); }
      }

      .pds-module-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
      }

      .pds-module-row {
        display: flex;
        align-items: center;
        gap: 12px;
        background: rgba(255,255,255,0.05);
        border-radius: 8px;
        padding: 12px 16px;
      }

      .pds-module-row.pds-installed {
        border-left: 3px solid #28a745;
      }

      .pds-module-row.pds-available {
        border-left: 3px solid var(--secondary-text-color, #aaa);
      }

      .pds-module-icon {
        font-size: 1.5em;
        width: 40px;
        text-align: center;
      }

      .pds-module-info {
        flex: 1;
      }

      .pds-module-name {
        font-weight: 600;
        color: var(--primary-text-color, #fff);
      }

      .pds-module-version {
        font-size: 0.8em;
        color: var(--secondary-text-color, #aaa);
      }

      .pds-module-status {
        font-size: 0.75em;
        padding: 4px 8px;
        border-radius: 4px;
        text-transform: uppercase;
        font-weight: 600;
      }

      .pds-module-status.pds-installed {
        background: rgba(40, 167, 69, 0.2);
        color: #28a745;
      }

      .pds-module-status.pds-available {
        background: rgba(255,255,255,0.1);
        color: var(--secondary-text-color, #aaa);
      }

      .pds-tools-grid {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }

      .pds-tools-grid .pds-btn {
        flex: none;
        padding: 10px 16px;
      }

      .pds-input-group {
        display: flex;
        gap: 8px;
        margin-top: 12px;
      }

      .pds-input-group input {
        flex: 1;
        padding: 12px;
        border: 1px solid rgba(255,255,255,0.2);
        border-radius: 8px;
        background: rgba(255,255,255,0.05);
        color: var(--primary-text-color, #fff);
        font-size: 0.9em;
      }

      .pds-input-group input::placeholder {
        color: var(--secondary-text-color, #aaa);
      }

      .pds-input-group input:focus {
        outline: none;
        border-color: var(--primary-color, #03a9f4);
      }

      .pds-input-group .pds-btn {
        flex: none;
      }

      .pds-status-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 10px;
        border-radius: 12px;
        font-size: 0.8em;
        font-weight: 500;
      }

      .pds-status-badge.pds-configured {
        background: rgba(40, 167, 69, 0.2);
        color: #28a745;
      }

      .pds-status-badge.pds-not-configured {
        background: rgba(255,255,255,0.1);
        color: var(--secondary-text-color, #aaa);
      }

      .pds-rtr-icon {
        font-size: 1.2em;
      }

      .pds-empty-state {
        text-align: center;
        padding: 24px;
        color: var(--secondary-text-color, #aaa);
      }
    `;
  }

  _attachEventListeners() {
    // Find all buttons with data-action and attach click handlers
    this.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        this._handleAction(btn);
      });
    });
  }

  _handleAction(btn) {
    const action = btn.dataset.action;
    const moduleId = btn.dataset.moduleId;

    console.log('PaddiSense: Action triggered:', action, moduleId || '');

    switch(action) {
      case 'install':
        this._installModule(moduleId, btn);
        break;
      case 'remove':
        this._removeModule(moduleId, btn);
        break;
      case 'check-updates':
        this._checkUpdates(btn);
        break;
      case 'update':
        this._updatePaddisense(btn);
        break;
      case 'backup':
        this._createBackup(btn);
        break;
      case 'options':
        this._openOptions();
        break;
      case 'export':
        this._exportConfig(btn);
        break;
      case 'configure-rtr':
        this._saveRtrUrl(btn);
        break;
      case 'refresh-rtr':
        this._refreshRtrData(btn);
        break;
    }
  }

  _showToast(message, type = 'info') {
    console.log(`PaddiSense [${type}]: ${message}`);

    // Remove existing toast
    const existing = document.querySelector('.pds-toast-global');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'pds-toast-global';
    toast.style.cssText = `
      position: fixed;
      bottom: 20px;
      left: 50%;
      transform: translateX(-50%);
      padding: 12px 24px;
      border-radius: 8px;
      color: white;
      font-weight: 500;
      z-index: 99999;
      font-family: var(--paper-font-body1_-_font-family, sans-serif);
      background: ${type === 'success' ? '#28a745' : type === 'error' ? '#dc3545' : '#03a9f4'};
    `;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  }

  _setLoading(btn, loading) {
    if (!btn) return;
    if (loading) {
      btn.classList.add('loading');
      btn.disabled = true;
    } else {
      btn.classList.remove('loading');
      btn.disabled = false;
    }
  }

  async _callService(domain, service, data = {}, btn = null) {
    if (!this._hass) {
      this._showToast('Home Assistant not available', 'error');
      return { success: false, error: 'hass not available' };
    }

    this._setLoading(btn, true);

    try {
      console.log(`PaddiSense: Calling ${domain}.${service}`, data);
      await this._hass.callService(domain, service, data);
      return { success: true };
    } catch (e) {
      console.error('PaddiSense: Service call failed:', e);
      return { success: false, error: e?.message || String(e) };
    } finally {
      this._setLoading(btn, false);
    }
  }

  async _checkUpdates(btn) {
    this._showToast('Checking for updates...', 'info');
    const result = await this._callService('paddisense', 'check_for_updates', {}, btn);
    if (result.success) {
      this._showToast('Update check complete', 'success');
    } else {
      this._showToast(`Failed: ${result.error}`, 'error');
    }
  }

  async _updatePaddisense(btn) {
    if (!confirm('Update PaddiSense? A backup will be created first. Home Assistant will restart.')) {
      return;
    }
    this._showToast('Starting update... HA will restart', 'info');
    const result = await this._callService('paddisense', 'update_paddisense', { backup_first: true }, btn);
    if (!result.success) {
      this._showToast(`Update failed: ${result.error}`, 'error');
    }
  }

  async _installModule(moduleId, btn) {
    const attrs = this._hass?.states[this._config.entity]?.attributes || {};
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

    this._showToast(`Installing ${moduleName}...`, 'info');
    const result = await this._callService('paddisense', 'install_module', { module_id: moduleId }, btn);
    if (result.success) {
      this._showToast(`${moduleName} installed! Restarting HA...`, 'success');
    } else {
      this._showToast(`Install failed: ${result.error}`, 'error');
    }
  }

  async _removeModule(moduleId, btn) {
    const attrs = this._hass?.states[this._config.entity]?.attributes || {};
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

    this._showToast(`Removing ${moduleName}...`, 'info');

    const data = { module_id: moduleId };
    if (dependents.length > 0) {
      data.force = true;
    }

    const result = await this._callService('paddisense', 'remove_module', data, btn);
    if (result.success) {
      this._showToast(`${moduleName} removed! Restarting HA...`, 'success');
    } else {
      this._showToast(`Remove failed: ${result.error}`, 'error');
    }
  }

  async _createBackup(btn) {
    this._showToast('Creating backup...', 'info');
    const result = await this._callService('paddisense', 'create_backup', {}, btn);
    if (result.success) {
      this._showToast('Backup created successfully', 'success');
    } else {
      this._showToast(`Backup failed: ${result.error}`, 'error');
    }
  }

  async _exportConfig(btn) {
    this._showToast('Exporting registry...', 'info');
    const result = await this._callService('paddisense', 'export_registry', {}, btn);
    if (result.success) {
      this._showToast('Registry exported to backup folder', 'success');
    } else {
      this._showToast(`Export failed: ${result.error}`, 'error');
    }
  }

  _openOptions() {
    const event = new Event('hass-more-info', { bubbles: true, composed: true });
    event.detail = { entityId: this._config.entity };
    this.dispatchEvent(event);
  }

  async _saveRtrUrl(btn) {
    const input = this.querySelector('#pds-rtr-url-input');
    if (!input || !input.value.trim()) {
      this._showToast('Please enter a Real Time Rice dashboard URL', 'error');
      return;
    }
    this._showToast('Saving RTR URL...', 'info');
    const result = await this._callService('paddisense', 'set_rtr_url', { url: input.value.trim() }, btn);
    if (result.success) {
      input.value = '';
      this._showToast('RTR URL saved. Data refreshing...', 'success');
    } else {
      this._showToast(`Failed: ${result.error}`, 'error');
    }
  }

  async _refreshRtrData(btn) {
    this._showToast('Refreshing RTR data...', 'info');
    const result = await this._callService('paddisense', 'refresh_rtr_data', {}, btn);
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

console.info('%c PADDISENSE-MANAGER-CARD %c v1.5.0 ',
  'background:#0066cc;color:white;font-weight:bold;padding:2px 6px;border-radius:3px 0 0 3px;',
  'background:#333;color:white;padding:2px 6px;border-radius:0 3px 3px 0;'
);
