/**
 * Planner Management Modal Component
 * CRUD interface for planner configurations with TOML editor
 */
class PlannerManagementModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data x-show="$store.app.showPlannerManagementModal"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex items-center justify-center p-4"
           x-transition>
        <div class="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-4xl modal-content max-h-[90vh] flex flex-col" @click.stop>
          <!-- Header -->
          <div class="flex items-center justify-between p-4 border-b border-gray-700">
            <h2 class="text-lg font-semibold text-gray-100">Planner Configuration</h2>
            <button @click="$store.app.closePlannerManagement()"
                    class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
          </div>

          <!-- Body -->
          <div class="p-4 space-y-4 overflow-y-auto flex-1">
            <!-- Planner Selector Section -->
            <div class="flex gap-3 items-end">
              <div class="flex-1">
                <label class="block text-sm text-gray-300 mb-1">Select Planner</label>
                <select x-model="$store.app.selectedPlannerId"
                        @change="$store.app.loadSelectedPlanner()"
                        class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                  <option value="">-- Select a planner --</option>
                  <template x-for="planner in $store.app.planners" :key="planner.id">
                    <option :value="planner.id" x-text="planner.name"></option>
                  </template>
                </select>
              </div>
              <button @click="$store.app.startCreatePlanner()"
                      class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded transition-colors whitespace-nowrap">
                + Add New
              </button>
            </div>

            <!-- Loading State -->
            <div x-show="$store.app.plannerLoading" class="text-center py-8">
              <span class="inline-block animate-spin text-2xl">&#9696;</span>
              <p class="text-sm text-gray-400 mt-2">Loading...</p>
            </div>

            <!-- Planner Form (shown when planner selected or creating new) -->
            <div x-show="$store.app.plannerFormMode !== 'none' && !$store.app.plannerLoading"
                 class="space-y-4" x-transition>

              <!-- Name Field -->
              <div>
                <label class="block text-sm text-gray-300 mb-1">Planner Name *</label>
                <input type="text"
                       x-model="$store.app.plannerForm.name"
                       placeholder="e.g., Aggressive Growth Strategy"
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
              </div>

              <!-- Bucket Assignment Dropdown -->
              <div>
                <label class="block text-sm text-gray-300 mb-1">Assign to Bucket (Optional)</label>
                <select x-model="$store.app.plannerForm.bucket_id"
                        class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                  <option value="">None (Template)</option>
                  <template x-for="bucket in $store.app.plannerBuckets" :key="bucket.id">
                    <option :value="bucket.id" x-text="bucket.name + ' (' + bucket.type + ')'"></option>
                  </template>
                </select>
                <p class="text-xs text-gray-500 mt-1">
                  <span x-show="$store.app.plannerForm.bucket_id">This planner will be used for the selected bucket</span>
                  <span x-show="!$store.app.plannerForm.bucket_id">No bucket assigned - this is a template configuration</span>
                </p>
              </div>

              <!-- TOML Configuration Textarea -->
              <div>
                <div class="flex items-center justify-between mb-1">
                  <label class="block text-sm text-gray-300">TOML Configuration *</label>
                  <div class="flex gap-2">
                    <!-- Template Loader (create mode only) -->
                    <div x-show="$store.app.plannerFormMode === 'create'" class="relative" x-data="{ showTemplates: false }">
                      <button @click="showTemplates = !showTemplates"
                              class="text-xs text-green-400 hover:text-green-300 transition-colors">
                        📋 Load Template
                      </button>
                      <div x-show="showTemplates" @click.away="showTemplates = false"
                           class="absolute right-0 mt-1 bg-gray-800 border border-gray-700 rounded shadow-lg py-1 z-10 min-w-[180px]">
                        <button @click="$store.app.loadPlannerTemplate('conservative'); showTemplates = false"
                                class="block w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-700">
                          Conservative Strategy
                        </button>
                        <button @click="$store.app.loadPlannerTemplate('balanced'); showTemplates = false"
                                class="block w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-700">
                          Balanced Growth
                        </button>
                        <button @click="$store.app.loadPlannerTemplate('aggressive'); showTemplates = false"
                                class="block w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-700">
                          Aggressive Growth
                        </button>
                      </div>
                    </div>
                    <!-- History Viewer (edit mode only) -->
                    <button x-show="$store.app.plannerFormMode === 'edit'"
                            @click="$store.app.togglePlannerHistory()"
                            class="text-xs text-blue-400 hover:text-blue-300 transition-colors">
                      <span x-text="$store.app.showPlannerHistory ? '▼ Hide History' : '▶ View History'"></span>
                    </button>
                  </div>
                </div>
                <textarea
                  id="planner-toml-textarea"
                  x-model="$store.app.plannerForm.toml"
                  x-init="setTimeout(() => { if (window.initTOMLHighlighter && $el.offsetParent) { $el._highlighter = initTOMLHighlighter($el); } }, 100)"
                  class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-xs text-gray-100 font-mono focus:border-blue-500 focus:outline-none resize-none"
                  rows="25"
                  placeholder="# Planner configuration in TOML format&#10;# Example:&#10;[planner]&#10;name = &quot;My Strategy&quot;&#10;&#10;[[calculators]]&#10;name = &quot;momentum&quot;&#10;# ... calculator configuration"
                  spellcheck="false"></textarea>
                <p class="text-xs text-gray-500 mt-1">Configure planner modules, calculators, patterns, and generators in TOML format</p>
              </div>

              <!-- Version History -->
              <div x-show="$store.app.showPlannerHistory && $store.app.plannerFormMode === 'edit'"
                   x-transition
                   class="border border-gray-700 rounded p-3 bg-gray-800/50">
                <h4 class="text-sm font-semibold text-gray-200 mb-2">Version History</h4>
                <div x-show="$store.app.plannerHistoryLoading" class="text-center py-4">
                  <span class="inline-block animate-spin text-lg">&#9696;</span>
                  <p class="text-xs text-gray-400 mt-1">Loading history...</p>
                </div>
                <div x-show="!$store.app.plannerHistoryLoading && $store.app.plannerHistory.length === 0"
                     class="text-sm text-gray-400 py-2">
                  No version history yet. History is created automatically when you save changes.
                </div>
                <div x-show="!$store.app.plannerHistoryLoading && $store.app.plannerHistory.length > 0"
                     class="space-y-2 max-h-60 overflow-y-auto">
                  <template x-for="(entry, index) in $store.app.plannerHistory" :key="entry.id">
                    <div class="bg-gray-900 border border-gray-700 rounded p-2 text-xs">
                      <div class="flex items-center justify-between mb-1">
                        <span class="text-gray-300 font-semibold" x-text="entry.name"></span>
                        <span class="text-gray-500" x-text="new Date(entry.saved_at).toLocaleString()"></span>
                      </div>
                      <div class="flex gap-3">
                        <button @click="$store.app.showPlannerDiff(entry)"
                                class="text-green-400 hover:text-green-300 text-xs">
                          Compare with current
                        </button>
                        <button @click="$store.app.restorePlannerVersion(entry)"
                                class="text-blue-400 hover:text-blue-300 text-xs">
                          Restore this version
                        </button>
                      </div>
                    </div>
                  </template>
                </div>
              </div>

              <!-- Validation Errors -->
              <div x-show="$store.app.plannerError"
                   class="bg-red-900/20 border border-red-700/50 rounded p-3">
                <p class="text-sm text-red-300">
                  <strong>Error:</strong>
                  <span x-text="$store.app.plannerError"></span>
                </p>
              </div>
            </div>
          </div>

          <!-- Footer -->
          <div class="flex justify-end gap-2 p-4 border-t border-gray-700">
            <template x-if="$store.app.plannerFormMode === 'edit'">
              <div class="flex justify-between w-full">
                <!-- Delete on left -->
                <button @click="$store.app.deletePlanner()"
                        :disabled="$store.app.plannerLoading"
                        class="px-4 py-2 bg-red-600 hover:bg-red-500 text-white text-sm rounded transition-colors disabled:opacity-50">
                  Delete
                </button>
                <!-- Cancel, Apply, and Save on right -->
                <div class="flex gap-2">
                  <button @click="$store.app.closePlannerManagement()"
                          class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors">
                    Cancel
                  </button>
                  <button @click="$store.app.applyPlannerConfig()"
                          x-show="$store.app.plannerForm.bucket_id"
                          :disabled="$store.app.plannerLoading"
                          class="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded transition-colors disabled:opacity-50"
                          title="Hot-reload this planner configuration for its bucket">
                    <span x-show="$store.app.plannerLoading" class="inline-block animate-spin mr-1">&#9696;</span>
                    <span x-text="$store.app.plannerLoading ? 'Applying...' : 'Apply'"></span>
                  </button>
                  <button @click="$store.app.savePlanner()"
                          :disabled="$store.app.plannerLoading || !$store.app.plannerForm.name || !$store.app.plannerForm.toml"
                          class="px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm rounded transition-colors disabled:opacity-50">
                    <span x-show="$store.app.plannerLoading" class="inline-block animate-spin mr-1">&#9696;</span>
                    <span x-text="$store.app.plannerLoading ? 'Saving...' : 'Save'"></span>
                  </button>
                </div>
              </div>
            </template>

            <template x-if="$store.app.plannerFormMode === 'create'">
              <div class="flex gap-2">
                <button @click="$store.app.closePlannerManagement()"
                        class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors">
                  Cancel
                </button>
                <button @click="$store.app.savePlanner()"
                        :disabled="$store.app.plannerLoading || !$store.app.plannerForm.name || !$store.app.plannerForm.toml"
                        class="px-4 py-2 bg-green-600 hover:bg-green-500 text-white text-sm rounded transition-colors disabled:opacity-50">
                  <span x-show="$store.app.plannerLoading" class="inline-block animate-spin mr-1">&#9696;</span>
                  <span x-text="$store.app.plannerLoading ? 'Creating...' : 'Create Planner'"></span>
                </button>
              </div>
            </template>

            <template x-if="$store.app.plannerFormMode === 'none'">
              <button @click="$store.app.closePlannerManagement()"
                      class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors">
                Close
              </button>
            </template>
          </div>
        </div>
      </div>

      <!-- Diff Viewer Modal -->
      <div x-data x-show="$store.app.showPlannerDiffModal"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
           x-transition>
        <div class="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-5xl modal-content max-h-[90vh] flex flex-col" @click.stop>
          <!-- Header -->
          <div class="flex items-center justify-between p-4 border-b border-gray-700">
            <h2 class="text-lg font-semibold text-gray-100">Version Comparison</h2>
            <button @click="$store.app.closePlannerDiff()"
                    class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
          </div>

          <!-- Body -->
          <div class="p-4 overflow-y-auto flex-1">
            <div x-html="$store.app.plannerDiffHtml"></div>
          </div>

          <!-- Footer -->
          <div class="flex justify-end gap-2 p-4 border-t border-gray-700">
            <button @click="$store.app.closePlannerDiff()"
                    class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors">
              Close
            </button>
          </div>
        </div>
      </div>
    `;
  }
}

customElements.define('planner-management-modal', PlannerManagementModal);
