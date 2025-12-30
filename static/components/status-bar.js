/**
 * Status Bar Component
 * Displays system status, last sync time, and next rebalance
 */
class StatusBar extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="flex items-center justify-between py-2 px-3 bg-gray-800/50 rounded text-xs text-gray-300" x-data>
        <div class="flex items-center gap-3">
          <span class="flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 rounded-full"
                  :class="$store.app.status.status === 'healthy' ? 'bg-green-500' : 'bg-red-500'"></span>
            <span x-text="$store.app.status.status === 'healthy' ? 'System Online' : 'System Offline'"></span>
          </span>
          <span class="text-gray-400">|</span>
          <span>
            Last sync: <span class="text-gray-300" x-text="$store.app.status.last_sync || 'Never'"></span>
          </span>
        </div>
      </div>
    `;
  }
}

customElements.define('status-bar', StatusBar);
