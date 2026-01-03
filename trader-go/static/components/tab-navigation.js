/**
 * Tab Navigation Component
 * Provides tab switching between "Next Actions", "Diversification", "Security Universe", "Recent Trades", and "Logs"
 * Keyboard shortcuts: 1 for Next Actions, 2 for Diversification, 3 for Security Universe, 4 for Recent Trades, 5 for Logs
 */
class TabNavigation extends HTMLElement {
  constructor() {
    super();
    this.handleKeydown = this.handleKeydown.bind(this);
  }

  handleKeydown(e) {
    // Ignore if typing in input fields or if modifier keys are pressed
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
    if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;

    const store = Alpine.store('app');
    if (!store) return;

    if (e.key === '1') {
      e.preventDefault();
      store.activeTab = 'next-actions';
      store.watchActiveTab();
    } else if (e.key === '2') {
      e.preventDefault();
      store.activeTab = 'diversification';
      store.watchActiveTab();
    } else if (e.key === '3') {
      e.preventDefault();
      store.activeTab = 'security-universe';
      store.watchActiveTab();
    } else if (e.key === '4') {
      e.preventDefault();
      store.activeTab = 'recent-trades';
      store.watchActiveTab();
    } else if (e.key === '5') {
      e.preventDefault();
      store.activeTab = 'logs';
      store.watchActiveTab();
    }
  }

  connectedCallback() {
    this.innerHTML = `
      <div class="flex items-center gap-1 border-b border-gray-700"
           x-data
           x-init="$store.app.activeTab = $store.app.activeTab || 'next-actions'">
        <button @click="$store.app.activeTab = 'next-actions'; $store.app.watchActiveTab()"
                class="px-3 md:px-4 py-2 text-sm font-medium transition-colors relative"
                :class="$store.app.activeTab === 'next-actions'
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-300 hover:text-gray-100'"
                aria-label="Next Actions tab">
          <span class="flex items-center gap-2">
            <span class="hidden sm:inline">Next Actions</span>
            <span class="sm:hidden">Actions</span>
            <span x-show="$store.app.recommendations && $store.app.recommendations.steps && $store.app.recommendations.steps.length > 0"
                  x-transition:enter="transition ease-out duration-200"
                  x-transition:enter-start="opacity-0 scale-75"
                  x-transition:enter-end="opacity-100 scale-100"
                  class="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 text-xs font-bold text-white bg-blue-500 rounded-full animate-pulse"
                  x-text="$store.app.recommendations?.steps?.length || 0"
                  aria-label="Pending actions count"></span>
          </span>
        </button>
        <button @click="$store.app.activeTab = 'diversification'; $store.app.watchActiveTab()"
                class="px-3 md:px-4 py-2 text-sm font-medium transition-colors relative"
                :class="$store.app.activeTab === 'diversification'
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-300 hover:text-gray-100'"
                aria-label="Diversification tab">
          <span class="hidden sm:inline">Diversification</span>
          <span class="sm:hidden">Diversify</span>
        </button>
        <button @click="$store.app.activeTab = 'security-universe'; $store.app.watchActiveTab()"
                class="px-3 md:px-4 py-2 text-sm font-medium transition-colors relative"
                :class="$store.app.activeTab === 'security-universe'
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-300 hover:text-gray-100'"
                aria-label="Security Universe tab">
          <span class="hidden sm:inline">Security Universe</span>
          <span class="sm:hidden">Securities</span>
        </button>
        <button @click="$store.app.activeTab = 'recent-trades'; $store.app.watchActiveTab()"
                class="px-3 md:px-4 py-2 text-sm font-medium transition-colors relative"
                :class="$store.app.activeTab === 'recent-trades'
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-300 hover:text-gray-100'"
                aria-label="Recent Trades tab">
          <span class="hidden sm:inline">Recent Trades</span>
          <span class="sm:hidden">Trades</span>
        </button>
        <button @click="$store.app.activeTab = 'logs'; $store.app.watchActiveTab()"
                class="px-3 md:px-4 py-2 text-sm font-medium transition-colors relative"
                :class="$store.app.activeTab === 'logs'
                  ? 'text-blue-400 border-b-2 border-blue-400'
                  : 'text-gray-300 hover:text-gray-100'"
                aria-label="Logs tab">
          <span class="hidden sm:inline">Logs</span>
          <span class="sm:hidden">Logs</span>
        </button>
        <div class="ml-auto text-xs text-gray-300 hidden lg:flex items-center gap-1">
          <span class="text-gray-300">Press</span>
          <kbd class="px-1.5 py-0.5 bg-gray-700 rounded text-gray-300 font-mono">1-5</kbd>
        </div>
      </div>
    `;

    // Add keyboard listener after Alpine initializes
    setTimeout(() => {
      document.addEventListener('keydown', this.handleKeydown);
    }, 0);
  }

  disconnectedCallback() {
    document.removeEventListener('keydown', this.handleKeydown);
  }
}

customElements.define('tab-navigation', TabNavigation);
