import { Card, Select, TextInput, NumberInput, Checkbox, Button, Group, Stack, ScrollArea, Text, Code } from '@mantine/core';
import { useLogsStore } from '../../stores/logsStore';
import { useEffect, useRef, useState } from 'react';
import { formatDateTime } from '../../utils/formatters';
import { useDebouncedValue } from '@mantine/hooks';

export function LogsViewer() {
  const {
    entries,
    selectedLogFile,
    availableLogFiles,
    filterLevel,
    searchQuery,
    lineCount,
    showErrorsOnly,
    autoRefresh,
    loading,
    totalLines,
    returnedLines,
    fetchAvailableLogFiles,
    fetchLogs,
    setSelectedLogFile,
    setFilterLevel,
    setLineCount,
    setShowErrorsOnly,
    setAutoRefresh,
    startAutoRefresh,
    stopAutoRefresh,
  } = useLogsStore();

  const [debouncedSearch] = useDebouncedValue(searchQuery, 300);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollAreaRef = useRef(null);

  useEffect(() => {
    fetchAvailableLogFiles();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    fetchLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [debouncedSearch]);

  useEffect(() => {
    if (autoRefresh) {
      startAutoRefresh();
    } else {
      stopAutoRefresh();
    }
    return () => {
      stopAutoRefresh();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh]);

  useEffect(() => {
    if (autoScroll && scrollAreaRef.current) {
      // Mantine ScrollArea exposes viewport property
      const scrollElement = scrollAreaRef.current.viewport || scrollAreaRef.current;
      if (scrollElement && typeof scrollElement.scrollTo === 'function') {
        scrollElement.scrollTo({ top: scrollElement.scrollHeight, behavior: 'smooth' });
      }
    }
  }, [entries, autoScroll]);

  const getLevelColor = (level) => {
    switch (level?.toUpperCase()) {
      case 'DEBUG': return 'dimmed';
      case 'INFO': return 'blue';
      case 'WARNING': return 'yellow';
      case 'ERROR': return 'orange';
      case 'CRITICAL': return 'red';
      default: return 'dimmed';
    }
  };

  return (
    <Card p="md">
      <Stack gap="md">
        {/* Controls */}
        <Card p="md" style={{ backgroundColor: 'var(--mantine-color-dark-7)' }}>
          <Group gap="md" wrap="wrap">
            <Select
              label="Log File"
              data={availableLogFiles.map(f => ({ value: f.name, label: f.name }))}
              value={selectedLogFile}
              onChange={setSelectedLogFile}
              style={{ flex: 1, minWidth: '150px' }}
              size="xs"
            />
            <Select
              label="Level"
              data={[
                { value: 'all', label: 'All' },
                { value: 'DEBUG', label: 'DEBUG' },
                { value: 'INFO', label: 'INFO' },
                { value: 'WARNING', label: 'WARNING' },
                { value: 'ERROR', label: 'ERROR' },
                { value: 'CRITICAL', label: 'CRITICAL' },
              ]}
              value={filterLevel || 'all'}
              onChange={setFilterLevel}
              size="xs"
              style={{ width: '120px' }}
            />
            <TextInput
              label="Search"
              placeholder="Search logs..."
              value={searchQuery}
              onChange={(e) => useLogsStore.getState().setSearchQuery(e.target.value)}
              size="xs"
              style={{ flex: 1, minWidth: '150px' }}
            />
            <NumberInput
              label="Lines"
              value={lineCount}
              onChange={(val) => setLineCount(Number(val))}
              min={50}
              max={1000}
              step={50}
              size="xs"
              style={{ width: '100px' }}
            />
            <Stack gap="xs" mt="xl">
              <Checkbox
                label="Errors Only"
                checked={showErrorsOnly}
                onChange={(e) => setShowErrorsOnly(e.currentTarget.checked)}
                size="xs"
              />
              <Checkbox
                label="Auto-refresh"
                checked={autoRefresh}
                onChange={(e) => setAutoRefresh(e.currentTarget.checked)}
                size="xs"
              />
              <Checkbox
                label="Auto-scroll"
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.currentTarget.checked)}
                size="xs"
              />
            </Stack>
          </Group>

          <Group gap="xs" mt="md">
            <Button size="xs" onClick={fetchLogs} loading={loading}>
              Refresh
            </Button>
            <Text size="xs" c="dimmed">
              {returnedLines} / {totalLines} lines
            </Text>
          </Group>
        </Card>

        {/* Log Entries */}
        <ScrollArea h={600} ref={scrollAreaRef}>
          <Code block style={{ backgroundColor: 'var(--mantine-color-dark-8)', padding: '12px' }}>
            {entries.length === 0 ? (
              <Text c="dimmed" size="sm">No log entries</Text>
            ) : (
              entries.map((entry, index) => (
                <div key={index} style={{ marginBottom: '4px' }}>
                  <Text
                    size="xs"
                    c={getLevelColor(entry.level)}
                    span
                    style={{ fontFamily: 'monospace' }}
                  >
                    [{formatDateTime(entry.timestamp)}] [{entry.level}] {entry.message}
                  </Text>
                </div>
              ))
            )}
          </Code>
        </ScrollArea>
      </Stack>
    </Card>
  );
}

