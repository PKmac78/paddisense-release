/**
 * PaddiSense Registry Card
 * Custom Lovelace card for Farm Registry management
 *
 * Mobile-first design following PaddiSense UI Style Guide
 */

class PaddiSenseRegistryCard extends HTMLElement {
  static get properties() {
    return {
      hass: {},
      config: {},
    };
  }

  // Card configuration
  static getConfigElement() {
    return document.createElement("paddisense-registry-card-editor");
  }

  static getStubConfig() {
    return {
      show_farm_overview: true,
      show_paddock_list: true,
      show_season_info: true,
      show_actions: true,
    };
  }

  setConfig(config) {
    this.config = {
      show_farm_overview: true,
      show_paddock_list: true,
      show_season_info: true,
      show_actions: true,
      ...config,
    };
    this._entity = config.entity || "sensor.paddisense_registry";
  }

  set hass(hass) {
    this._hass = hass;
    this._updateCard();
  }

  _updateCard() {
    if (!this._hass) return;

    const state = this._hass.states[this._entity];
    if (!state) {
      this._renderError("Entity not found: " + this._entity);
      return;
    }

    this._state = state;
    this._renderCard();
  }

  _renderError(message) {
    this.innerHTML = `
      <ha-card>
        <div class="card-content" style="color: var(--error-color);">
          ${message}
        </div>
      </ha-card>
    `;
  }

  _renderCard() {
    const attrs = this._state.attributes;
    const grower = attrs.grower || {};
    const hierarchy = attrs.hierarchy || {};
    const activeSeason = attrs.active_season_name;

    this.innerHTML = `
      <ha-card>
        ${this._renderHeader(grower)}
        <div class="card-content">
          ${this.config.show_farm_overview ? this._renderOverview(attrs) : ""}
          ${this.config.show_season_info && activeSeason ? this._renderSeasonBadge(activeSeason) : ""}
          ${this.config.show_paddock_list ? this._renderPaddockList(hierarchy) : ""}
          ${this.config.show_actions ? this._renderActions() : ""}
        </div>
      </ha-card>
      <style>
        ${this._getStyles()}
      </style>
    `;

    this._attachEventListeners();
  }

  _renderHeader(grower) {
    return `
      <div class="ps-header">
        <ha-icon icon="mdi:barn"></ha-icon>
        <span class="ps-header-title">${grower.name || "PaddiSense Farm"}</span>
      </div>
    `;
  }

  _renderOverview(attrs) {
    return `
      <div class="ps-overview">
        <div class="ps-stat">
          <span class="ps-stat-value">${attrs.total_paddocks || 0}</span>
          <span class="ps-stat-label">Paddocks</span>
        </div>
        <div class="ps-stat">
          <span class="ps-stat-value">${attrs.total_bays || 0}</span>
          <span class="ps-stat-label">Bays</span>
        </div>
        <div class="ps-stat">
          <span class="ps-stat-value">${attrs.total_seasons || 0}</span>
          <span class="ps-stat-label">Seasons</span>
        </div>
      </div>
    `;
  }

  _renderSeasonBadge(seasonName) {
    return `
      <div class="ps-season-badge">
        <ha-icon icon="mdi:calendar-range"></ha-icon>
        <span>Active Season: ${seasonName}</span>
      </div>
    `;
  }

  _renderPaddockList(hierarchy) {
    const farms = Object.entries(hierarchy);
    if (farms.length === 0) {
      return `
        <div class="ps-empty">
          <ha-icon icon="mdi:information-outline"></ha-icon>
          <span>No paddocks configured yet</span>
        </div>
      `;
    }

    let html = '<div class="ps-paddock-list">';

    for (const [farmId, farm] of farms) {
      const paddocks = Object.entries(farm.paddocks || {});

      if (paddocks.length === 0) continue;

      for (const [paddockId, paddock] of paddocks) {
        const statusClass = paddock.current_season ? "ps-status-active" : "ps-status-inactive";
        const statusIcon = paddock.current_season ? "mdi:check-circle" : "mdi:minus-circle";

        html += `
          <div class="ps-paddock-row" data-paddock-id="${paddockId}">
            <div class="ps-paddock-info">
              <div class="ps-paddock-name">
                <ha-icon icon="${statusIcon}" class="${statusClass}"></ha-icon>
                ${paddock.name}
              </div>
              <div class="ps-paddock-meta">
                ${paddock.bay_count} bays
              </div>
            </div>
            <div class="ps-paddock-actions">
              <button class="ps-btn ps-btn-icon" data-action="toggle-season" data-id="${paddockId}" title="Toggle Season">
                <ha-icon icon="mdi:swap-horizontal"></ha-icon>
              </button>
              <button class="ps-btn ps-btn-icon ps-btn-danger" data-action="delete" data-id="${paddockId}" title="Delete">
                <ha-icon icon="mdi:delete"></ha-icon>
              </button>
            </div>
          </div>
        `;
      }
    }

    html += "</div>";
    return html;
  }

