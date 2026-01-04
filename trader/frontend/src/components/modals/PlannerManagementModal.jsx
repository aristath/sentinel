import { useState, useEffect } from 'react';
import { Modal, Text, Button, Select, Textarea, Group, Stack, Paper, Alert, Loader, ActionIcon } from '@mantine/core';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { api } from '../../api/client';
import { useNotifications } from '../../hooks/useNotifications';
import { computeLineDiff, renderDiffHTML } from '../../utils/diff';
import { IconX } from '@tabler/icons-react';

const PLANNER_TEMPLATES = {
  conservative: `[planner]
name = "Conservative Strategy"
description = "Low-risk, steady growth approach"

[[calculators]]
name = "momentum"
weight = 0.3
lookback_days = 90

[[calculators]]
name = "value"
weight = 0.4
pe_threshold = 15.0

[[calculators]]
name = "quality"
weight = 0.3
min_roe = 0.15
`,

  balanced: `[planner]
name = "Balanced Growth"
description = "Moderate risk, balanced approach"

[[calculators]]
name = "momentum"
weight = 0.4
lookback_days = 60

[[calculators]]
name = "value"
weight = 0.3
pe_threshold = 20.0

[[calculators]]
name = "quality"
weight = 0.3
min_roe = 0.12
`,

  aggressive: `[planner]
name = "Aggressive Growth"
description = "High-risk, high-reward strategy"

[[calculators]]
name = "momentum"
weight = 0.5
lookback_days = 30

[[calculators]]
name = "value"
weight = 0.2
pe_threshold = 25.0

[[calculators]]
name = "quality"
weight = 0.3
min_roe = 0.10
`,
};

