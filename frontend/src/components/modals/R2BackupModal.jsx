import { useState, useEffect, useCallback } from 'react';
import { Modal, Table, Button, Group, Text, Alert, ActionIcon, Tooltip, Stack, Badge, Divider } from '@mantine/core';
import { IconDownload, IconTrash, IconRefresh, IconRestore } from '@tabler/icons-react';
import { api } from '../../api/client';
import { useNotifications } from '../../hooks/useNotifications';

export function R2BackupModal({ opened, onClose }) {
  const { showNotification } = useNotifications();
  const [backups, setBackups] = useState([]);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(null); // Track which action is loading
  const [showRestoreConfirm, setShowRestoreConfirm] = useState(null); // Backup to restore

  const fetchBackups = useCallback(async () => {
    setLoading(true);
    try {
      const result = await api.listR2Backups();
      setBackups(result.backups || []);
    } catch (error) {
      showNotification(`Failed to load backups: ${error.message}`, 'error');
      setBackups([]);
    } finally {
      setLoading(false);
    }
  }, [showNotification]);

  useEffect(() => {
    if (opened) {
      fetchBackups();
    }
  }, [opened, fetchBackups]);

  const handleDownload = async (filename) => {
    setActionLoading(`download-${filename}`);
    try {
      await api.downloadR2Backup(filename);
      showNotification('Backup download started', 'success');
    } catch (error) {
      showNotification(`Failed to download backup: ${error.message}`, 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDelete = async (filename) => {
    if (!confirm(`Are you sure you want to delete backup "${filename}"? This action cannot be undone.`)) {
      return;
    }

    setActionLoading(`delete-${filename}`);
    try {
      await api.deleteR2Backup(filename);
      showNotification('Backup deleted successfully', 'success');
      fetchBackups(); // Refresh list
    } catch (error) {
      showNotification(`Failed to delete backup: ${error.message}`, 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRestoreClick = (backup) => {
    setShowRestoreConfirm(backup);
  };

  const handleRestoreConfirm = async () => {
    if (!showRestoreConfirm) return;

    const filename = showRestoreConfirm.filename;
    setActionLoading(`restore-${filename}`);

    try {
      await api.stageR2Restore(filename);
      showNotification('Restore initiated - system will restart automatically', 'success');
      setShowRestoreConfirm(null);
      onClose(); // Close modal since system is restarting
    } catch (error) {
      showNotification(`Failed to restore backup: ${error.message}`, 'error');
    } finally {
      setActionLoading(null);
    }
  };

  const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${(bytes / Math.pow(k, i)).toFixed(2)} ${sizes[i]}`;
  };

  const formatAge = (timestamp) => {
    const now = new Date();
    const backupDate = new Date(timestamp);
    const diffMs = now - backupDate;
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffDays > 0) {
      return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    }
    return `${diffHours} hour${diffHours !== 1 ? 's' : ''} ago`;
  };

  const formatTimestamp = (timestamp) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <>
      <Modal
        opened={opened}
        onClose={onClose}
        title="Cloudflare R2 Backups"
        size="xl"
      >
        <Stack gap="md">
          {!showRestoreConfirm && (
            <>
              <Group justify="space-between">
                <Text size="sm" c="dimmed">
                  {backups.length} backup{backups.length !== 1 ? 's' : ''} available
                </Text>
                <Button
                  size="xs"
                  variant="light"
                  leftSection={<IconRefresh size={16} />}
                  onClick={fetchBackups}
                  loading={loading}
                >
                  Refresh
                </Button>
              </Group>

              {backups.length === 0 && !loading && (
                <Alert color="blue">
                  <Text size="sm">No backups found. Create your first backup using the &quot;Backup Now&quot; button in Settings.</Text>
                </Alert>
              )}

              {backups.length > 0 && (
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Date</Table.Th>
                      <Table.Th>Age</Table.Th>
                      <Table.Th>Size</Table.Th>
                      <Table.Th style={{ textAlign: 'right' }}>Actions</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {backups.map((backup) => (
                      <Table.Tr key={backup.filename}>
                        <Table.Td>
                          <Text size="sm" fw={500}>{formatTimestamp(backup.timestamp)}</Text>
                          <Text size="xs" c="dimmed">{backup.filename}</Text>
                        </Table.Td>
                        <Table.Td>
                          <Badge size="sm" variant="light">
                            {formatAge(backup.timestamp)}
                          </Badge>
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm">{formatBytes(backup.size)}</Text>
                        </Table.Td>
                        <Table.Td>
                          <Group gap="xs" justify="flex-end">
                            <Tooltip label="Download backup">
                              <ActionIcon
                                variant="light"
                                color="blue"
                                onClick={() => handleDownload(backup.filename)}
                                loading={actionLoading === `download-${backup.filename}`}
                              >
                                <IconDownload size={18} />
                              </ActionIcon>
                            </Tooltip>
                            <Tooltip label="Restore backup">
                              <ActionIcon
                                variant="light"
                                color="green"
                                onClick={() => handleRestoreClick(backup)}
                                loading={actionLoading === `restore-${backup.filename}`}
                              >
                                <IconRestore size={18} />
                              </ActionIcon>
                            </Tooltip>
                            <Tooltip label="Delete backup">
                              <ActionIcon
                                variant="light"
                                color="red"
                                onClick={() => handleDelete(backup.filename)}
                                loading={actionLoading === `delete-${backup.filename}`}
                              >
                                <IconTrash size={18} />
                              </ActionIcon>
                            </Tooltip>
                          </Group>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              )}
            </>
          )}

          {showRestoreConfirm && (
            <Stack gap="md">
              <Alert color="orange" title="Confirm Restore">
                <Stack gap="sm">
                  <Text size="sm">
                    You are about to restore the following backup:
                  </Text>
                  <Text size="sm" fw={500}>
                    {showRestoreConfirm.filename}
                  </Text>
                  <Text size="sm" c="dimmed">
                    Created: {formatTimestamp(showRestoreConfirm.timestamp)}
                  </Text>
                  <Text size="sm" c="dimmed">
                    Size: {formatBytes(showRestoreConfirm.size)}
                  </Text>
                  <Divider />
                  <Text size="sm" fw={500} c="red">
                    Warning: This will replace all current databases!
                  </Text>
                  <Text size="xs" c="dimmed">
                    • Your current databases will be backed up automatically before restore
                  </Text>
                  <Text size="xs" c="dimmed">
                    • The system will restart automatically
                  </Text>
                  <Text size="xs" c="dimmed">
                    • You may lose connection briefly during restart
                  </Text>
                  <Text size="xs" c="dimmed">
                    • Pre-restore backup will be saved in case recovery is needed
                  </Text>
                </Stack>
              </Alert>

              <Group justify="flex-end" gap="sm">
                <Button
                  variant="default"
                  onClick={() => setShowRestoreConfirm(null)}
                  disabled={actionLoading}
                >
                  Cancel
                </Button>
                <Button
                  color="orange"
                  onClick={handleRestoreConfirm}
                  loading={actionLoading === `restore-${showRestoreConfirm.filename}`}
                >
                  Confirm Restore
                </Button>
              </Group>
            </Stack>
          )}
        </Stack>
      </Modal>
    </>
  );
}