  _renderActions() {
    return `
      <div class="ps-actions">
        <button class="ps-btn ps-btn-primary" data-action="add-paddock">
          <ha-icon icon="mdi:plus"></ha-icon>
          Add Paddock
        </button>
        <button class="ps-btn ps-btn-secondary" data-action="add-season">
          <ha-icon icon="mdi:calendar-plus"></ha-icon>
          Add Season
        </button>
      </div>
    `;
  }

  _getStyles() {
    return `
      /* Header */
      .ps-header {
        background: #1e1e1e;
        color: white;
        padding: 16px;
        display: flex;
        align-items: center;
        gap: 12px;
        border-radius: 12px 12px 0 0;
      }

      .ps-header ha-icon {
        --mdc-icon-size: 28px;
      }

      .ps-header-title {
        font-size: 18px;
        font-weight: 700;
      }

      /* Card content */
      .card-content {
        padding: 16px;
      }

      /* Overview stats */
      .ps-overview {
        display: flex;
        justify-content: space-around;
        background: #546e7a;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 16px;
      }

      .ps-stat {
        display: flex;
        flex-direction: column;
        align-items: center;
        color: white;
      }

      .ps-stat-value {
        font-size: 32px;
        font-weight: 800;
      }

      .ps-stat-label {
        font-size: 14px;
        font-weight: 600;
        opacity: 0.9;
      }

      /* Season badge */
      .ps-season-badge {
        display: flex;
        align-items: center;
        gap: 8px;
        background: #424242;
        color: white;
        padding: 10px 16px;
        border-radius: 25px;
        margin-bottom: 16px;
        font-size: 14px;
      }

      .ps-season-badge ha-icon {
        --mdc-icon-size: 20px;
      }

      /* Empty state */
      .ps-empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 8px;
        padding: 32px;
        color: var(--secondary-text-color);
      }

      .ps-empty ha-icon {
        --mdc-icon-size: 48px;
        opacity: 0.5;
      }

      /* Paddock list */
      .ps-paddock-list {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-bottom: 16px;
      }

      .ps-paddock-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: var(--card-background-color);
        border: 1px solid var(--divider-color);
        border-radius: 12px;
        padding: 12px 16px;
        min-height: 60px;
      }

      .ps-paddock-info {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }

      .ps-paddock-name {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 16px;
        font-weight: 600;
      }

      .ps-paddock-meta {
        font-size: 14px;
        color: var(--secondary-text-color);
        padding-left: 28px;
      }

      .ps-status-active {
        color: #28a745;
      }

      .ps-status-inactive {
        color: #6c757d;
      }

      .ps-paddock-actions {
        display: flex;
        gap: 8px;
      }

      /* Buttons */
      .ps-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        border: none;
        border-radius: 12px;
        padding: 12px 20px;
        font-size: 16px;
        font-weight: 700;
        cursor: pointer;
        transition: opacity 0.2s;
        min-height: 48px;
      }

      .ps-btn:active {
        opacity: 0.8;
      }

      .ps-btn ha-icon {
        --mdc-icon-size: 24px;
      }

      .ps-btn-icon {
        padding: 10px;
        min-height: 44px;
        min-width: 44px;
        background: var(--secondary-background-color);
        color: var(--primary-text-color);
      }

      .ps-btn-primary {
        background: #0066cc;
        color: white;
        flex: 1;
      }

      .ps-btn-secondary {
        background: #555555;
        color: white;
        flex: 1;
      }

      .ps-btn-danger {
        background: transparent;
        color: #dc3545;
      }

      .ps-btn-danger:hover {
        background: rgba(220, 53, 69, 0.1);
      }

      /* Actions row */
      .ps-actions {
        display: flex;
        gap: 12px;
        margin-top: 8px;
      }

      /* Dialog */
      .ps-dialog-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 999;
      }

      .ps-dialog {
        background: var(--card-background-color);
        border-radius: 16px;
        padding: 24px;
        width: 90%;
        max-width: 400px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
      }

      .ps-dialog-title {
        font-size: 20px;
        font-weight: 700;
        margin-bottom: 16px;
      }

      .ps-dialog-content {
        margin-bottom: 20px;
      }

      .ps-dialog-actions {
        display: flex;
        gap: 12px;
        justify-content: flex-end;
      }

      .ps-input-group {
        margin-bottom: 16px;
      }

      .ps-input-label {
        display: block;
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 6px;
        color: var(--primary-text-color);
      }

      .ps-input {
        width: 100%;
        padding: 12px;
        font-size: 16px;
        border: 1px solid var(--divider-color);
        border-radius: 8px;
        background: var(--card-background-color);
        color: var(--primary-text-color);
        box-sizing: border-box;
      }

      .ps-input:focus {
        outline: none;
        border-color: #0066cc;
      }
    `;
  }

