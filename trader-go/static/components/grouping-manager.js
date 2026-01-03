/**
 * Grouping Manager Component
 *
 * Modern pill/tag interface for managing country and industry groups.
 * Shows all items inline with their group assignments and colors.
 */
class GroupingManager extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `
      <div x-data="groupingManager()" x-init="init()" class="space-y-6">
        <!-- Country Groups -->
        <div>
          <h3 class="text-sm font-medium text-gray-300 mb-3">Countries</h3>
          <div class="flex flex-wrap gap-2">
            <template x-for="country in availableCountries" :key="country">
              <button
                @click="openAssignmentModal('country', country)"
                class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm transition-colors"
                :class="getCountryPillClass(country)">
                <span x-text="country"></span>
                <template x-if="getCountryGroup(country)">
                  <span class="px-2 py-0.5 rounded text-xs font-medium"
                        :style="'background-color: ' + getGroupColor(getCountryGroup(country)) + '; color: ' + getContrastColor(getGroupColor(getCountryGroup(country)))"
                        x-text="'| ' + getCountryGroup(country)"></span>
                </template>
                <template x-if="!getCountryGroup(country)">
                  <span class="text-yellow-400" title="Unassigned">⚠️</span>
                </template>
              </button>
            </template>
          </div>
        </div>

        <!-- Industry Groups -->
        <div>
          <h3 class="text-sm font-medium text-gray-300 mb-3">Industries</h3>
          <div class="flex flex-wrap gap-2">
            <template x-for="industry in availableIndustries" :key="industry">
              <button
                @click="openAssignmentModal('industry', industry)"
                class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-sm transition-colors"
                :class="getIndustryPillClass(industry)">
                <span x-text="industry"></span>
                <template x-if="getIndustryGroup(industry)">
                  <span class="px-2 py-0.5 rounded text-xs font-medium"
                        :style="'background-color: ' + getGroupColor(getIndustryGroup(industry)) + '; color: ' + getContrastColor(getGroupColor(getIndustryGroup(industry)))"
                        x-text="'| ' + getIndustryGroup(industry)"></span>
                </template>
                <template x-if="!getIndustryGroup(industry)">
                  <span class="text-yellow-400" title="Unassigned">⚠️</span>
                </template>
              </button>
            </template>
          </div>
        </div>

        <!-- Assignment Modal -->
        <div x-show="showModal" x-transition
             class="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center"
             @click.self="closeModal()">
          <div class="bg-gray-800 border border-gray-700 rounded-lg p-6 max-w-md w-full mx-4">
            <div class="flex items-center justify-between mb-4">
              <h3 class="text-lg font-semibold text-gray-100">
                Assign <span x-text="modalItem"></span>
              </h3>
              <button @click="closeModal()" class="text-gray-400 hover:text-gray-200 text-2xl leading-none">&times;</button>
            </div>

            <div class="space-y-4">
              <!-- Current Assignment -->
              <div x-show="getCurrentGroup()">
                <p class="text-sm text-gray-300 mb-2">Current group:</p>
                <div class="flex items-center gap-2">
                  <span class="px-3 py-1.5 rounded text-sm font-medium"
                        :style="'background-color: ' + getGroupColor(getCurrentGroup()) + '; color: ' + getContrastColor(getGroupColor(getCurrentGroup()))"
                        x-text="getCurrentGroup()"></span>
                  <button @click="removeAssignment()"
                          class="px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm rounded transition-colors">
                    Remove
                  </button>
                </div>
              </div>

              <!-- Assign to Existing Group -->
              <div>
                <p class="text-sm text-gray-300 mb-2">Assign to existing group:</p>
                <div class="space-y-2 max-h-48 overflow-y-auto">
                  <template x-for="groupName in getExistingGroups()" :key="groupName">
                    <button
                      @click="assignToGroup(groupName)"
                      class="w-full text-left px-3 py-2 rounded hover:bg-gray-700 transition-colors flex items-center gap-2"
                      :class="getCurrentGroup() === groupName ? 'bg-gray-700' : ''">
                      <span class="w-4 h-4 rounded"
                            :style="'background-color: ' + getGroupColor(groupName)"></span>
                      <span class="text-sm text-gray-300" x-text="groupName"></span>
                    </button>
                  </template>
                  <p x-show="getExistingGroups().length === 0" class="text-xs text-gray-300 px-3 py-2">
                    No groups exist yet. Create one below.
                  </p>
                </div>
              </div>

              <!-- Create New Group -->
              <div class="pt-4 border-t border-gray-700">
                <p class="text-sm text-gray-300 mb-2">Create new group:</p>
                <div class="flex gap-2">
                  <input
                    type="text"
                    x-model="newGroupName"
                    @keyup.enter="createAndAssignGroup()"
                    placeholder="Group name (e.g., EU, US, Technology)"
                    class="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded text-sm text-gray-200 focus:outline-none focus:border-blue-500">
                  <button
                    @click="createAndAssignGroup()"
                    :disabled="!newGroupName || !newGroupName.trim()"
                    class="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-500 disabled:cursor-not-allowed text-white text-sm rounded transition-colors">
                    Create & Assign
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    `;
  }
}

