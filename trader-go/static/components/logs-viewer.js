/**
 * Logs Viewer Component
 * Displays logs from multiple log files with filtering and search capabilities
 */
class LogsViewer extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div class="space-y-4" x-data="{ autoScroll: true }" x-init="
        // Load available log files on mount
        $store.app.fetchAvailableLogFiles();
        // Ensure auto-refresh is set up
        $store.app.watchActiveTab();
      ">
        <!-- Controls -->
        <div class="bg-gray-800 border border-gray-700 rounded p-4">
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
            <!-- Log File Selector -->
            <div>
              <label class="block text-xs text-gray-300 mb-1">Log File</label>
              <select @change="$store.app.logs.selectedLogFile = $event.target.value; $store.app.fetchLogs()"
                      :value="$store.app.logs.selectedLogFile"
                      class="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                <template x-for="logFile in $store.app.logs.availableLogFiles" :key="logFile.name">
                  <option :value="logFile.name" x-text="logFile.name"></option>
                </template>
                <template x-if="$store.app.logs.availableLogFiles.length === 0">
                  <option>Loading...</option>
                </template>
              </select>
            </div>

            <!-- Level Filter -->
            <div>
              <label class="block text-xs text-gray-300 mb-1">Level</label>
              <select @change="$store.app.logs.filterLevel = $event.target.value === 'all' ? null : $event.target.value; $store.app.fetchLogs()"
                      :value="$store.app.logs.filterLevel || 'all'"
                      class="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                <option value="all">All</option>
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>

            <!-- Search -->
            <div>
              <label class="block text-xs text-gray-300 mb-1">Search</label>
              <input type="text"
                     @input.debounce.300ms="$store.app.logs.searchQuery = $event.target.value; $store.app.fetchLogs()"
                     :value="$store.app.logs.searchQuery"
                     placeholder="Search logs..."
                     class="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500">
            </div>

            <!-- Line Count -->
            <div>
              <label class="block text-xs text-gray-300 mb-1">Lines</label>
              <input type="number"
                     min="50"
                     max="1000"
                     step="50"
                     @change="$store.app.logs.lineCount = Math.max(50, Math.min(1000, parseInt($event.target.value) || 100)); $store.app.fetchLogs()"
                     :value="$store.app.logs.lineCount"
                     class="w-full bg-gray-700 border border-gray-600 rounded px-2 py-1.5 text-sm text-gray-200 focus:outline-none focus:border-blue-500">
            </div>

            <!-- Toggles -->
            <div class="flex flex-col gap-2">
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox"
                       :checked="$store.app.logs.showErrorsOnly"
                       @change="$store.app.logs.showErrorsOnly = $event.target.checked; $store.app.fetchLogs()"
                       class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                <span class="text-xs text-gray-300">Errors Only</span>
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox"
                       :checked="$store.app.logs.autoRefresh"
                       @change="$store.app.logs.autoRefresh = $event.target.checked; if ($event.target.checked) { $store.app.startLogsAutoRefresh(); } else { $store.app.stopLogsAutoRefresh(); }"
                       class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                <span class="text-xs text-gray-300">Auto-refresh</span>
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox"
                       x-model="autoScroll"
                       class="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500 focus:ring-offset-gray-800">
                <span class="text-xs text-gray-300">Auto-scroll</span>
              </label>
            </div>
          </div>

          <!-- Action Buttons -->
          <div class="mt-4 flex items-center gap-2">
            <button @click="$store.app.fetchLogs()"
                    :disabled="$store.app.logs.loading"
                    class="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed text-white text-xs rounded transition-colors">
              <span x-show="$store.app.logs.loading" class="inline-block animate-spin mr-1">&#9696;</span>
              <span x-text="$store.app.logs.loading ? 'Loading...' : 'Refresh'"></span>
            </button>
            <span class="text-xs text-gray-300">
              <span x-show="$store.app.logs.lastRefresh">
                Last refresh: <span x-text="new Date($store.app.logs.lastRefresh).toLocaleTimeString()"></span>
              </span>
            </span>
          </div>
        </div>

        <!-- Status Bar -->
        <div class="bg-gray-800 border border-gray-700 rounded px-4 py-2 flex items-center justify-between text-xs text-gray-300">
          <div class="flex items-center gap-4">
            <span>Total lines: <span class="text-gray-200" x-text="$store.app.logs.totalLines || 0"></span></span>
            <span>Displayed: <span class="text-gray-200" x-text="$store.app.logs.returnedLines || 0"></span></span>
            <span x-show="$store.app.logs.logPath" class="text-gray-300">
              Path: <span class="text-gray-200 font-mono text-xs" x-text="$store.app.logs.logPath"></span>
            </span>
          </div>
        </div>

        <!-- Log Display -->
        <div class="bg-gray-900 border border-gray-700 rounded p-4">
          <div class="bg-black rounded p-4 overflow-auto max-h-[600px] font-mono text-xs"
               x-ref="logContainer"
               x-effect="
                 if (autoScroll && $store.app.logs.entries.length > 0) {
                   setTimeout(() => {
                     $refs.logContainer.scrollTop = $refs.logContainer.scrollHeight;
                   }, 100);
                 }
               ">
            <template x-if="$store.app.logs.entries.length === 0 && !$store.app.logs.loading">
              <div class="text-gray-300 text-center py-8">No log entries found</div>
            </template>
            <template x-if="$store.app.logs.loading && $store.app.logs.entries.length === 0">
              <div class="text-gray-300 text-center py-8">Loading logs...</div>
            </template>
            <template x-for="(line, index) in $store.app.logs.entries" :key="index">
              <div class="whitespace-pre-wrap break-words mb-1"
                   :class="{
                     'text-red-400': line.includes(' - ERROR - ') || line.includes(' - CRITICAL - '),
                     'text-yellow-400': line.includes(' - WARNING - '),
                     'text-blue-400': line.includes(' - INFO - '),
                     'text-gray-400': line.includes(' - DEBUG - '),
                     'text-gray-300': !line.includes(' - ERROR - ') && !line.includes(' - WARNING - ') && !line.includes(' - INFO - ') && !line.includes(' - DEBUG - ') && !line.includes(' - CRITICAL - ')
                   }"
                   x-text="line">
              </div>
            </template>
          </div>
        </div>
      </div>
    `;

    // Ensure Alpine processes the component
    if (window.Alpine) {
      window.Alpine.initTree(this);
    } else {
      document.addEventListener('alpine:init', () => {
        if (window.Alpine) {
          window.Alpine.initTree(this);
        }
      });
    }
  }
}

customElements.define('logs-viewer', LogsViewer);
