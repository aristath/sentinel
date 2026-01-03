/**
 * Bucket Health Modal Component
 * Shows health metrics and allows manual cash transfers for a specific bucket
 */
class BucketHealthModal extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data x-show="$store.app.showBucketHealthModal"
           class="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 flex items-center justify-center p-4"
           x-transition>
        <div class="bg-gray-800 border border-gray-700 rounded-lg w-full max-w-2xl modal-content" @click.stop>
          <template x-if="$store.app.selectedBucket">
            <div>
              <div class="flex items-center justify-between p-4 border-b border-gray-700">
                <div>
                  <h2 class="text-lg font-semibold text-gray-100" x-text="$store.app.selectedBucket.name"></h2>
                  <p class="text-xs text-gray-400 mt-0.5">
                    <span x-text="$store.app.selectedBucket.type === 'core' ? 'Core Universe' : 'Satellite Universe'"></span>
                  </p>
                </div>
                <button @click="$store.app.closeBucketHealth()"
                        class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
              </div>

              <div class="p-4 space-y-4">
                <!-- Health Metrics -->
                <div class="grid grid-cols-2 gap-3">
                  <!-- Status -->
                  <div class="bg-gray-900 border border-gray-700 rounded p-3">
                    <div class="text-xs text-gray-400 mb-1">Status</div>
                    <div class="flex items-center gap-2">
                      <div :class="{
                        'w-2 h-2 rounded-full': true,
                        'bg-green-500': $store.app.selectedBucket.status === 'active',
                        'bg-yellow-500': $store.app.selectedBucket.status === 'accumulating',
                        'bg-orange-500': $store.app.selectedBucket.status === 'hibernating',
                        'bg-gray-500': $store.app.selectedBucket.status === 'paused',
                        'bg-red-500': $store.app.selectedBucket.status === 'retired'
                      }"></div>
                      <span class="text-sm font-medium text-gray-100 capitalize" x-text="$store.app.selectedBucket.status"></span>
                    </div>
                  </div>

                  <!-- Cash Balance -->
                  <div class="bg-gray-900 border border-gray-700 rounded p-3">
                    <div class="text-xs text-gray-400 mb-1">Cash Balance</div>
                    <div class="text-sm font-medium text-gray-100">
                      <template x-if="$store.app.bucketBalances[$store.app.selectedBucket.id]">
                        <span x-text="'€' + ($store.app.bucketBalances[$store.app.selectedBucket.id].EUR || 0).toFixed(2)"></span>
                      </template>
                      <template x-if="!$store.app.bucketBalances[$store.app.selectedBucket.id]">
                        <span>€0.00</span>
                      </template>
                    </div>
                  </div>

                  <!-- Target Allocation -->
                  <template x-if="$store.app.selectedBucket.type === 'satellite'">
                    <div class="bg-gray-900 border border-gray-700 rounded p-3">
                      <div class="text-xs text-gray-400 mb-1">Target Allocation</div>
                      <div class="text-sm font-medium text-gray-100">
                        <span x-text="($store.app.selectedBucket.target_pct * 100).toFixed(1) + '%'"></span>
                      </div>
                    </div>
                  </template>

                  <!-- High Water Mark -->
                  <template x-if="$store.app.selectedBucket.high_water_mark">
                    <div class="bg-gray-900 border border-gray-700 rounded p-3">
                      <div class="text-xs text-gray-400 mb-1">High Water Mark</div>
                      <div class="text-sm font-medium text-gray-100">
                        <span x-text="'€' + $store.app.selectedBucket.high_water_mark.toFixed(2)"></span>
                      </div>
                    </div>
                  </template>
                </div>

                <!-- Manual Cash Transfer -->
                <div class="border border-gray-700 rounded-lg p-4 mt-4">
                  <h3 class="text-sm font-semibold text-gray-200 mb-3">Manual Cash Transfer</h3>

                  <div class="space-y-3">
                    <!-- From Bucket -->
                    <div>
                      <label class="block text-xs text-gray-400 mb-1">From Universe</label>
                      <select x-model="$store.app.cashTransfer.fromBucket"
                              class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                        <option value="">Select source universe</option>
                        <template x-for="bucket in $store.app.buckets" :key="bucket.id">
                          <option :value="bucket.id" x-text="bucket.name"></option>
                        </template>
                      </select>
                    </div>

                    <!-- To Bucket -->
                    <div>
                      <label class="block text-xs text-gray-400 mb-1">To Universe</label>
                      <select x-model="$store.app.cashTransfer.toBucket"
                              class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                        <option value="">Select destination universe</option>
                        <template x-for="bucket in $store.app.buckets" :key="bucket.id">
                          <option :value="bucket.id" x-text="bucket.name"></option>
                        </template>
                      </select>
                    </div>

                    <!-- Amount -->
                    <div>
                      <label class="block text-xs text-gray-400 mb-1">Amount (EUR)</label>
                      <input type="number"
                             x-model="$store.app.cashTransfer.amount"
                             min="0"
                             step="0.01"
                             placeholder="0.00"
                             class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                    </div>

                    <!-- Currency -->
                    <div>
                      <label class="block text-xs text-gray-400 mb-1">Currency</label>
                      <select x-model="$store.app.cashTransfer.currency"
                              class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                        <option value="EUR">EUR</option>
                        <option value="USD">USD</option>
                        <option value="GBP">GBP</option>
                        <option value="HKD">HKD</option>
                      </select>
                    </div>

                    <!-- Description -->
                    <div>
                      <label class="block text-xs text-gray-400 mb-1">Description (optional)</label>
                      <input type="text"
                             x-model="$store.app.cashTransfer.description"
                             placeholder="e.g., 'Rebalancing', 'Jumpstart new satellite'"
                             class="w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded text-sm text-gray-100 focus:border-blue-500 focus:outline-none">
                    </div>

                    <!-- Transfer Button -->
                    <button @click="$store.app.executeCashTransfer()"
                            :disabled="!$store.app.cashTransfer.fromBucket || !$store.app.cashTransfer.toBucket || !$store.app.cashTransfer.amount || $store.app.transferringCash"
                            class="w-full px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                      <span x-show="$store.app.transferringCash" class="inline-block animate-spin mr-1">&#9696;</span>
                      <span x-text="$store.app.transferringCash ? 'Transferring...' : 'Execute Transfer'"></span>
                    </button>
                  </div>
                </div>
              </div>

              <div class="flex justify-end gap-2 p-4 border-t border-gray-700">
                <button @click="$store.app.closeBucketHealth()"
                        class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors">
                  Close
                </button>
              </div>
            </div>
          </template>
        </div>
      </div>
    `;
  }
}

customElements.define('bucket-health-modal', BucketHealthModal);
