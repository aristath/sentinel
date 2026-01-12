import { useState, useEffect, useCallback } from 'react';
import { Modal, Text, Button, TextInput, Group, Stack, Paper, Badge, Loader, ActionIcon } from '@mantine/core';
import { IconTrash } from '@tabler/icons-react';
import { api } from '../../api/client';
import { useNotifications } from '../../hooks/useNotifications';

// Catppuccin Mocha accent color palette for groups
// https://catppuccin.com/palette
const COLOR_PALETTE = [
  '#89b4fa', // Blue
  '#a6e3a1', // Green
  '#f38ba8', // Red
  '#f9e2af', // Yellow
  '#fab387', // Peach
  '#cba6f7', // Mauve
  '#94e2d5', // Teal
  '#89dceb', // Sky
  '#74c7ec', // Sapphire
  '#b4befe', // Lavender
  '#f5c2e7', // Pink
  '#f5e0dc', // Rosewater
  '#f2cdcd', // Flamingo
  '#eba0ac', // Maroon
  '#8caaee', // Blue (alternative)
  '#a6da95', // Green (alternative)
  '#ed8796', // Red (alternative)
  '#eed49f', // Yellow (alternative)
  '#f5a97f', // Peach (alternative)
  '#c6a0f6', // Mauve (alternative)
  '#8bd5ca', // Teal (alternative)
  '#91d7e3', // Sky (alternative)
  '#7dc4e4', // Sapphire (alternative)
  '#b7bdf8', // Lavender (alternative)
  '#f4b8e4', // Pink (alternative)
];

function hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return Math.abs(hash);
}

function getContrastColor(hexColor) {
  const r = parseInt(hexColor.slice(1, 3), 16);
  const g = parseInt(hexColor.slice(3, 5), 16);
  const b = parseInt(hexColor.slice(5, 7), 16);
  const brightness = (r * 299 + g * 587 + b * 114) / 1000;
  return brightness > 128 ? '#000000' : '#FFFFFF';
}

