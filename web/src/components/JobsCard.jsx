/**
 * Jobs Card Component
 *
 * Compact badge-based view of job status.
 * Click any job badge to run it immediately.
 */
import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Card, Group, Text, Badge, Loader, Tooltip } from '@mantine/core';
import { IconCheck, IconX } from '@tabler/icons-react';
import { getSchedulerStatus, runJob } from '../api/client';
import { formatTimeUntil } from '../utils/dateFormatting';

function formatJobName(jobType) {
  if (!jobType) return '';
  const parts = jobType.split(':');
  return parts[parts.length - 1];
}

export function JobsCard() {
  const [runningJob, setRunningJob] = useState(null);
  const queryClient = useQueryClient();

  const { data: statusData } = useQuery({
    queryKey: ['scheduler'],
    queryFn: getSchedulerStatus,
    refetchInterval: 2000,
  });

  const handleRunJob = async (jobType) => {
    setRunningJob(jobType);
    try {
      await runJob(jobType);
      queryClient.invalidateQueries({ queryKey: ['scheduler'] });
      queryClient.invalidateQueries({ queryKey: ['jobSchedules'] });
      queryClient.invalidateQueries({ queryKey: ['jobHistory'] });
    } finally {
      setRunningJob(null);
    }
  };

  const current = statusData?.current;
  const upcoming = statusData?.upcoming || [];
  const recent = statusData?.recent || [];

  const recentCompleted = recent.filter((h) => h.status === 'completed').slice(0, 2);
  const recentFailed = recent.filter((h) => h.status === 'failed').slice(0, 2);

  const hasActivity = current || upcoming.length > 0 || recent.length > 0;

  return (
    <Card className="jobs-card" p="sm" withBorder>
      <Group gap="xs" wrap="wrap">
        <Text size="xs" c="dimmed" fw={600} tt="uppercase">Jobs</Text>

        {/* Current running */}
        {current && (
          <Badge
            size="sm"
            color="blue"
            variant="light"
            leftSection={<Loader size={10} color="blue" />}
          >
            {formatJobName(current)}
          </Badge>
        )}

        {/* User-triggered immediate run */}
        {runningJob && runningJob !== current && (
          <Badge
            size="sm"
            color="blue"
            variant="light"
            leftSection={<Loader size={10} color="blue" />}
          >
            {formatJobName(runningJob)}
          </Badge>
        )}

        {/* Upcoming jobs */}
        {upcoming.slice(0, 3).map((job, i) => {
          const timeUntil = formatTimeUntil(job.next_run);
          return (
            <Tooltip key={`upcoming-${job.job_type}-${i}`} label="Click to run now">
              <Badge
                size="sm"
                color="gray"
                variant="outline"
                style={{ cursor: 'pointer' }}
                onClick={() => handleRunJob(job.job_type)}
              >
                {formatJobName(job.job_type)}{timeUntil && ` (${timeUntil})`}
              </Badge>
            </Tooltip>
          );
        })}

        {/* Recent failed */}
        {recentFailed.map((job, i) => (
          <Tooltip key={`fail-${job.job_type}-${i}`} label="Click to retry">
            <Badge
              size="sm"
              color="red"
              variant="light"
              leftSection={<IconX size={10} />}
              style={{ cursor: 'pointer' }}
              onClick={() => handleRunJob(job.job_type)}
            >
              {formatJobName(job.job_type)}
            </Badge>
          </Tooltip>
        ))}

        {/* Recent completed - at the end */}
        {recentCompleted.map((job, i) => (
          <Tooltip key={`done-${job.job_type}-${i}`} label="Click to run again">
            <Badge
              size="sm"
              color="green"
              variant="light"
              leftSection={<IconCheck size={10} />}
              style={{ cursor: 'pointer' }}
              onClick={() => handleRunJob(job.job_type)}
            >
              {formatJobName(job.job_type)}
            </Badge>
          </Tooltip>
        ))}

        {!hasActivity && (
          <Text size="xs" c="dimmed" fs="italic">Idle</Text>
        )}
      </Group>
    </Card>
  );
}
