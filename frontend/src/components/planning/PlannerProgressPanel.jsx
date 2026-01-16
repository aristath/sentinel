/**
 * Planner Progress Panel Component
 *
 * Displays the progress of planner batch job execution, including:
 * - Overall progress bar for running jobs
 * - Stage timeline showing execution stages (opportunity identification, sequence generation, evaluation, etc.)
 * - Detailed metrics for the active stage (candidates, sequences, throughput, etc.)
 * - Summary metrics for completed runs
 * - Error messages for failed runs
 *
 * The component can display either:
 * - A currently running job (with live progress updates)
 * - The last completed run (for debugging and review)
 */
import { Paper, Text, Progress, Group, Stack, Badge, ThemeIcon, Collapse, UnstyledButton } from '@mantine/core';
import { IconCheck, IconLoader, IconCircle, IconChevronDown, IconChevronRight } from '@tabler/icons-react';
import { useState } from 'react';

/**
 * Formats a duration in milliseconds to a human-readable string
 *
 * Formats as:
 * - Milliseconds if < 1 second
 * - Seconds with 1 decimal if < 1 minute
 * - Minutes and seconds if >= 1 minute
 *
 * @param {number|null|undefined} ms - Duration in milliseconds
 * @returns {string} Formatted duration string (e.g., "1.5s", "2m 30s") or empty string
 */