// Alpine.js component
function groupingManager() {
  // 25-color palette for groups
  const COLOR_PALETTE = [
    '#3B82F6', // blue
    '#10B981', // emerald
    '#F59E0B', // amber
    '#EF4444', // red
    '#8B5CF6', // violet
    '#06B6D4', // cyan
    '#EC4899', // pink
    '#84CC16', // lime
    '#F97316', // orange
    '#6366F1', // indigo
    '#14B8A6', // teal
    '#A855F7', // purple
    '#22C55E', // green
    '#EAB308', // yellow
    '#F43F5E', // rose
    '#0EA5E9', // sky
    '#64748B', // slate
    '#78716C', // stone
    '#B91C1C', // red-800
    '#059669', // emerald-600
    '#DC2626', // red-600
    '#7C3AED', // violet-600
    '#0891B2', // cyan-600
    '#BE185D', // pink-700
    '#CA8A04', // yellow-600
  ];

  return {
    availableCountries: [],
    availableIndustries: [],
    countryGroups: {},
    industryGroups: {},
    loading: false,
    showModal: false,
    modalType: null, // 'country' or 'industry'
    modalItem: null,
    newGroupName: '',
    groupColorMap: {}, // Maps group names to colors

    async init() {
      await this.loadData();
      this.assignColorsToGroups();
    },

    assignColorsToGroups() {
      // Assign colors to all existing groups
      const allGroups = new Set();
      Object.keys(this.countryGroups).forEach(g => allGroups.add(g));
      Object.keys(this.industryGroups).forEach(g => allGroups.add(g));

      allGroups.forEach(groupName => {
        if (!this.groupColorMap[groupName]) {
          // Hash group name to get consistent color
          const hash = this.hashString(groupName);
          const colorIndex = hash % COLOR_PALETTE.length;
          this.groupColorMap[groupName] = COLOR_PALETTE[colorIndex];
        }
      });
    },

    hashString(str) {
      let hash = 0;
      for (let i = 0; i < str.length; i++) {
        const char = str.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // Convert to 32bit integer
      }
      return Math.abs(hash);
    },

    getGroupColor(groupName) {
      if (!groupName) return '#6B7280'; // gray default
      if (!this.groupColorMap[groupName]) {
        const hash = this.hashString(groupName);
        const colorIndex = hash % COLOR_PALETTE.length;
        this.groupColorMap[groupName] = COLOR_PALETTE[colorIndex];
      }
      return this.groupColorMap[groupName];
    },

    getContrastColor(hexColor) {
      // Simple contrast calculation - return white or black based on brightness
      const r = parseInt(hexColor.slice(1, 3), 16);
      const g = parseInt(hexColor.slice(3, 5), 16);
      const b = parseInt(hexColor.slice(5, 7), 16);
      const brightness = (r * 299 + g * 587 + b * 114) / 1000;
      return brightness > 128 ? '#000000' : '#FFFFFF';
    },

    async loadData() {
      this.loading = true;
      try {
        const [countriesRes, industriesRes, countryGroupsRes, industryGroupsRes] = await Promise.all([
          fetch('/api/allocation/groups/available/countries'),
          fetch('/api/allocation/groups/available/industries'),
          fetch('/api/allocation/groups/country'),
          fetch('/api/allocation/groups/industry'),
        ]);

        const countries = await countriesRes.json();
        const industries = await industriesRes.json();
        const countryGroups = await countryGroupsRes.json();
        const industryGroups = await industryGroupsRes.json();

        this.availableCountries = (countries.countries || []).sort();
        this.availableIndustries = (industries.industries || []).sort();
        this.countryGroups = countryGroups.groups || {};
        this.industryGroups = industryGroups.groups || {};

        this.assignColorsToGroups();
      } catch (error) {
        console.error('Failed to load grouping data:', error);
        this.showError('Failed to load grouping data');
      } finally {
        this.loading = false;
      }
    },

    getCountryGroup(country) {
      for (const [groupName, countries] of Object.entries(this.countryGroups)) {
        if (countries.includes(country)) {
          return groupName;
        }
      }
      return null;
    },

    getIndustryGroup(industry) {
      for (const [groupName, industries] of Object.entries(this.industryGroups)) {
        if (industries.includes(industry)) {
          return groupName;
        }
      }
      return null;
    },

    getCountryPillClass(country) {
      const group = this.getCountryGroup(country);
      if (group) {
        return 'bg-gray-700 hover:bg-gray-600 text-gray-200';
      }
      return 'bg-gray-700 hover:bg-gray-600 text-gray-200 border-2 border-yellow-500';
    },

    getIndustryPillClass(industry) {
      const group = this.getIndustryGroup(industry);
      if (group) {
        return 'bg-gray-700 hover:bg-gray-600 text-gray-200';
      }
      return 'bg-gray-700 hover:bg-gray-600 text-gray-200 border-2 border-yellow-500';
    },

    openAssignmentModal(type, item) {
      this.modalType = type;
      this.modalItem = item;
      this.newGroupName = '';
      this.showModal = true;
    },

    closeModal() {
      this.showModal = false;
      this.modalType = null;
      this.modalItem = null;
      this.newGroupName = '';
    },

    getCurrentGroup() {
      if (this.modalType === 'country') {
        return this.getCountryGroup(this.modalItem);
      } else if (this.modalType === 'industry') {
        return this.getIndustryGroup(this.modalItem);
      }
      return null;
    },

    getExistingGroups() {
      if (this.modalType === 'country') {
        return Object.keys(this.countryGroups).sort();
      } else if (this.modalType === 'industry') {
        return Object.keys(this.industryGroups).sort();
      }
      return [];
    },

    async assignToGroup(groupName) {
      if (this.modalType === 'country') {
        await this.assignCountryToGroup(this.modalItem, groupName);
      } else if (this.modalType === 'industry') {
        await this.assignIndustryToGroup(this.modalItem, groupName);
      }
      this.closeModal();
    },

    async createAndAssignGroup() {
      if (!this.newGroupName || !this.newGroupName.trim()) return;

      const groupName = this.newGroupName.trim();
      if (this.modalType === 'country') {
        await this.assignCountryToGroup(this.modalItem, groupName);
      } else if (this.modalType === 'industry') {
        await this.assignIndustryToGroup(this.modalItem, groupName);
      }
      this.closeModal();
    },

    async removeAssignment() {
      const currentGroup = this.getCurrentGroup();
      if (!currentGroup) return;

      if (this.modalType === 'country') {
        await this.removeCountryFromGroup(this.modalItem, currentGroup);
      } else if (this.modalType === 'industry') {
        await this.removeIndustryFromGroup(this.modalItem, currentGroup);
      }
      this.closeModal();
    },

    async assignCountryToGroup(country, groupName) {
      // Remove from current group if any
      const currentGroup = this.getCountryGroup(country);
      if (currentGroup) {
        await this.removeCountryFromGroup(country, currentGroup);
      }

      // Add to new group
      const countries = this.countryGroups[groupName] || [];
      if (!countries.includes(country)) {
        countries.push(country);
        await this.saveCountryGroup(groupName, countries);
      }
    },

    async assignIndustryToGroup(industry, groupName) {
      // Remove from current group if any
      const currentGroup = this.getIndustryGroup(industry);
      if (currentGroup) {
        await this.removeIndustryFromGroup(industry, currentGroup);
      }

      // Add to new group
      const industries = this.industryGroups[groupName] || [];
      if (!industries.includes(industry)) {
        industries.push(industry);
        await this.saveIndustryGroup(groupName, industries);
      }
    },

    async removeCountryFromGroup(country, groupName) {
      const countries = [...(this.countryGroups[groupName] || [])];
      const index = countries.indexOf(country);
      if (index > -1) {
        countries.splice(index, 1);
        if (countries.length === 0) {
          // Delete empty group
          await this.deleteCountryGroup(groupName);
        } else {
          await this.saveCountryGroup(groupName, countries);
        }
      }
    },

    async removeIndustryFromGroup(industry, groupName) {
      const industries = [...(this.industryGroups[groupName] || [])];
      const index = industries.indexOf(industry);
      if (index > -1) {
        industries.splice(index, 1);
        if (industries.length === 0) {
          // Delete empty group
          await this.deleteIndustryGroup(groupName);
        } else {
          await this.saveIndustryGroup(groupName, industries);
        }
      }
    },

    async saveCountryGroup(groupName, countries) {
      try {
        const response = await fetch('/api/allocation/groups/country', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ group_name: groupName, country_names: countries }),
        });

        if (response.ok) {
          await this.loadData();
          this.showSuccess('Country group saved');
        } else {
          const error = await response.json();
          this.showError(error.detail || 'Failed to save country group');
        }
      } catch (error) {
        console.error('Error saving country group:', error);
        this.showError('Failed to save country group');
      }
    },

    async saveIndustryGroup(groupName, industries) {
      try {
        const response = await fetch('/api/allocation/groups/industry', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ group_name: groupName, industry_names: industries }),
        });

        if (response.ok) {
          await this.loadData();
          this.showSuccess('Industry group saved');
        } else {
          const error = await response.json();
          this.showError(error.detail || 'Failed to save industry group');
        }
      } catch (error) {
        console.error('Error saving industry group:', error);
        this.showError('Failed to save industry group');
      }
    },

    async deleteCountryGroup(groupName) {
      try {
        const response = await fetch(`/api/allocation/groups/country/${encodeURIComponent(groupName)}`, {
          method: 'DELETE',
        });

        if (response.ok) {
          await this.loadData();
          this.showSuccess('Country group deleted');
        } else {
          this.showError('Failed to delete country group');
        }
      } catch (error) {
        console.error('Error deleting country group:', error);
        this.showError('Failed to delete country group');
      }
    },

    async deleteIndustryGroup(groupName) {
      try {
        const response = await fetch(`/api/allocation/groups/industry/${encodeURIComponent(groupName)}`, {
          method: 'DELETE',
        });

        if (response.ok) {
          await this.loadData();
          this.showSuccess('Industry group deleted');
        } else {
          this.showError('Failed to delete industry group');
        }
      } catch (error) {
        console.error('Error deleting industry group:', error);
        this.showError('Failed to delete industry group');
      }
    },

    showSuccess(message) {
      if (window.Alpine && window.Alpine.store && window.Alpine.store('app')) {
        window.Alpine.store('app').message = message;
        window.Alpine.store('app').messageType = 'success';
        setTimeout(() => {
          window.Alpine.store('app').message = '';
        }, 3000);
      } else {
        console.log('Success:', message);
      }
    },

    showError(message) {
      if (window.Alpine && window.Alpine.store && window.Alpine.store('app')) {
        window.Alpine.store('app').message = message;
        window.Alpine.store('app').messageType = 'error';
        setTimeout(() => {
          window.Alpine.store('app').message = '';
        }, 5000);
      } else {
        console.error('Error:', message);
      }
    },
  };
}

customElements.define('grouping-manager', GroupingManager);
