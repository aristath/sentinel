/**
 * Universe Management Modal Component
 * Allows creating and managing bucket/universe configurations
 */
class UniverseManagementModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data x-show="$store.app.showUniverseManagementModal"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex items-center justify-center p-4"
           x-transition>
        <div class="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-2xl modal-content" @click.stop>
          <div class="flex items-center justify-between p-4 border-b border-gray-700">
            <h2 class="text-lg font-semibold text-gray-100">Manage Universes / Buckets</h2>
            <button @click="$store.app.showUniverseManagementModal = false"
                    class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
          </div>

          <div class="p-4 space-y-4">
            <!-- Info Banner -->
            <div class="bg-blue-900/20 border border-blue-700/50 rounded p-3">
              <p class="text-xs text-blue-300">
                ℹ️ Universes (also called "buckets") allow you to organize securities into separate trading groups.
                Each universe operates independently with its own cash balance and trading strategy.
              </p>
            </div>

            <!-- Create New Universe -->
            <div class="border border-gray-700 rounded-lg p-4">
              <h3 class="text-sm font-semibold text-gray-200 mb-3">Create New Universe</h3>
              <div class="flex gap-2">
                <input type="text"
                       x-model="$store.app.newUniverseName"
                       @keyup.enter="$store.app.createUniverse()"
                       placeholder="Enter universe name (e.g., 'Tech Growth', 'Dividend Focus')"
                       class="flex-1 px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                <button @click="$store.app.createUniverse()"
                        :disabled="!$store.app.newUniverseName || $store.app.creatingUniverse"
                        class="px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                  <span x-show="$store.app.creatingUniverse" class="inline-block animate-spin mr-1">&#9696;</span>
                  <span x-text="$store.app.creatingUniverse ? 'Creating...' : 'Create'"></span>
                </button>
              </div>
            </div>

            <!-- Existing Universes -->
            <div class="border border-gray-700 rounded-lg p-4">
              <h3 class="text-sm font-semibold text-gray-200 mb-3">Existing Universes</h3>

              <template x-if="$store.app.loadingBuckets">
                <div class="text-center py-8 text-gray-400">
                  <div class="inline-block animate-spin text-2xl">&#9696;</div>
                  <p class="mt-2 text-sm">Loading universes...</p>
                </div>
              </template>

              <template x-if="!$store.app.loadingBuckets && $store.app.buckets.length === 0">
                <div class="text-center py-8 text-gray-400">
                  <p class="text-sm">No universes found. The "core" universe will be created automatically.</p>
                </div>
              </template>

              <template x-if="!$store.app.loadingBuckets && $store.app.buckets.length > 0">
                <div class="space-y-2">
                  <template x-for="bucket in $store.app.buckets" :key="bucket.id">
                    <div class="flex items-center justify-between p-3 bg-gray-900 rounded border border-gray-700">
                      <div class="flex-1">
                        <div class="flex items-center gap-2">
                          <span class="font-medium text-gray-100" x-text="bucket.name"></span>
                          <template x-if="bucket.type === 'core'">
                            <span class="text-xs px-2 py-0.5 bg-blue-600 text-white rounded">Core</span>
                          </template>
                          <template x-if="bucket.type === 'satellite'">
                            <span class="text-xs px-2 py-0.5 bg-purple-600 text-white rounded">Satellite</span>
                          </template>
                        </div>
                        <div class="text-xs text-gray-400 mt-1">
                          <span>ID: </span><span x-text="bucket.id"></span>
                          <span class="ml-3">Status: </span><span x-text="bucket.status"></span>
                        </div>
                      </div>
                      <div class="flex items-center gap-2">
                        <template x-if="bucket.type !== 'core'">
                          <button @click="$store.app.retireUniverse(bucket.id)"
                                  class="px-3 py-1 text-sm bg-red-600 hover:bg-red-500 text-white rounded transition-colors"
                                  title="Retire this universe">
                            Retire
                          </button>
                        </template>
                      </div>
                    </div>
                  </template>
                </div>
              </template>
            </div>
          </div>

          <div class="flex justify-end gap-2 p-4 border-t border-gray-700">
            <button @click="$store.app.showUniverseManagementModal = false"
                    class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors">
              Close
            </button>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('universe-management-modal', UniverseManagementModal);