export function PlannerManagementModal() {
  const { showPlannerManagementModal, closePlannerManagementModal } = useAppStore();
  const { buckets } = usePortfolioStore();
  const { showNotification } = useNotifications();

  const [planners, setPlanners] = useState([]);
  const [selectedPlannerId, setSelectedPlannerId] = useState('');
  const [plannerForm, setPlannerForm] = useState({ name: '', toml: '', bucket_id: '' });
  const [formMode, setFormMode] = useState('none'); // 'none', 'create', 'edit'
  const [loading, setLoading] = useState(false);
  const [plannerLoading, setPlannerLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [showDiff, setShowDiff] = useState(false);
  const [diffHtml, setDiffHtml] = useState('');

  useEffect(() => {
    if (showPlannerManagementModal) {
      loadPlanners();
    }
  }, [showPlannerManagementModal]);

  useEffect(() => {
    if (selectedPlannerId) {
      loadPlanner(selectedPlannerId);
    } else {
      setFormMode('none');
      setPlannerForm({ name: '', toml: '', bucket_id: '' });
    }
  }, [selectedPlannerId]);

  const loadPlanners = async () => {
    setLoading(true);
    try {
      const data = await api.fetchPlanners();
      setPlanners(Array.isArray(data) ? data : (data.planners || []));
    } catch (error) {
      showNotification(`Failed to load planners: ${error.message}`, 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadPlanner = async (id) => {
    setPlannerLoading(true);
    setError(null);
    try {
      const planner = await api.fetchPlannerById(id);
      setPlannerForm({
        name: planner.name || '',
        toml: planner.toml || planner.config || '',
        bucket_id: planner.bucket_id || '',
      });
      setFormMode('edit');
    } catch (error) {
      setError(`Failed to load planner: ${error.message}`);
      showNotification(`Failed to load planner: ${error.message}`, 'error');
    } finally {
      setPlannerLoading(false);
    }
  };

  const startCreate = () => {
    setSelectedPlannerId('');
    setPlannerForm({ name: '', toml: '', bucket_id: '' });
    setFormMode('create');
    setError(null);
  };

  const loadTemplate = (templateName) => {
    const template = PLANNER_TEMPLATES[templateName];
    if (template) {
      setPlannerForm({ ...plannerForm, toml: template });
    }
  };

  const savePlanner = async () => {
    if (!plannerForm.name || !plannerForm.toml) {
      setError('Name and TOML configuration are required');
      return;
    }

    setPlannerLoading(true);
    setError(null);

    try {
      // Validate TOML first
      await api.validatePlannerToml(plannerForm.toml);

      const data = {
        name: plannerForm.name,
        toml: plannerForm.toml,
        bucket_id: plannerForm.bucket_id || null,
      };

      if (formMode === 'create') {
        await api.createPlanner(data);
        showNotification('Planner created successfully', 'success');
        await loadPlanners();
        setFormMode('none');
        setPlannerForm({ name: '', toml: '', bucket_id: '' });
      } else {
        await api.updatePlanner(selectedPlannerId, data);
        showNotification('Planner updated successfully', 'success');
        await loadPlanner(selectedPlannerId);
      }
    } catch (error) {
      const errorMsg = error.message || 'Failed to save planner';
      setError(errorMsg);
      showNotification(errorMsg, 'error');
    } finally {
      setPlannerLoading(false);
    }
  };

  const deletePlanner = async () => {
    if (!confirm('Are you sure you want to delete this planner?')) return;

    setPlannerLoading(true);
    try {
      await api.deletePlanner(selectedPlannerId);
      showNotification('Planner deleted successfully', 'success');
      await loadPlanners();
      setSelectedPlannerId('');
      setFormMode('none');
    } catch (error) {
      showNotification(`Failed to delete planner: ${error.message}`, 'error');
    } finally {
      setPlannerLoading(false);
    }
  };

  const applyPlanner = async () => {
    if (!plannerForm.bucket_id) {
      setError('Bucket must be assigned to apply planner');
      return;
    }

    setPlannerLoading(true);
    try {
      await api.applyPlanner(selectedPlannerId);
      showNotification('Planner configuration applied successfully', 'success');
    } catch (error) {
      showNotification(`Failed to apply planner: ${error.message}`, 'error');
    } finally {
      setPlannerLoading(false);
    }
  };

  const loadHistory = async () => {
    if (!selectedPlannerId) return;

    setHistoryLoading(true);
    try {
      const data = await api.fetchPlannerHistory(selectedPlannerId);
      setHistory(Array.isArray(data) ? data : (data.history || []));
      setShowHistory(true);
    } catch (error) {
      showNotification(`Failed to load history: ${error.message}`, 'error');
    } finally {
      setHistoryLoading(false);
    }
  };

  const showDiffModal = async (entry) => {
    const oldText = entry.toml || entry.config || '';
    const newText = plannerForm.toml || '';
    const oldLabel = `${entry.name || 'Previous version'} (${new Date(entry.saved_at || entry.created_at).toLocaleString()})`;
    const newLabel = 'Current version';

    const diff = computeLineDiff(oldText, newText);
    const html = renderDiffHTML(diff, oldLabel, newLabel);

    setDiffHtml(html);
    setShowDiff(true);
  };

  const restoreVersion = async (entry) => {
    if (!confirm('Restore this version? This will overwrite the current configuration.')) return;

    setPlannerLoading(true);
    try {
      setPlannerForm({
        ...plannerForm,
        toml: entry.toml || entry.config || '',
      });
      await savePlanner();
      showNotification('Version restored successfully', 'success');
    } catch (error) {
      showNotification(`Failed to restore version: ${error.message}`, 'error');
    } finally {
      setPlannerLoading(false);
    }
  };

  const plannerBuckets = (buckets || []).filter(b => b.type === 'satellite' || b.type === 'core');

  return (
    <>
      <Modal
        opened={showPlannerManagementModal}
        onClose={closePlannerManagementModal}
        title="Planner Configuration"
        size="xl"
      >
        <Stack gap="md">
          {/* Planner Selector */}
          <Group>
            <Select
              placeholder="Select a planner"
              data={planners.map(p => ({ value: String(p.id), label: p.name || `Planner ${p.id}` }))}
              value={selectedPlannerId}
              onChange={(val) => setSelectedPlannerId(val || '')}
              style={{ flex: 1 }}
              disabled={loading}
            />
            <Button onClick={startCreate} disabled={loading}>
              + Add New
            </Button>
          </Group>

          {loading && (
            <Group justify="center" p="xl">
              <Loader />
              <Text c="dimmed">Loading planners...</Text>
            </Group>
          )}

          {/* Planner Form */}
          {formMode !== 'none' && !loading && (
            <Stack gap="md">
              {/* Name Field */}
              <Text size="sm" fw={500}>Planner Name *</Text>
              <Textarea
                value={plannerForm.name}
                onChange={(e) => setPlannerForm({ ...plannerForm, name: e.currentTarget.value })}
                placeholder="e.g., Aggressive Growth Strategy"
                minRows={1}
              />

              {/* Bucket Assignment */}
              <div>
                <Text size="sm" fw={500} mb="xs">Assign to Bucket (Optional)</Text>
                <Select
                  placeholder="None (Template)"
                  data={[
                    { value: '', label: 'None (Template)' },
                    ...plannerBuckets.map(b => ({
                      value: String(b.id),
                      label: `${b.name} (${b.type})`,
                    })),
                  ]}
                  value={plannerForm.bucket_id}
                  onChange={(val) => setPlannerForm({ ...plannerForm, bucket_id: val || '' })}
                />
                <Text size="xs" c="dimmed" mt="xs">
                  {plannerForm.bucket_id
                    ? 'This planner will be used for the selected bucket'
                    : 'No bucket assigned - this is a template configuration'}
                </Text>
              </div>

              {/* TOML Configuration */}
              <div>
                <Group justify="space-between" mb="xs">
                  <Text size="sm" fw={500}>TOML Configuration *</Text>
                  <Group gap="xs">
                    {formMode === 'create' && (
                      <Select
                        placeholder="Load Template"
                        data={[
                          { value: 'conservative', label: 'Conservative Strategy' },
                          { value: 'balanced', label: 'Balanced Growth' },
                          { value: 'aggressive', label: 'Aggressive Growth' },
                        ]}
                        onChange={(val) => val && loadTemplate(val)}
                        size="xs"
                      />
                    )}
                    {formMode === 'edit' && (
                      <Button
                        size="xs"
                        variant="subtle"
                        onClick={() => {
                          if (showHistory) {
                            setShowHistory(false);
                          } else {
                            loadHistory();
                          }
                        }}
                      >
                        {showHistory ? '▼ Hide History' : '▶ View History'}
                      </Button>
                    )}
                  </Group>
                </Group>
                <Textarea
                  value={plannerForm.toml}
                  onChange={(e) => setPlannerForm({ ...plannerForm, toml: e.currentTarget.value })}
                  placeholder="# Planner configuration in TOML format&#10;# Example:&#10;[planner]&#10;name = &quot;My Strategy&quot;&#10;&#10;[[calculators]]&#10;name = &quot;momentum&quot;&#10;# ... calculator configuration"
                  minRows={20}
                  styles={{ input: { fontFamily: 'monospace', fontSize: '12px' } }}
                />
                <Text size="xs" c="dimmed" mt="xs">
                  Configure planner modules, calculators, patterns, and generators in TOML format
                </Text>
              </div>

              {/* Version History */}
              {showHistory && formMode === 'edit' && (
                <Paper p="md" withBorder>
                  <Text size="sm" fw={500} mb="md">Version History</Text>
                  {historyLoading ? (
                    <Group justify="center" p="xl">
                      <Loader size="sm" />
                      <Text size="sm" c="dimmed">Loading history...</Text>
                    </Group>
                  ) : history.length === 0 ? (
                    <Text size="sm" c="dimmed">
                      No version history yet. History is created automatically when you save changes.
                    </Text>
                  ) : (
                    <Stack gap="sm">
                      {history.map((entry) => (
                        <Paper key={entry.id} p="sm" withBorder>
                          <Group justify="space-between" mb="xs">
                            <Text size="sm" fw={500}>{entry.name || `Version ${entry.id}`}</Text>
                            <Text size="xs" c="dimmed">
                              {new Date(entry.saved_at || entry.created_at).toLocaleString()}
                            </Text>
                          </Group>
                          <Group gap="xs">
                            <Button
                              size="xs"
                              variant="subtle"
                              onClick={() => showDiffModal(entry)}
                            >
                              Compare with current
                            </Button>
                            <Button
                              size="xs"
                              variant="subtle"
                              onClick={() => restoreVersion(entry)}
                            >
                              Restore this version
                            </Button>
                          </Group>
                        </Paper>
                      ))}
                    </Stack>
                  )}
                </Paper>
              )}

              {/* Error Display */}
              {error && (
                <Alert color="red" title="Error">
                  {error}
                </Alert>
              )}
            </Stack>
          )}
        </Stack>

        {/* Footer Actions */}
        <Group justify="space-between" mt="xl" pt="md" style={{ borderTop: '1px solid var(--mantine-color-default-border)' }}>
          {formMode === 'edit' && (
            <>
              <Button
                color="red"
                variant="light"
                onClick={deletePlanner}
                disabled={plannerLoading}
              >
                Delete
              </Button>
              <Group>
                <Button
                  variant="subtle"
                  onClick={closePlannerManagementModal}
                >
                  Cancel
                </Button>
                {plannerForm.bucket_id && (
                  <Button
                    variant="light"
                    onClick={applyPlanner}
                    disabled={plannerLoading}
                    loading={plannerLoading}
                  >
                    Apply
                  </Button>
                )}
                <Button
                  onClick={savePlanner}
                  disabled={plannerLoading || !plannerForm.name || !plannerForm.toml}
                  loading={plannerLoading}
                >
                  Save
                </Button>
              </Group>
            </>
          )}

          {formMode === 'create' && (
            <Group ml="auto">
              <Button
                variant="subtle"
                onClick={closePlannerManagementModal}
              >
                Cancel
              </Button>
              <Button
                onClick={savePlanner}
                disabled={plannerLoading || !plannerForm.name || !plannerForm.toml}
                loading={plannerLoading}
              >
                Create Planner
              </Button>
            </Group>
          )}

          {formMode === 'none' && (
            <Button
              ml="auto"
              variant="subtle"
              onClick={closePlannerManagementModal}
            >
              Close
            </Button>
          )}
        </Group>
      </Modal>

      {/* Diff Viewer Modal */}
      <Modal
        opened={showDiff}
        onClose={() => setShowDiff(false)}
        title="Version Comparison"
        size="xl"
      >
        <div dangerouslySetInnerHTML={{ __html: diffHtml }} />
      </Modal>
    </>
  );
}
