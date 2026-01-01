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

              <!-- Bucket ID (optional, shown in edit mode) -->
              <div x-show="$store.app.plannerFormMode === 'edit' && $store.app.plannerForm.bucket_id">
                <label class="block text-sm text-gray-300 mb-1">Associated Bucket</label>
                <input type="text"
                       :value="$store.app.plannerForm.bucket_id || 'None (Template)'"
                       disabled
                       class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-400 cursor-not-allowed">
                <p class="text-xs text-gray-500 mt-1">Bucket assignments are managed separately</p>
              </div>

              <!-- TOML Configuration Textarea -->
              <div>
                <label class="block text-sm text-gray-300 mb-1">TOML Configuration *</label>
                <textarea
                  x-model="$store.app.plannerForm.toml"
                  class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-xs text-gray-100 font-mono focus:border-blue-500 focus:outline-none resize-none"
                  rows="25"
                  placeholder="# Planner configuration in TOML format&#10;# Example:&#10;[planner]&#10;name = &quot;My Strategy&quot;&#10;&#10;[[calculators]]&#10;name = &quot;momentum&quot;&#10;# ... calculator configuration"
                  spellcheck="false"></textarea>
                <p class="text-xs text-gray-500 mt-1">Configure planner modules, calculators, patterns, and generators in TOML format</p>
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
                <!-- Cancel and Save on right -->
                <div class="flex gap-2">
                  <button @click="$store.app.closePlannerManagement()"
                          class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors">
                    Cancel
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
    `;
  }
}

customElements.define('planner-management-modal', PlannerManagementModal);
