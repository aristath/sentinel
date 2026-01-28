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
import { getSchedulerStatus, getJobSchedules, runJob } from '../api/client';

function formatJobName(jobId) {
  if (!jobId) return '';
  const parts = jobId.split(':');
  return parts[parts.length - 1];
}

function formatTimeUntil(lastRun, intervalMinutes) {
  if (!lastRun || !intervalMinutes) return null;

  // lastRun is ISO datetime string, convert to timestamp
  const lastRunTs = new Date(lastRun).getTime();
  const nextRunTs = lastRunTs + intervalMinutes * 60 * 1000;
  const now = Date.now();
  const ms = nextRunTs - now;

  if (ms <= 0) return 'now';
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h`;
  return `${Math.floor(seconds / 86400)}d`;
}

export function JobsCard() {
  const [runningJob, setRunningJob] = useState(null);
  const queryClient = useQueryClient();

  const { data: jobsData } = useQuery({
    queryKey: ['jobs-status'],
    queryFn: getSchedulerStatus,
    refetchInterval: 2000,
  });

  const { data: schedulesData } = useQuery({
    queryKey: ['jobs-schedules'],
    queryFn: getJobSchedules,
    refetchInterval: 10000,
  });

  const handleRunJob = async (jobType) => {
    setRunningJob(jobType);
    try {
      await runJob(jobType, true);
      queryClient.invalidateQueries({ queryKey: ['jobs-status'] });
      queryClient.invalidateQueries({ queryKey: ['jobs-schedules'] });
    } finally {
      setRunningJob(null);
    }
  };

  const current = jobsData?.current;
  const pending = jobsData?.pending || [];
  const history = jobsData?.history || [];
  const schedules = schedulesData?.schedules || [];

  const recentCompleted = history.filter((h) => h.status === 'completed').slice(0, 3);
  const recentFailed = history.filter((h) => h.status === 'failed').slice(0, 2);

  const scheduleMap = {};
  schedules.forEach((s) => {
    if (s.enabled && s.last_run) {
      scheduleMap[s.job_type] = {
        nextIn: formatTimeUntil(s.last_run, s.interval_minutes),
      };
    }
  });

  const hasActivity = current || pending.length > 0 || recentCompleted.length > 0;

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

        {/* Pending */}
        {pending.map((job) => (
          <Tooltip key={job.job_id} label="Click to run now">
            <Badge
              size="sm"
              color="gray"
              variant="light"
              style={{ cursor: 'pointer' }}
              onClick={() => handleRunJob(job.type)}
            >
              {formatJobName(job.job_id)}
            </Badge>
          </Tooltip>
        ))}

        {/* Recent failed */}
        {recentFailed.map((job, i) => (
          <Tooltip key={`fail-${job.job_id}-${i}`} label="Click to retry">
            <Badge
              size="sm"
              color="red"
              variant="light"
              leftSection={<IconX size={10} />}
              style={{ cursor: 'pointer' }}
              onClick={() => handleRunJob(job.job_type)}
            >
              {formatJobName(job.job_id)}
            </Badge>
          </Tooltip>
        ))}

        {/* Upcoming scheduled jobs */}
        {schedules
          .filter((s) => s.enabled && !s.is_queued && scheduleMap[s.job_type]?.nextIn)
          .slice(0, 3)
          .map((s) => (
            <Tooltip key={s.job_type} label="Click to run now">
              <Badge
                size="sm"
                color="gray"
                variant="outline"
                style={{ cursor: 'pointer' }}
                onClick={() => handleRunJob(s.job_type)}
              >
                {formatJobName(s.job_type)} ({scheduleMap[s.job_type].nextIn})
              </Badge>
            </Tooltip>
          ))}

        {/* Recent completed - at the end */}
        {recentCompleted.map((job, i) => (
          <Tooltip key={`done-${job.job_id}-${i}`} label="Click to run again">
            <Badge
              size="sm"
              color="green"
              variant="light"
              leftSection={<IconCheck size={10} />}
              style={{ cursor: 'pointer' }}
              onClick={() => handleRunJob(job.job_type)}
            >
              {formatJobName(job.job_id)}
            </Badge>
          </Tooltip>
        ))}

        {!hasActivity && schedules.length === 0 && (
          <Text size="xs" c="dimmed" fs="italic">Idle</Text>
        )}
      </Group>
    </Card>
  );
}