function formatDuration(ms) {
  if (ms === null || ms === undefined) return '';
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

/**
 * Stage icon component - displays icon based on stage status
 *
 * @param {Object} props - Component props
 * @param {string} props.status - Stage status: 'completed', 'running', or 'pending'
 * @returns {JSX.Element} ThemeIcon with appropriate icon and color
 */
function StageIcon({ status }) {
  if (status === 'completed') {
    // Green checkmark for completed stages
    return (
      <ThemeIcon size="xs" radius="xl" color="green" variant="filled">
        <IconCheck size={10} />
      </ThemeIcon>
    );
  }
  if (status === 'running') {
    // Blue spinning loader for active stages
    return (
      <ThemeIcon size="xs" radius="xl" color="blue" variant="filled">
        <IconLoader size={10} className="animate-spin" />
      </ThemeIcon>
    );
  }
  // Gray circle for pending stages
  return (
    <ThemeIcon size="xs" radius="xl" color="gray" variant="light">
      <IconCircle size={10} />
    </ThemeIcon>
  );
}

/**
 * Stage row component - displays a single stage in the timeline
 *
 * Shows stage name, status icon, and duration (if completed).
 * Highlights the active (running) stage.
 *
 * @param {Object} props - Component props
 * @param {Object} props.stage - Stage object with name, status, duration_ms
 * @param {boolean} props.isActive - Whether this is the currently active stage
 * @returns {JSX.Element} Stage row with icon, name, and duration
 */
function StageRow({ stage, isActive }) {
  return (
    <Group gap="xs" wrap="nowrap">
      <StageIcon status={stage.status} />
      <Text
        size="xs"
        c={stage.status === 'running' ? 'blue' : stage.status === 'completed' ? 'dimmed' : 'gray.6'}
        fw={isActive ? 600 : 400}  // Bold for active stage
        style={{ flex: 1 }}
      >
        {stage.name}
      </Text>
      {/* Show duration for completed stages */}
      {stage.status === 'completed' && stage.duration_ms !== undefined && (
        <Text size="xs" c="dimmed">
          ({formatDuration(stage.duration_ms)})
        </Text>
      )}
    </Group>
  );
}

/**
 * Detailed metrics display component
 *
 * Displays various metrics from the progress details object:
 * - Opportunity identification: candidates_count, filtered_count
 * - Sequence generation: sequences_generated, current_depth
 * - Evaluation: workers_active, feasible_count, infeasible_count, best_score, sequences_per_second
 *
 * @param {Object} props - Component props
 * @param {Object} props.details - Progress details object with various metrics
 * @returns {JSX.Element|null} Metrics display or null if no metrics available
 */
function DetailedMetrics({ details }) {
  if (!details) return null;

  const metrics = [];

  // Opportunity identification metrics
  // Number of securities identified as opportunities and filtered count
  if (details.candidates_count !== undefined) {
    metrics.push({ label: 'Candidates', value: details.candidates_count });
  }
  if (details.filtered_count !== undefined) {
    metrics.push({ label: 'Filtered', value: details.filtered_count });
  }

  // Sequence generation metrics
  // Total sequences generated and current search depth
  if (details.sequences_generated !== undefined) {
    metrics.push({ label: 'Sequences', value: details.sequences_generated.toLocaleString() });
  }
  if (details.current_depth !== undefined) {
    metrics.push({ label: 'Depth', value: details.current_depth });
  }

  // Evaluation metrics
  // Worker pool status and evaluation results
  if (details.workers_active !== undefined) {
    metrics.push({ label: 'Workers', value: details.workers_active });
  }
  // Feasible sequences (pass constraints) - green for positive
  if (details.feasible_count !== undefined) {
    metrics.push({ label: 'Feasible', value: details.feasible_count.toLocaleString(), color: 'green' });
  }
  // Infeasible sequences (fail constraints) - red for negative
  if (details.infeasible_count !== undefined) {
    metrics.push({ label: 'Infeasible', value: details.infeasible_count.toLocaleString(), color: 'red' });
  }
  // Best score found so far - blue for highlight
  if (details.best_score !== undefined) {
    metrics.push({ label: 'Best Score', value: details.best_score.toFixed(3), color: 'blue' });
  }
  // Evaluation throughput (sequences per second)
  if (details.sequences_per_second !== undefined) {
    metrics.push({ label: 'Throughput', value: `${details.sequences_per_second.toFixed(0)}/s` });
  }

  if (metrics.length === 0) return null;

  // Render metrics as a horizontal list
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

/**
 * Main planner progress panel component
 *
 * Displays planner batch job execution progress with:
 * - Collapsible panel (expandable/collapsible)
 * - Overall progress bar for running jobs
 * - Stage timeline with status icons
 * - Detailed metrics for active stage
 * - Summary metrics for completed runs
 * - Error messages for failed runs
 *
 * @param {Object} props - Component props
 * @param {Object|null} props.job - Currently running job object (null if no job running)
 * @param {Object|null} props.lastRun - Last completed run object (for debugging/review)
 * @returns {JSX.Element|null} Progress panel component or null if no data
 */
export function PlannerProgressPanel({ job, lastRun }) {
  const [expanded, setExpanded] = useState(true);  // Panel starts expanded

  // Determine if showing running job or last completed run
  const isRunning = !!job;
  const stages = isRunning ? job?.stages : lastRun?.stages;
  const progress = isRunning ? job?.progress : null;
  const summary = lastRun?.summary;

  // If no data, don't render
  if (!stages && !progress && !lastRun) {
    return null;
  }

  // Find the active (running) stage index for highlighting
  const activeStageIndex = stages?.findIndex(s => s.status === 'running') ?? -1;

  // Calculate overall progress percentage
  // Uses progress.current/total if available, otherwise uses completed stages count
  let overallProgress = 0;
  if (progress?.total > 0) {
    overallProgress = (progress.current / progress.total) * 100;
  } else if (stages) {
    const completed = stages.filter(s => s.status === 'completed').length;
    overallProgress = (completed / stages.length) * 100;
  }

  // Header title - different for running vs completed
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
      {/* Collapsible header - click to expand/collapse */}
      <UnstyledButton onClick={() => setExpanded(!expanded)} style={{ width: '100%' }}>
        <Group justify="space-between" mb={expanded ? 'sm' : 0}>
          <Group gap="xs">
            {/* Status icon: spinning loader for running, checkmark for completed/failed */}
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
            {/* Show total duration badge for completed runs */}
            {totalDuration && !isRunning && (
              <Badge size="sm" variant="light" color="gray">
                {formatDuration(totalDuration)}
              </Badge>
            )}
            {/* Chevron icon indicates expand/collapse state */}
            {expanded ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
          </Group>
        </Group>
      </UnstyledButton>

      {/* Collapsible content */}
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

        {/* Stage timeline - shows all execution stages with status */}
        {stages && stages.length > 0 && (
          <Stack gap="xs" mt="xs">
            {stages.map((stage, index) => (
              <div key={stage.name}>
                <StageRow stage={stage} isActive={index === activeStageIndex} />

                {/* Show detailed metrics for the active (running) stage */}
                {index === activeStageIndex && progress?.details && (
                  <div style={{ marginLeft: '24px', marginTop: '4px' }}>
                    {/* Show phase and sub-phase if available */}
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

        {/* Summary metrics for completed runs */}
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
