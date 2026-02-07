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
  Select,
  Tooltip,
  Table,
  ScrollArea,
} from '@mantine/core';
import { useDebouncedCallback } from '@mantine/hooks';
import { IconClock, IconActivity, IconHistory, IconPlayerPlay } from '@tabler/icons-react';
import { getJobSchedules, updateJobSchedule, runJob, getSchedulerStatus, getJobHistory } from '../api/client';
import { IntervalPicker } from './IntervalPicker';
import { formatTime, formatRelativeTime, formatDuration } from '../utils/dateFormatting';

function JobScheduleRow({ job, onUpdate, onRun, isUpdating }) {
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
      <Stack gap="xs">
        <Group justify="space-between" wrap="nowrap">
          <Group gap="xs">
            <Text fw={500} size="sm" className="scheduler-modal__job-name">{job.job_type}</Text>
            {job.last_status && (
              <Badge color={job.last_status === 'completed' ? 'green' : 'red'} size="sm">
                {job.last_status}
              </Badge>
            )}
          </Group>
          <Group gap="xs" wrap="nowrap">
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
              disabled={isUpdating}
              leftSection={<IconPlayerPlay size={14} />}
              className="scheduler-modal__run-btn"
            >
              Run
            </Button>
          </Group>
        </Group>
        <Text size="xs" c="dimmed" className="scheduler-modal__job-desc">
          {job.description}
        </Text>
        <Group gap="lg">
          <IntervalPicker
            label="Interval"
            value={job.interval_minutes}
            onChange={debouncedUpdateInterval}
          />
          <IntervalPicker
            label="Market open"
            value={job.interval_market_open_minutes || job.interval_minutes}
            onChange={debouncedUpdateIntervalOpen}
          />
          {job.next_run && (
            <Text size="xs" c="dimmed">
              Next: {formatRelativeTime(job.next_run)}
            </Text>
          )}
        </Group>
      </Stack>
    </Paper>
  );
}

function JobScheduleList({ schedules, onUpdate, onRun, isUpdating }) {
  const categories = [...new Set(schedules.map((s) => s.category).filter(Boolean))];

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

function StatusPanel({ status }) {
  const { current, upcoming, recent } = status || {};

  return (
    <Stack gap="lg">
      {/* Currently Running */}
      <Paper p="md" withBorder>
        <Text fw={600} size="sm" mb="xs">Currently Running</Text>
        {current ? (
          <Group gap="sm">
            <Loader size="sm" />
            <Text size="sm">{current}</Text>
          </Group>
        ) : (
          <Text size="sm" c="dimmed">No job running</Text>
        )}
      </Paper>

      {/* Upcoming Jobs */}
      <Paper p="md" withBorder>
        <Text fw={600} size="sm" mb="xs">Upcoming Jobs</Text>
        {upcoming && upcoming.length > 0 ? (
          <Stack gap="xs">
            {upcoming.map((job, i) => (
              <Group key={i} justify="space-between">
                <Text size="sm">{job.job_type}</Text>
                <Text size="sm" c="dimmed">{formatRelativeTime(job.next_run)}</Text>
              </Group>
            ))}
          </Stack>
        ) : (
          <Text size="sm" c="dimmed">No upcoming jobs</Text>
        )}
      </Paper>

      {/* Recent Jobs */}
      <Paper p="md" withBorder>
        <Text fw={600} size="sm" mb="xs">Recent Jobs</Text>
        {recent && recent.length > 0 ? (
          <Stack gap="xs">
            {recent.map((job, i) => (
              <Group key={i} justify="space-between">
                <Group gap="xs">
                  <Text size="sm">{job.job_type}</Text>
                  <Badge
                    color={job.status === 'completed' ? 'green' : 'red'}
                    size="sm"
                    variant="light"
                  >
                    {job.status}
                  </Badge>
                </Group>
                <Text size="sm" c="dimmed">{formatRelativeTime(job.executed_at)}</Text>
              </Group>
            ))}
          </Stack>
        ) : (
          <Text size="sm" c="dimmed">No recent jobs</Text>
        )}
      </Paper>
    </Stack>
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

export function SchedulerModal({ opened, onClose }) {
  const queryClient = useQueryClient();

  // Fetch job schedules
  const { data: schedulesData, isLoading: loadingSchedules, error: schedulesError } = useQuery({
    queryKey: ['jobSchedules'],
    queryFn: getJobSchedules,
    refetchInterval: opened ? 5000 : false,
    enabled: opened,
  });

  // Fetch scheduler status (current, upcoming, recent)
  const { data: statusData, isLoading: loadingStatus } = useQuery({
    queryKey: ['scheduler'],
    queryFn: getSchedulerStatus,
    refetchInterval: opened ? 3000 : false,
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
      queryClient.invalidateQueries({ queryKey: ['jobHistory'] });
    },
  });

  const handleUpdate = (jobType, data) => {
    updateMutation.mutate({ jobType, data });
  };

  const handleRun = (jobType) => {
    runJobMutation.mutate(jobType);
  };

  const schedules = schedulesData?.schedules || [];
  const history = historyData?.history || [];
  const currentJob = statusData?.current;

  const isLoading = loadingSchedules || loadingStatus || loadingHistory;

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap="sm">
          <Text fw={600} className="scheduler-modal__title">
            Job Scheduler
          </Text>
          {currentJob && (
            <Badge color="blue" size="sm" leftSection={<Loader size={10} color="white" />}>
              {currentJob}
            </Badge>
          )}
        </Group>
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
        <Tabs defaultValue="status">
          <Tabs.List>
            <Tabs.Tab value="status" leftSection={<IconActivity size={16} />}>
              Status
            </Tabs.Tab>
            <Tabs.Tab value="jobs" leftSection={<IconClock size={16} />}>
              Jobs
            </Tabs.Tab>
            <Tabs.Tab value="history" leftSection={<IconHistory size={16} />}>
              History
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="status" pt="md">
            <StatusPanel status={statusData} />
          </Tabs.Panel>

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

          <Tabs.Panel value="history" pt="md">
            <JobHistoryList history={history} />
          </Tabs.Panel>
        </Tabs>
      )}
    </Modal>
  );
}
