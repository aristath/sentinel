import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Stack, Title, Card, Table, Text, Badge, Button, Group, Loader, Center } from '@mantine/core';
import { getSchedulerStatus, runJob } from '../api/client';

function formatTime(isoString) {
  if (!isoString) return 'Never';
  const date = new Date(isoString);
  return date.toLocaleString();
}

function SchedulerPage() {
  const queryClient = useQueryClient();

  const { data: schedulerData, isLoading, error } = useQuery({
    queryKey: ['scheduler'],
    queryFn: getSchedulerStatus,
    refetchInterval: 5000,
  });

  const runJobMutation = useMutation({
    mutationFn: runJob,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['scheduler'] });
    },
  });

  if (isLoading) {
    return (
      <Center h={200}>
        <Loader />
      </Center>
    );
  }

  if (error) {
    return (
      <Stack gap="lg">
        <Title order={2}>Scheduler</Title>
        <Card shadow="sm" padding="lg" withBorder>
          <Text c="red">Error loading scheduler status: {error.message}</Text>
        </Card>
      </Stack>
    );
  }

  const pendingJobs = schedulerData?.pending || [];
  const registeredTypes = schedulerData?.registered_types || [];

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={2}>Scheduler</Title>
        <Badge color={pendingJobs.length > 0 ? 'blue' : 'gray'} size="lg">
          {pendingJobs.length} jobs queued
        </Badge>
      </Group>

      <Card shadow="sm" padding="lg" withBorder>
        <Title order={4} mb="md">Pending Jobs</Title>
        {pendingJobs.length === 0 ? (
          <Text c="dimmed">No jobs in queue</Text>
        ) : (
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
              {pendingJobs.map((job) => (
                <Table.Tr key={job.job_id}>
                  <Table.Td>
                    <Text fw={600}>{job.job_id}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">{job.type}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">{formatTime(job.enqueued_at)}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge color={job.retry_count > 0 ? 'orange' : 'gray'} size="sm">
                      {job.retry_count}
                    </Badge>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Card>

      <Card shadow="sm" padding="lg" withBorder>
        <Title order={4} mb="md">Run Job</Title>
        <Group gap="xs" wrap="wrap">
          {registeredTypes.map((jobType) => (
            <Button
              key={jobType}
              size="sm"
              variant="light"
              disabled={runJobMutation.isPending}
              loading={runJobMutation.isPending && runJobMutation.variables === jobType}
              onClick={() => runJobMutation.mutate(jobType)}
            >
              {jobType}
            </Button>
          ))}
        </Group>
      </Card>

      {runJobMutation.isError && (
        <Card shadow="sm" padding="md" withBorder>
          <Text c="red">Error running job: {runJobMutation.error.message}</Text>
        </Card>
      )}
    </Stack>
  );
}

export default SchedulerPage;
