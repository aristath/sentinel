/**
 * Alpine.js component for job footer
 * Make it globally available so Alpine can find it
 */
window.jobFooterComponent = function() {
  return {
    loading: {},
    messages: {},
    jobs: [
      { id: 'sync-cycle', name: 'Sync Cycle', api: 'triggerSyncCycle' },
      { id: 'daily-pipeline', name: 'Daily Pipeline', api: 'triggerDailyPipeline' },
      { id: 'daily-maintenance', name: 'Daily Maintenance', api: 'triggerDailyMaintenance' },
      { id: 'weekly-maintenance', name: 'Weekly Maintenance', api: 'triggerWeeklyMaintenance' },
      { id: 'dividend-reinvestment', name: 'Dividend Reinvestment', api: 'triggerDividendReinvestment' }
    ],
    async triggerJob(job) {
      if (this.loading[job.id]) return;

      this.loading[job.id] = true;
      this.messages[job.id] = null;

      try {
        const result = await window.API[job.api]();
        this.messages[job.id] = {
          type: result.status === 'success' ? 'success' : 'error',
          text: result.message || result.status
        };

        // Clear message after 5 seconds
        setTimeout(() => {
          this.messages[job.id] = null;
        }, 5000);
      } catch (error) {
        this.messages[job.id] = {
          type: 'error',
          text: error.message || 'Failed to trigger job'
        };

        // Clear message after 5 seconds
        setTimeout(() => {
          this.messages[job.id] = null;
        }, 5000);
      } finally {
        this.loading[job.id] = false;
      }
    }
  };
};

/**
 * Job Footer Component
 * Displays buttons to manually trigger all scheduled jobs
 */
class JobFooter extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <footer class="mt-8 pt-4 border-t border-gray-800" x-data="jobFooterComponent()">
        <div class="mb-2">
          <h3 class="text-xs text-gray-300 uppercase tracking-wide mb-3">Manual Job Triggers</h3>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7 gap-2">
          <template x-for="job in jobs" :key="job.id">
            <div class="flex flex-col">
              <button @click="triggerJob(job)"
                      class="px-3 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 text-xs rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                      :disabled="!!loading[job.id]">
                <div class="flex items-center justify-center gap-1.5">
                  <span x-show="loading[job.id]" class="inline-block animate-spin text-blue-400">&#9696;</span>
                  <span x-text="job.name"></span>
                </div>
              </button>

              <div x-show="messages[job.id]"
                   x-text="messages[job.id]?.text"
                   class="mt-1 px-2 py-1 rounded text-xs"
                   :class="messages[job.id]?.type === 'success' ? 'bg-green-900/50 text-green-400' : 'bg-red-900/50 text-red-400'">
              </div>
            </div>
          </template>
        </div>
      </footer>
    `;

    // Ensure Alpine processes the component after it's added to DOM
    if (window.Alpine) {
      window.Alpine.initTree(this);
    } else {
      // Wait for Alpine to be ready
      document.addEventListener('alpine:init', () => {
        if (window.Alpine) {
          window.Alpine.initTree(this);
        }
      });
    }
  }
}

customElements.define('job-footer', JobFooter);