  _attachEventListeners() {
    // Add Paddock button
    const addPaddockBtn = this.querySelector('[data-action="add-paddock"]');
    if (addPaddockBtn) {
      addPaddockBtn.addEventListener("click", () => this._showAddPaddockDialog());
    }

    // Add Season button
    const addSeasonBtn = this.querySelector('[data-action="add-season"]');
    if (addSeasonBtn) {
      addSeasonBtn.addEventListener("click", () => this._showAddSeasonDialog());
    }

    // Toggle season buttons
    const toggleBtns = this.querySelectorAll('[data-action="toggle-season"]');
    toggleBtns.forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const paddockId = btn.dataset.id;
        this._togglePaddockSeason(paddockId);
      });
    });

    // Delete buttons
    const deleteBtns = this.querySelectorAll('[data-action="delete"]');
    deleteBtns.forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const paddockId = btn.dataset.id;
        this._confirmDeletePaddock(paddockId);
      });
    });
  }

  _showAddPaddockDialog() {
    const dialog = document.createElement("div");
    dialog.className = "ps-dialog-overlay";
    dialog.innerHTML = `
      <div class="ps-dialog">
        <div class="ps-dialog-title">Add Paddock</div>
        <div class="ps-dialog-content">
          <div class="ps-input-group">
            <label class="ps-input-label">Paddock Name</label>
            <input type="text" class="ps-input" id="ps-paddock-name" placeholder="e.g., SW6">
          </div>
          <div class="ps-input-group">
            <label class="ps-input-label">Number of Bays</label>
            <input type="number" class="ps-input" id="ps-bay-count" value="5" min="1" max="50">
          </div>
          <div class="ps-input-group">
            <label class="ps-input-label">Bay Prefix</label>
            <input type="text" class="ps-input" id="ps-bay-prefix" value="B-">
          </div>
        </div>
        <div class="ps-dialog-actions">
          <button class="ps-btn ps-btn-secondary" id="ps-dialog-cancel">Cancel</button>
          <button class="ps-btn ps-btn-primary" id="ps-dialog-confirm">Add</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    dialog.querySelector("#ps-dialog-cancel").addEventListener("click", () => {
      dialog.remove();
    });

    dialog.querySelector("#ps-dialog-confirm").addEventListener("click", () => {
      const name = dialog.querySelector("#ps-paddock-name").value.trim();
      const bayCount = parseInt(dialog.querySelector("#ps-bay-count").value, 10);
      const bayPrefix = dialog.querySelector("#ps-bay-prefix").value || "B-";

      if (name && bayCount > 0) {
        this._addPaddock(name, bayCount, bayPrefix);
        dialog.remove();
      }
    });

    dialog.addEventListener("click", (e) => {
      if (e.target === dialog) {
        dialog.remove();
      }
    });

    // Focus the name input
    setTimeout(() => {
      dialog.querySelector("#ps-paddock-name").focus();
    }, 100);
  }

  _showAddSeasonDialog() {
    const currentYear = new Date().getFullYear();
    const defaultName = `CY${(currentYear + 1).toString().slice(-2)}`;
    const defaultStart = `${currentYear}-04-01`;
    const defaultEnd = `${currentYear + 1}-03-31`;

    const dialog = document.createElement("div");
    dialog.className = "ps-dialog-overlay";
    dialog.innerHTML = `
      <div class="ps-dialog">
        <div class="ps-dialog-title">Add Season</div>
        <div class="ps-dialog-content">
          <div class="ps-input-group">
            <label class="ps-input-label">Season Name</label>
            <input type="text" class="ps-input" id="ps-season-name" value="${defaultName}">
          </div>
          <div class="ps-input-group">
            <label class="ps-input-label">Start Date</label>
            <input type="date" class="ps-input" id="ps-season-start" value="${defaultStart}">
          </div>
          <div class="ps-input-group">
            <label class="ps-input-label">End Date</label>
            <input type="date" class="ps-input" id="ps-season-end" value="${defaultEnd}">
          </div>
        </div>
        <div class="ps-dialog-actions">
          <button class="ps-btn ps-btn-secondary" id="ps-dialog-cancel">Cancel</button>
          <button class="ps-btn ps-btn-primary" id="ps-dialog-confirm">Add</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    dialog.querySelector("#ps-dialog-cancel").addEventListener("click", () => {
      dialog.remove();
    });

    dialog.querySelector("#ps-dialog-confirm").addEventListener("click", () => {
      const name = dialog.querySelector("#ps-season-name").value.trim();
      const startDate = dialog.querySelector("#ps-season-start").value;
      const endDate = dialog.querySelector("#ps-season-end").value;

      if (name && startDate && endDate) {
        this._addSeason(name, startDate, endDate);
        dialog.remove();
      }
    });

    dialog.addEventListener("click", (e) => {
      if (e.target === dialog) {
        dialog.remove();
      }
    });
  }

  _confirmDeletePaddock(paddockId) {
    const paddocks = this._state.attributes.paddocks || {};
    const paddock = paddocks[paddockId];
    const paddockName = paddock ? paddock.name : paddockId;

    const dialog = document.createElement("div");
    dialog.className = "ps-dialog-overlay";
    dialog.innerHTML = `
      <div class="ps-dialog">
        <div class="ps-dialog-title">Delete Paddock</div>
        <div class="ps-dialog-content">
          <p>Are you sure you want to delete <strong>${paddockName}</strong>?</p>
          <p style="color: #dc3545;">This will also delete all associated bays.</p>
        </div>
        <div class="ps-dialog-actions">
          <button class="ps-btn ps-btn-secondary" id="ps-dialog-cancel">Cancel</button>
          <button class="ps-btn" style="background: #dc3545; color: white;" id="ps-dialog-confirm">Delete</button>
        </div>
      </div>
    `;

    document.body.appendChild(dialog);

    dialog.querySelector("#ps-dialog-cancel").addEventListener("click", () => {
      dialog.remove();
    });

    dialog.querySelector("#ps-dialog-confirm").addEventListener("click", () => {
      this._deletePaddock(paddockId);
      dialog.remove();
    });

    dialog.addEventListener("click", (e) => {
      if (e.target === dialog) {
        dialog.remove();
      }
    });
  }

  // Service calls
  _addPaddock(name, bayCount, bayPrefix) {
    this._hass.callService("paddisense", "add_paddock", {
      name: name,
      bay_count: bayCount,
      bay_prefix: bayPrefix,
    });
  }

  _addSeason(name, startDate, endDate) {
    this._hass.callService("paddisense", "add_season", {
      name: name,
      start_date: startDate,
      end_date: endDate,
      active: true,
    });
  }

  _togglePaddockSeason(paddockId) {
    this._hass.callService("paddisense", "set_current_season", {
      paddock_id: paddockId,
    });
  }

  _deletePaddock(paddockId) {
    this._hass.callService("paddisense", "delete_paddock", {
      paddock_id: paddockId,
    });
  }

  getCardSize() {
    return 4;
  }
}

// Register the card
customElements.define("paddisense-registry-card", PaddiSenseRegistryCard);

// Register with Lovelace
window.customCards = window.customCards || [];
window.customCards.push({
  type: "paddisense-registry-card",
  name: "PaddiSense Registry Card",
  description: "Farm Registry management card for PaddiSense",
  preview: true,
});

console.info(
  "%c PADDISENSE-REGISTRY-CARD %c v2026.1.0 ",
  "color: white; background: #0066cc; font-weight: bold;",
  "color: #0066cc; background: white; font-weight: bold;"
);
