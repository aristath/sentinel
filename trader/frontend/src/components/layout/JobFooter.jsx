import { Paper, Group, Button, Text, Stack } from '@mantine/core';
import { api } from '../../api/client';
import { useState } from 'react';

const jobs = [
  { id: 'sync-cycle', name: 'Sync Cycle', api: 'triggerSyncCycle' },
  { id: 'daily-pipeline', name: 'Daily Pipeline', api: 'triggerDailyPipeline' },
  { id: 'dividend-reinvestment', name: 'Dividend Reinvestment', api: 'triggerDividendReinvestment' },
];

export function JobFooter() {
  const [loading, setLoading] = useState({});
  const [messages, setMessages] = useState({});

  const triggerJob = async (job) => {
    if (loading[job.id]) return;

    setLoading((prev) => ({ ...prev, [job.id]: true }));
    setMessages((prev) => ({ ...prev, [job.id]: null }));

    try {
      const result = await api[job.api]();
      setMessages((prev) => ({
        ...prev,
        [job.id]: {
          type: result.status === 'success' ? 'success' : 'error',
          text: result.message || result.status,
        },
      }));

      setTimeout(() => {
        setMessages((prev) => {
          const next = { ...prev };
          delete next[job.id];
          return next;
        });
      }, 5000);
    } catch (error) {
      setMessages((prev) => ({
        ...prev,
        [job.id]: {
          type: 'error',
          text: error.message || 'Failed to trigger job',
        },
      }));

      setTimeout(() => {
        setMessages((prev) => {
          const next = { ...prev };
          delete next[job.id];
          return next;
        });
      }, 5000);
    } finally {
      setLoading((prev) => {
        const next = { ...prev };
        delete next[job.id];
        return next;
      });
    }
  };

  return (
    <Paper p="md" mt="xl" style={{ borderTop: '1px solid var(--mantine-color-dark-6)' }}>
      <Text size="xs" tt="uppercase" c="dimmed" fw={600} mb="md">
        Manual Job Triggers
      </Text>
      <Group gap="xs" wrap="wrap">
        {jobs.map((job) => (
          <Stack key={job.id} gap="xs" style={{ minWidth: '120px' }}>
            <Button
              size="xs"
              variant="light"
              onClick={() => triggerJob(job)}
              loading={loading[job.id]}
              fullWidth
            >
              {job.name}
            </Button>
            {messages[job.id] && (
              <Text
                size="xs"
                c={messages[job.id].type === 'success' ? 'green' : 'red'}
                ta="center"
              >
                {messages[job.id].text}
              </Text>
            )}
          </Stack>
        ))}
      </Group>
    </Paper>
  );
}

