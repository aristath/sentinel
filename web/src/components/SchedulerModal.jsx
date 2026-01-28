import { useState, useCallback, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Modal,
  Stack,
  Text,
  Badge,
  Button,
  Loader,
  Center,
  Tabs,
  Paper,
  Group,
  Switch,
  NumberInput,
  Select,
  MultiSelect,
  Tooltip,
  Table,
  ScrollArea,
} from '@mantine/core';
import { useDebouncedCallback } from '@mantine/hooks';
import { IconClock, IconList, IconHistory, IconGitBranch, IconPlayerPlay } from '@tabler/icons-react';
import { getJobSchedules, updateJobSchedule, runJob, getSchedulerStatus, getJobHistory } from '../api/client';

function formatTime(isoString) {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  return date.toLocaleString();
}

function formatDuration(ms) {
  if (!ms) return '-';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60000).toFixed(1)}m`;
}

function JobScheduleRow({ job, onUpdate, onRun, isUpdating }) {
  // Local state for number inputs to avoid sending requests on every keystroke
  const [interval, setInterval] = useState(job.interval_minutes);
  const [intervalOpen, setIntervalOpen] = useState(job.interval_market_open_minutes || job.interval_minutes);

  // Sync local state when job prop changes (e.g., after server refresh)
  useEffect(() => {
    setInterval(job.interval_minutes);
    setIntervalOpen(job.interval_market_open_minutes || job.interval_minutes);
  }, [job.interval_minutes, job.interval_market_open_minutes]);

  // Debounced update for number inputs
  const debouncedUpdateInterval = useDebouncedCallback((val) => {
    if (val && val !== job.interval_minutes) {
      onUpdate(job.job_type, { interval_minutes: val });
    }
  }, 500);

  const debouncedUpdateIntervalOpen = useDebouncedCallback((val) => {
    if (val && val !== (job.interval_market_open_minutes || job.interval_minutes)) {
      onUpdate(job.job_type, { interval_market_open_minutes: val });
    }
  }, 500);

  return (
    <Paper p="sm" withBorder className="scheduler-modal__job-row">
      <Group justify="space-between" wrap="nowrap">
        <div style={{ flex: 1 }}>
          <Group gap="xs">
            <Switch
              checked={job.enabled}
              onChange={(e) => onUpdate(job.job_type, { enabled: e.currentTarget.checked })}
              size="sm"
              className="scheduler-modal__enable-switch"
            />
            <Text fw={500} size="sm" className="scheduler-modal__job-name">{job.job_type}</Text>
            {job.is_parameterized && (
              <Tooltip label={`Runs per ${job.parameter_field} from ${job.parameter_source}`}>
                <Badge color="violet" size="sm" variant="light">
                  x{job.instance_count ?? '?'}
                </Badge>
              </Tooltip>
            )}
            {job.is_queued && <Badge color="blue" size="sm">Queued</Badge>}
            {job.last_status && (
              <Badge color={job.last_status === 'completed' ? 'green' : 'red'} size="sm">
                {job.last_status}
              </Badge>
            )}
          </Group>
          <Text size="xs" c="dimmed" className="scheduler-modal__job-desc">
            {job.description}
          </Text>
        </div>

        <Group gap="xs" wrap="nowrap">
          <NumberInput
            label="Interval"
            value={interval}
            onChange={(val) => {
              setInterval(val);
              debouncedUpdateInterval(val);
            }}
            min={1}
            max={10080}
            w={80}
            size="xs"
            suffix="m"
          />
          <NumberInput
            label="Open"
            value={intervalOpen}
            onChange={(val) => {
              setIntervalOpen(val);
              debouncedUpdateIntervalOpen(val);
            }}
            min={1}
            max={10080}
            w={80}
            size="xs"
            suffix="m"
          />
          <Select
            label="Timing"
            value={String(job.market_timing)}
            onChange={(val) => onUpdate(job.job_type, { market_timing: parseInt(val) })}
            data={[
              { value: '0', label: 'Any time' },
              { value: '1', label: 'After close' },
              { value: '2', label: 'During open' },
              { value: '3', label: 'All closed' },
            ]}
            w={110}
            size="xs"
          />
          <Button
            size="xs"
            variant="light"
            onClick={() => onRun(job.job_type)}
            disabled={job.is_queued || job.is_parameterized || isUpdating}
            title={job.is_parameterized ? 'Parameterized jobs run automatically' : undefined}
            leftSection={<IconPlayerPlay size={14} />}
            className="scheduler-modal__run-btn"
          >
            Run
          </Button>
        </Group>
      </Group>
    </Paper>
  );
}

function JobScheduleList({ schedules, onUpdate, onRun, isUpdating }) {
  const categories = ['sync', 'scoring', 'analytics', 'trading', 'ml'];

  return (
    <Stack gap="lg">
      {categories.map(cat => {
        const jobs = schedules.filter(s => s.category === cat);
        if (jobs.length === 0) return null;

        return (
          <div key={cat}>
            <Text fw={600} tt="capitalize" mb="sm" c="dimmed" size="sm">
              {cat}
            </Text>
            <Stack gap="xs">
              {jobs.map(job => (
                <JobScheduleRow
                  key={job.job_type}
                  job={job}
                  onUpdate={onUpdate}
                  onRun={onRun}
                  isUpdating={isUpdating}
                />
              ))}
            </Stack>
          </div>
        );
      })}
    </Stack>
  );
}

function PendingJobsList({ jobs }) {
  if (!jobs || jobs.length === 0) {
    return <Text c="dimmed" ta="center" py="xl">No jobs in queue</Text>;
  }

  return (
    <Table striped highlightOnHover>
      <Table.Thead>
        <Table.Tr>
          <Table.Th>Job ID</Table.Th>
          <Table.Th>Type</Table.Th>
          <Table.Th>Enqueued</Table.Th>
          <Table.Th>Retries</Table.Th>
        </Table.Tr>
      </Table.Thead>
      <Table.Tbody>
        {jobs.map((job, i) => (
          <Table.Tr key={job.job_id || i}>
            <Table.Td><Text size="sm" fw={500}>{job.job_id}</Text></Table.Td>
            <Table.Td><Text size="sm" c="dimmed">{job.type}</Text></Table.Td>
            <Table.Td><Text size="sm" c="dimmed">{formatTime(job.enqueued_at)}</Text></Table.Td>
            <Table.Td><Badge color={job.retry_count > 0 ? 'orange' : 'gray'} size="sm">{job.retry_count}</Badge></Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function JobHistoryList({ history }) {
  if (!history || history.length === 0) {
    return <Text c="dimmed" ta="center" py="xl">No execution history</Text>;
  }

  return (
    <ScrollArea h={400}>
      <Table striped highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Job ID</Table.Th>
            <Table.Th>Status</Table.Th>
            <Table.Th>Duration</Table.Th>
            <Table.Th>Executed</Table.Th>
            <Table.Th>Error</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {history.map((entry, i) => (
            <Table.Tr key={entry.job_id + entry.executed_at || i}>
              <Table.Td><Text size="sm" fw={500}>{entry.job_id}</Text></Table.Td>
              <Table.Td>
                <Badge color={entry.status === 'completed' ? 'green' : 'red'} size="sm">
                  {entry.status}
                </Badge>
              </Table.Td>
              <Table.Td><Text size="sm" c="dimmed">{formatDuration(entry.duration_ms)}</Text></Table.Td>
              <Table.Td>
                <Text size="sm" c="dimmed">
                  {entry.executed_at ? formatTime(new Date(entry.executed_at * 1000).toISOString()) : '-'}
                </Text>
              </Table.Td>
              <Table.Td>
                {entry.error && (
                  <Tooltip label={entry.error} multiline w={300}>
                    <Text size="sm" c="red" truncate maw={200}>{entry.error}</Text>
                  </Tooltip>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </ScrollArea>
  );
}

function JobDependenciesList({ schedules, onUpdate }) {
  // Build options list (all job types)
  const allJobTypes = schedules.map(s => ({
    value: s.job_type,
    label: s.job_type,
  }));

  const categories = ['sync', 'scoring', 'analytics', 'trading', 'ml'];

  return (
    <ScrollArea h={400}>
      <Stack gap="md">
        {categories.map(cat => {
          const jobs = schedules.filter(s => s.category === cat);
          if (jobs.length === 0) return null;

          return (
            <div key={cat}>
              <Text fw={600} tt="capitalize" mb="xs" c="dimmed" size="sm">
                {cat}
              </Text>
              <Stack gap="xs">
                {jobs.map(job => {
                  // Options exclude the job itself
                  const options = allJobTypes.filter(o => o.value !== job.job_type);
                  const currentDeps = Array.isArray(job.dependencies) ? job.dependencies : [];

                  return (
                    <Paper key={job.job_type} p="sm" withBorder>
                      <Group justify="space-between" align="flex-start">
                        <div style={{ flex: '0 0 200px' }}>
                          <Text size="sm" fw={500}>{job.job_type}</Text>
                          <Text size="xs" c="dimmed">{job.description}</Text>
                        </div>
                        <MultiSelect
                          placeholder="No dependencies"
                          data={options}
                          value={currentDeps}
                          onChange={(deps) => onUpdate(job.job_type, deps)}
                          clearable
                          searchable
                          size="xs"
                          style={{ flex: 1 }}
                        />
                      </Group>
                    </Paper>
                  );
                })}
              </Stack>
            </div>
          );
        })}
      </Stack>
    </ScrollArea>
  );
}

export function SchedulerModal({ opened, onClose }) {
  const queryClient = useQueryClient();

  // Fetch job schedules
  const { data: schedulesData, isLoading: loadingSchedules, error: schedulesError } = useQuery({
    queryKey: ['jobSchedules'],
    queryFn: getJobSchedules,
    refetchInterval: opened ? 5000 : false,
    enabled: opened,
  });

  // Fetch queue status
  const { data: statusData, isLoading: loadingStatus } = useQuery({
    queryKey: ['scheduler'],
    queryFn: getSchedulerStatus,
    refetchInterval: opened ? 5000 : false,
    enabled: opened,
  });

  // Fetch job history
  const { data: historyData, isLoading: loadingHistory } = useQuery({
    queryKey: ['jobHistory'],
    queryFn: () => getJobHistory(null, 100),
    refetchInterval: opened ? 10000 : false,
    enabled: opened,
  });

  // Update schedule mutation
  const updateMutation = useMutation({
    mutationFn: ({ jobType, data }) => updateJobSchedule(jobType, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['jobSchedules'] });
    },
  });

  // Run job mutation
  const runJobMutation = useMutation({
    mutationFn: runJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler'] });
      queryClient.invalidateQueries({ queryKey: ['jobSchedules'] });
    },
  });

  const handleUpdate = (jobType, data) => {
    updateMutation.mutate({ jobType, data });
  };

  const handleRun = (jobType) => {
    runJobMutation.mutate(jobType);
  };

  const schedules = schedulesData?.schedules || [];
  const pendingJobs = statusData?.pending || [];
  const history = historyData?.history || [];
  const queueLength = pendingJobs.length;

  const isLoading = loadingSchedules || loadingStatus || loadingHistory;

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Text fw={600} className="scheduler-modal__title">
          Job Scheduler
          {queueLength > 0 && (
            <Badge color="blue" size="sm" ml="sm">
              {queueLength} queued
            </Badge>
          )}
        </Text>
      }
      size="xl"
      className="scheduler-modal"
    >
      {isLoading ? (
        <Center h={300}>
          <Loader />
        </Center>
      ) : schedulesError ? (
        <Text c="red">Error loading schedules: {schedulesError.message}</Text>
      ) : (
        <Tabs defaultValue="jobs">
          <Tabs.List>
            <Tabs.Tab value="jobs" leftSection={<IconClock size={16} />}>
              Jobs
            </Tabs.Tab>
            <Tabs.Tab value="queue" leftSection={<IconList size={16} />}>
              Queue ({queueLength})
            </Tabs.Tab>
            <Tabs.Tab value="history" leftSection={<IconHistory size={16} />}>
              History
            </Tabs.Tab>
            <Tabs.Tab value="dependencies" leftSection={<IconGitBranch size={16} />}>
              Dependencies
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="jobs" pt="md">
            <JobScheduleList
              schedules={schedules}
              onUpdate={handleUpdate}
              onRun={handleRun}
              isUpdating={updateMutation.isPending}
            />
            {updateMutation.isError && (
              <Text c="red" size="sm" mt="md">
                Error updating schedule: {updateMutation.error.message}
              </Text>
            )}
            {runJobMutation.isError && (
              <Text c="red" size="sm" mt="md">
                Error running job: {runJobMutation.error.message}
              </Text>
            )}
          </Tabs.Panel>

          <Tabs.Panel value="queue" pt="md">
            <PendingJobsList jobs={pendingJobs} />
          </Tabs.Panel>

          <Tabs.Panel value="history" pt="md">
            <JobHistoryList history={history} />
          </Tabs.Panel>

          <Tabs.Panel value="dependencies" pt="md">
            <Text size="sm" c="dimmed" mb="md">
              Select which jobs must complete before each job can run.
            </Text>
            <JobDependenciesList
              schedules={schedules}
              onUpdate={(jobType, deps) =>
                updateMutation.mutate({
                  jobType,
                  data: { dependencies: deps },
                })
              }
            />
          </Tabs.Panel>
        </Tabs>
      )}
    </Modal>
  );
}