export function GroupingManager() {
  const { showNotification } = useNotifications();

  const [availableCountries, setAvailableCountries] = useState([]);
  const [availableIndustries, setAvailableIndustries] = useState([]);
  const [countryGroups, setCountryGroups] = useState({});
  const [industryGroups, setIndustryGroups] = useState({});
  const [groupColorMap, setGroupColorMap] = useState({});
  const [loading, setLoading] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [modalType, setModalType] = useState(null); // 'country' or 'industry'
  const [modalItem, setModalItem] = useState(null);
  const [newGroupName, setNewGroupName] = useState('');

  const assignColorsToGroups = useCallback((countryGroups, industryGroups) => {
    const allGroups = new Set();
    Object.keys(countryGroups).forEach(g => allGroups.add(g));
    Object.keys(industryGroups).forEach(g => allGroups.add(g));

    const colorMap = {};
    allGroups.forEach(groupName => {
      if (!colorMap[groupName]) {
        const hash = hashString(groupName);
        const colorIndex = hash % COLOR_PALETTE.length;
        colorMap[groupName] = COLOR_PALETTE[colorIndex];
      }
    });
    setGroupColorMap(colorMap);
  }, []);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [countriesRes, industriesRes, countryGroupsRes, industryGroupsRes] = await Promise.all([
        api.fetchAvailableCountries(),
        api.fetchAvailableIndustries(),
        api.fetchCountryGroups(),
        api.fetchIndustryGroups(),
      ]);

      const countries = (countriesRes.countries || []).sort();
      const industries = (industriesRes.industries || []).sort();

      // Ensure groups is an object, not an array
      let cGroups = countryGroupsRes.groups || {};
      if (Array.isArray(cGroups)) {
        cGroups = {};
      }

      let iGroups = industryGroupsRes.groups || {};
      if (Array.isArray(iGroups)) {
        iGroups = {};
      }

      setAvailableCountries(countries);
      setAvailableIndustries(industries);
      setCountryGroups(cGroups);
      setIndustryGroups(iGroups);
      assignColorsToGroups(cGroups, iGroups);
    } catch (error) {
      showNotification(`Failed to load grouping data: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  }, [showNotification, assignColorsToGroups]);

  useEffect(() => {
    loadData();
  }, []);

  // Returns array of all groups containing the country
  const getCountryGroups = (country) => {
    const groups = [];
    for (const [groupName, countries] of Object.entries(countryGroups)) {
      if (countries.includes(country)) {
        groups.push(groupName);
      }
    }
    return groups;
  };

  // Returns array of all groups containing the industry
  const getIndustryGroups = (industry) => {
    const groups = [];
    for (const [groupName, industries] of Object.entries(industryGroups)) {
      if (industries.includes(industry)) {
        groups.push(groupName);
      }
    }
    return groups;
  };

  const getCountryPillClass = (country) => {
    const groups = getCountryGroups(country);
    if (groups.length > 0) {
      return { variant: 'light' };
    }
    return { variant: 'outline', color: 'yellow' };
  };

  const getIndustryPillClass = (industry) => {
    const groups = getIndustryGroups(industry);
    if (groups.length > 0) {
      return { variant: 'light' };
    }
    return { variant: 'outline', color: 'yellow' };
  };

  const openAssignmentModal = (type, item) => {
    setModalType(type);
    setModalItem(item);
    setNewGroupName('');
    setShowModal(true);
  };

  const closeModal = () => {
    setShowModal(false);
    setModalType(null);
    setModalItem(null);
    setNewGroupName('');
  };

  // Returns array of all groups the current modal item belongs to
  const getCurrentGroups = () => {
    if (modalType === 'country') {
      return getCountryGroups(modalItem);
    } else {
      return getIndustryGroups(modalItem);
    }
  };

  const getExistingGroups = () => {
    if (modalType === 'country') {
      // Ensure countryGroups is an object, not an array
      const groups = countryGroups && !Array.isArray(countryGroups) ? countryGroups : {};
      return Object.keys(groups).sort();
    } else {
      // Ensure industryGroups is an object, not an array
      const groups = industryGroups && !Array.isArray(industryGroups) ? industryGroups : {};
      return Object.keys(groups).sort();
    }
  };

  // Remove item from a specific group
  const removeFromGroup = async (groupName) => {
    if (!groupName) return;

    try {
      if (modalType === 'country') {
        const countries = countryGroups[groupName].filter(c => c !== modalItem);
        await api.updateCountryGroup({
          group_name: groupName,
          country_names: countries,
        });
      } else {
        const industries = industryGroups[groupName].filter(i => i !== modalItem);
        await api.updateIndustryGroup({
          group_name: groupName,
          industry_names: industries,
        });
      }
      showNotification(`Removed from ${groupName}`, 'success');
      await loadData();
    } catch (error) {
      showNotification(`Failed to remove assignment: ${error.message}`, 'error');
    }
  };

  const assignToGroup = async (groupName) => {
    // Check if already assigned to this group
    const currentGroups = getCurrentGroups();
    if (currentGroups.includes(groupName)) {
      showNotification(`Already assigned to ${groupName}`, 'info');
      return;
    }

    try {
      if (modalType === 'country') {
        const countries = [...(countryGroups[groupName] || []), modalItem];
        await api.updateCountryGroup({
          group_name: groupName,
          country_names: countries,
        });
      } else {
        const industries = [...(industryGroups[groupName] || []), modalItem];
        await api.updateIndustryGroup({
          group_name: groupName,
          industry_names: industries,
        });
      }
      showNotification(`Added to ${groupName}`, 'success');
      await loadData();
      // Don't close modal - allow adding to multiple groups
    } catch (error) {
      showNotification(`Failed to assign to group: ${error.message}`, 'error');
    }
  };

  const createAndAssignGroup = async () => {
    if (!newGroupName.trim()) return;

    try {
      if (modalType === 'country') {
        await api.updateCountryGroup({
          group_name: newGroupName.trim(),
          country_names: [modalItem],
        });
      } else {
        await api.updateIndustryGroup({
          group_name: newGroupName.trim(),
          industry_names: [modalItem],
        });
      }
      showNotification(`Created group "${newGroupName.trim()}" and assigned`, 'success');
      setNewGroupName('');
      await loadData();
      // Don't close modal - allow adding to more groups
    } catch (error) {
      showNotification(`Failed to create group: ${error.message}`, 'error');
    }
  };

  const deleteGroup = async (groupName) => {
    const groupType = modalType === 'country' ? 'country' : 'industry';
    const confirmMessage = `Are you sure you want to delete the ${groupType} group "${groupName}"? This will remove all assignments in this group.`;

    if (!window.confirm(confirmMessage)) {
      return;
    }

    try {
      if (modalType === 'country') {
        await api.deleteCountryGroup(groupName);
      } else {
        await api.deleteIndustryGroup(groupName);
      }
      showNotification(`Group "${groupName}" deleted successfully`, 'success');
      await loadData();
    } catch (error) {
      showNotification(`Failed to delete group: ${error.message}`, 'error');
    }
  };

  if (loading) {
    return (
      <Group justify="center" p="xl">
        <Loader />
        <Text c="dimmed">Loading grouping data...</Text>
      </Group>
    );
  }

  return (
    <>
      <Stack gap="lg">
        {/* Country Groups */}
        <div>
          <Text size="sm" fw={500} mb="md">Countries</Text>
          <Group gap="xs" wrap="wrap">
            {availableCountries.map((country) => {
              const groups = getCountryGroups(country);
              const pillClass = getCountryPillClass(country);

              return (
                <Button
                  key={country}
                  onClick={() => openAssignmentModal('country', country)}
                  {...pillClass}
                  size="sm"
                  style={{ position: 'relative' }}
                >
                  {country}
                  {groups.length > 0 && groups.map((group) => (
                    <Badge
                      key={group}
                      size="xs"
                      style={{
                        marginLeft: '4px',
                        backgroundColor: groupColorMap[group],
                        color: getContrastColor(groupColorMap[group]),
                      }}
                    >
                      {group}
                    </Badge>
                  ))}
                  {groups.length === 0 && (
                    <Text size="xs" c="yellow" style={{ marginLeft: '4px' }}>
                      ⚠️
                    </Text>
                  )}
                </Button>
              );
            })}
          </Group>
        </div>

        {/* Industry Groups */}
        <div>
          <Text size="sm" fw={500} mb="md">Industries</Text>
          <Group gap="xs" wrap="wrap">
            {availableIndustries.map((industry) => {
              const groups = getIndustryGroups(industry);
              const pillClass = getIndustryPillClass(industry);

              return (
                <Button
                  key={industry}
                  onClick={() => openAssignmentModal('industry', industry)}
                  {...pillClass}
                  size="sm"
                  style={{ position: 'relative' }}
                >
                  {industry}
                  {groups.length > 0 && groups.map((group) => (
                    <Badge
                      key={group}
                      size="xs"
                      style={{
                        marginLeft: '4px',
                        backgroundColor: groupColorMap[group],
                        color: getContrastColor(groupColorMap[group]),
                      }}
                    >
                      {group}
                    </Badge>
                  ))}
                  {groups.length === 0 && (
                    <Text size="xs" c="yellow" style={{ marginLeft: '4px' }}>
                      ⚠️
                    </Text>
                  )}
                </Button>
              );
            })}
          </Group>
        </div>
      </Stack>

      {/* Assignment Modal */}
      <Modal
        opened={showModal}
        onClose={closeModal}
        title={`Assign ${modalItem}`}
        size="md"
      >
        <Stack gap="md">
          {/* Current Groups */}
          {getCurrentGroups().length > 0 && (
            <Paper p="md" withBorder>
              <Text size="sm" fw={500} mb="xs">
                Current groups ({getCurrentGroups().length}):
              </Text>
              <Group gap="xs" wrap="wrap">
                {getCurrentGroups().map((group) => (
                  <Badge
                    key={group}
                    size="lg"
                    rightSection={
                      <ActionIcon
                        size="xs"
                        color="red"
                        variant="transparent"
                        onClick={() => removeFromGroup(group)}
                        style={{ marginLeft: '4px' }}
                      >
                        ×
                      </ActionIcon>
                    }
                    style={{
                      backgroundColor: groupColorMap[group],
                      color: getContrastColor(groupColorMap[group]),
                      paddingRight: '4px',
                    }}
                  >
                    {group}
                  </Badge>
                ))}
              </Group>
              {getCurrentGroups().length > 1 && (
                <Text size="xs" c="dimmed" mt="xs">
                  Value will be split equally across {getCurrentGroups().length} groups
                </Text>
              )}
            </Paper>
          )}

          {/* Assign to Existing Group */}
          <div>
            <Text size="sm" fw={500} mb="xs">Add to group:</Text>
            <Stack gap="xs" style={{ maxHeight: '200px', overflowY: 'auto' }}>
              {getExistingGroups().length === 0 ? (
                <Text size="xs" c="dimmed" p="sm">
                  No groups exist yet. Create one below.
                </Text>
              ) : (
                getExistingGroups().map((groupName) => {
                  const isAssigned = getCurrentGroups().includes(groupName);
                  return (
                    <Group key={groupName} justify="space-between" gap="xs">
                      <Button
                        onClick={() => assignToGroup(groupName)}
                        variant={isAssigned ? 'filled' : 'light'}
                        justify="flex-start"
                        style={{ flex: 1 }}
                        disabled={isAssigned}
                      >
                        <div
                          style={{
                            width: '16px',
                            height: '16px',
                            borderRadius: '4px',
                            backgroundColor: groupColorMap[groupName],
                            marginRight: '8px',
                          }}
                        />
                        {groupName}
                        {isAssigned && (
                          <Text size="xs" c="dimmed" ml="xs">
                            (assigned)
                          </Text>
                        )}
                      </Button>
                      <ActionIcon
                        color="red"
                        variant="light"
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteGroup(groupName);
                        }}
                        title={`Delete group "${groupName}"`}
                      >
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Group>
                  );
                })
              )}
            </Stack>
          </div>

          {/* Create New Group */}
          <Paper p="md" withBorder>
            <Text size="sm" fw={500} mb="xs">Create new group:</Text>
            <Group>
              <TextInput
                placeholder="Group name (e.g., EU, US, Technology)"
                value={newGroupName}
                onChange={(e) => setNewGroupName(e.currentTarget.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    createAndAssignGroup();
                  }
                }}
                style={{ flex: 1 }}
              />
              <Button
                onClick={createAndAssignGroup}
                disabled={!newGroupName.trim()}
              >
                Create & Add
              </Button>
            </Group>
          </Paper>

          {/* Done button */}
          <Button variant="default" onClick={closeModal}>
            Done
          </Button>
        </Stack>
      </Modal>
    </>
  );
}
