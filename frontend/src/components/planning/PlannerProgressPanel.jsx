import { Paper, Text, Progress, Group, Stack, Badge, ThemeIcon, Collapse, UnstyledButton } from '@mantine/core';
import { IconCheck, IconLoader, IconCircle, IconChevronDown, IconChevronRight } from '@tabler/icons-react';
import { useState } from 'react';

// Format duration in ms to human-readable string
function formatDuration(ms) {
  if (ms === null || ms === undefined) return '';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

// Stage icon based on status
function StageIcon({ status }) {
  if (status === 'completed') {
    return (
      <ThemeIcon size="xs" radius="xl" color="green" variant="filled">
        <IconCheck size={10} />
      </ThemeIcon>
    );
  }
  if (status === 'running') {
    return (
      <ThemeIcon size="xs" radius="xl" color="blue" variant="filled">
        <IconLoader size={10} className="animate-spin" />
      </ThemeIcon>
    );
  }
  return (
    <ThemeIcon size="xs" radius="xl" color="gray" variant="light">
      <IconCircle size={10} />
    </ThemeIcon>
  );
}

// Stage row in the timeline
function StageRow({ stage, isActive }) {
  return (
    <Group gap="xs" wrap="nowrap">
      <StageIcon status={stage.status} />
      <Text
        size="xs"
        c={stage.status === 'running' ? 'blue' : stage.status === 'completed' ? 'dimmed' : 'gray.6'}
        fw={isActive ? 600 : 400}
        style={{ flex: 1 }}
      >
        {stage.name}
      </Text>
      {stage.status === 'completed' && stage.duration_ms !== undefined && (
        <Text size="xs" c="dimmed">
          ({formatDuration(stage.duration_ms)})
        </Text>
      )}
    </Group>
  );
}

// Detailed metrics display
function DetailedMetrics({ details }) {
  if (!details) return null;

  const metrics = [];

  // Opportunity identification metrics
  if (details.candidates_count !== undefined) {
    metrics.push({ label: 'Candidates', value: details.candidates_count });
  }
  if (details.filtered_count !== undefined) {
    metrics.push({ label: 'Filtered', value: details.filtered_count });
  }

  // Sequence generation metrics
  if (details.sequences_generated !== undefined) {
    metrics.push({ label: 'Sequences', value: details.sequences_generated.toLocaleString() });
  }
  if (details.current_depth !== undefined) {
    metrics.push({ label: 'Depth', value: details.current_depth });
  }

  // Evaluation metrics
  if (details.workers_active !== undefined) {
    metrics.push({ label: 'Workers', value: details.workers_active });
  }
  if (details.feasible_count !== undefined) {
    metrics.push({ label: 'Feasible', value: details.feasible_count.toLocaleString(), color: 'green' });
  }
  if (details.infeasible_count !== undefined) {
    metrics.push({ label: 'Infeasible', value: details.infeasible_count.toLocaleString(), color: 'red' });
  }
  if (details.best_score !== undefined) {
    metrics.push({ label: 'Best Score', value: details.best_score.toFixed(3), color: 'blue' });
  }
  if (details.sequences_per_second !== undefined) {
    metrics.push({ label: 'Throughput', value: `${details.sequences_per_second.toFixed(0)}/s` });
  }

  if (metrics.length === 0) return null;

  return (
    <Group gap="md" mt="xs" wrap="wrap">
      {metrics.map((metric) => (
        <Text key={metric.label} size="xs" c={metric.color || 'dimmed'}>
          {metric.label}: <Text span fw={600} c={metric.color || 'dimmed'}>{metric.value}</Text>
        </Text>
      ))}
    </Group>
  );
}

// Main progress panel component
export function PlannerProgressPanel({ job, lastRun }) {
  const [expanded, setExpanded] = useState(true);

  // Determine if showing running job or last completed run
  const isRunning = !!job;
  const stages = isRunning ? job?.stages : lastRun?.stages;
  const progress = isRunning ? job?.progress : null;
  const summary = lastRun?.summary;

  // If no data, don't render
  if (!stages && !progress && !lastRun) {
    return null;
  }

  // Find the active (running) stage
  const activeStageIndex = stages?.findIndex(s => s.status === 'running') ?? -1;

  // Calculate overall progress percentage
  let overallProgress = 0;
  if (progress?.total > 0) {
    overallProgress = (progress.current / progress.total) * 100;
  } else if (stages) {
    const completed = stages.filter(s => s.status === 'completed').length;
    overallProgress = (completed / stages.length) * 100;
  }

  // Header title
  const title = isRunning
    ? 'Generating Trading Recommendations'
    : `Last Planning Run${lastRun?.status === 'failed' ? ' (Failed)' : ''}`;

  // Total duration for completed runs
  const totalDuration = lastRun?.totalDuration;

  return (
    <Paper
      p="md"
      mb="md"
      style={{
        border: `1px solid var(--mantine-color-${isRunning ? 'blue' : lastRun?.status === 'failed' ? 'red' : 'dark'}-${isRunning || lastRun?.status === 'failed' ? '4' : '6'})`,
        backgroundColor: 'var(--mantine-color-dark-7)',
      }}
    >
      <UnstyledButton onClick={() => setExpanded(!expanded)} style={{ width: '100%' }}>
        <Group justify="space-between" mb={expanded ? 'sm' : 0}>
          <Group gap="xs">
            {isRunning ? (
              <IconLoader size={16} color="var(--mantine-color-blue-5)" className="animate-spin" />
            ) : (
              <IconCheck size={16} color={lastRun?.status === 'failed' ? 'var(--mantine-color-red-5)' : 'var(--mantine-color-green-5)'} />
            )}
            <Text size="sm" fw={600} c={isRunning ? 'blue' : lastRun?.status === 'failed' ? 'red' : 'dimmed'}>
              {title}
            </Text>
          </Group>
          <Group gap="xs">
            {totalDuration && !isRunning && (
              <Badge size="sm" variant="light" color="gray">
                {formatDuration(totalDuration)}
              </Badge>
            )}
            {expanded ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
          </Group>
        </Group>
      </UnstyledButton>

      <Collapse in={expanded}>
        {/* Overall progress bar for running jobs */}
        {isRunning && progress?.total > 0 && (
          <div style={{ marginBottom: 'var(--mantine-spacing-sm)' }}>
            <Progress
              value={overallProgress}
              size="sm"
              color="blue"
              mb="xs"
            />
            <Text size="xs" c="dimmed" ta="center">
              Step {progress.current} of {progress.total}
              {progress.message && ` - ${progress.message}`}
            </Text>
          </div>
        )}

        {/* Stage timeline */}
        {stages && stages.length > 0 && (
          <Stack gap="xs" mt="xs">
            {stages.map((stage, index) => (
              <div key={stage.name}>
                <StageRow stage={stage} isActive={index === activeStageIndex} />

                {/* Show detailed metrics for the active stage */}
                {index === activeStageIndex && progress?.details && (
                  <div style={{ marginLeft: '24px', marginTop: '4px' }}>
                    {progress.phase && (
                      <Text size="xs" c="blue" mb="xs">
                        {progress.phase}
                        {progress.subPhase && ` > ${progress.subPhase}`}
                      </Text>
                    )}
                    <DetailedMetrics details={progress.details} />
                  </div>
                )}
              </div>
            ))}
          </Stack>
        )}

        {/* Summary for completed runs */}
        {!isRunning && summary && (
          <div style={{ marginTop: 'var(--mantine-spacing-sm)', borderTop: '1px solid var(--mantine-color-dark-6)', paddingTop: 'var(--mantine-spacing-sm)' }}>
            <DetailedMetrics details={summary} />
          </div>
        )}

        {/* Error message for failed runs */}
        {!isRunning && lastRun?.error && (
          <Text size="xs" c="red" mt="xs">
            Error: {lastRun.error}
          </Text>
        )}
      </Collapse>
    </Paper>
  );
}
