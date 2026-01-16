/**
 * Rejected Sequences List Component
 *
 * Displays a collapsible list of trade sequences that were rejected during planner evaluation.
 * Shows sequences that were either:
 * - Infeasible (failed constraints)
 * - Feasible but had lower scores than the selected sequence
 *
 * Features:
 * - Collapsible list (starts collapsed)
 * - Counts of feasible vs infeasible sequences
 * - Individual sequence details (rank, score, actions, rejection reason)
 * - Score comparison with selected sequence
 * - Estimated value calculation
 */
import { Paper, Text, Stack, Group, Badge, Collapse, UnstyledButton, ScrollArea } from '@mantine/core';
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react';
import { useState } from 'react';
import { formatCurrency } from '../../utils/formatters';

/**
 * Single rejected sequence item component
 *
 * Displays details for one rejected sequence:
 * - Rank, feasibility status, score
 * - Trade actions (BUY/SELL with symbols and quantities)
 * - Rejection reason
 * - Estimated value
 * - Score difference vs selected sequence
 *
 * @param {Object} props - Component props
 * @param {Object} props.sequence - Sequence object with rank, score, feasible, actions, reason
 * @param {number|null} props.selectedScore - Score of the selected sequence (for comparison)
 * @returns {JSX.Element} Sequence item card
 */
function RejectedSequenceItem({ sequence, selectedScore }) {
  // Calculate score difference vs selected sequence (if available)
  const scoreDiff = selectedScore && sequence.score ? selectedScore - sequence.score : null;

  return (
    <Paper
      p="sm"
      style={{
        // Red border for infeasible sequences, dark border for feasible but rejected
        border: `1px solid var(--mantine-color-${sequence.feasible ? 'dark-6' : 'red-9'})`,
        backgroundColor: 'var(--mantine-color-dark-8)',
      }}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Header: rank, feasibility badge, score, score difference */}
          <Group gap="xs" mb="xs" wrap="wrap">
            <Badge size="xs" color="gray" variant="filled">
              #{sequence.rank}
            </Badge>
            {/* Show infeasible badge if sequence failed constraints */}
            {!sequence.feasible && (
              <Badge size="xs" color="red" variant="light">
                INFEASIBLE
              </Badge>
            )}
            {/* Score display - red for infeasible, dimmed for feasible */}
            {sequence.score !== undefined && (
              <Text size="xs" c={sequence.feasible ? 'dimmed' : 'red'}>
                Score: {sequence.score.toFixed(3)}
              </Text>
            )}
            {/* Show score difference vs selected sequence */}
            {scoreDiff !== null && scoreDiff > 0 && (
              <Text size="xs" c="dimmed">
                (-{scoreDiff.toFixed(3)} vs selected)
              </Text>
            )}
          </Group>

          {/* Trade actions in the sequence (BUY/SELL badges) */}
          {sequence.actions && sequence.actions.length > 0 && (
            <Group gap="xs" wrap="wrap">
              {sequence.actions.map((action, idx) => (
                <Badge
                  key={`${action.symbol}-${idx}`}
                  size="sm"
                  color={action.side === 'SELL' ? 'red' : 'green'}  // Red for SELL, green for BUY
                  variant="light"
                >
                  {action.side} {action.symbol} {action.quantity && `x${action.quantity}`}
                </Badge>
              ))}
            </Group>
          )}

          {/* Rejection reason (why this sequence was rejected) */}
          {sequence.reason && (
            <Text size="xs" c="dimmed" mt="xs">
              {sequence.reason}
            </Text>
          )}
        </div>

        {/* Estimated total value of all actions in the sequence */}
        {sequence.actions && sequence.actions.length > 0 && (
          <Text size="xs" c="dimmed" style={{ flexShrink: 0 }}>
            {sequence.actions.reduce((sum, a) => sum + (a.estimated_value || 0), 0) > 0 &&
              formatCurrency(sequence.actions.reduce((sum, a) => sum + (a.estimated_value || 0), 0))}
          </Text>
        )}
      </Group>
    </Paper>
  );
}

/**
 * Main rejected sequences list component
 *
 * Displays a collapsible list of rejected trade sequences with:
 * - Header showing total count and breakdown (feasible vs infeasible)
 * - Scrollable list of sequence items
 * - Each item shows rank, score, actions, and rejection reason
 *
 * @param {Object} props - Component props
 * @param {Array<Object>|null} props.sequences - Array of rejected sequence objects
 * @param {number|null} props.selectedScore - Score of the selected sequence (for comparison)
 * @returns {JSX.Element|null} Rejected sequences list or null if no sequences
 */
export function RejectedSequencesList({ sequences, selectedScore }) {
  const [expanded, setExpanded] = useState(false);  // Starts collapsed

  // Don't render if no sequences
  if (!sequences || sequences.length === 0) {
    return null;
  }

  // Count feasible vs infeasible sequences for summary badges
  const feasibleCount = sequences.filter(s => s.feasible).length;
  const infeasibleCount = sequences.length - feasibleCount;

  return (
    <div style={{
      marginTop: 'var(--mantine-spacing-md)',
      borderTop: '1px solid var(--mantine-color-dark-6)',
      paddingTop: 'var(--mantine-spacing-md)',
    }}>
      {/* Collapsible header with counts */}
      <UnstyledButton onClick={() => setExpanded(!expanded)} style={{ width: '100%' }}>
        <Group justify="space-between">
          <Group gap="xs">
            {/* Chevron icon indicates expand/collapse state */}
            {expanded ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
            <Text size="sm" c="dimmed" fw={500}>
              Rejected Sequences ({sequences.length.toLocaleString()})
            </Text>
          </Group>
          {/* Summary badges: feasible vs infeasible counts */}
          <Group gap="xs">
            {feasibleCount > 0 && (
              <Badge size="xs" color="gray" variant="light">
                {feasibleCount.toLocaleString()} feasible
              </Badge>
            )}
            {infeasibleCount > 0 && (
              <Badge size="xs" color="red" variant="light">
                {infeasibleCount.toLocaleString()} infeasible
              </Badge>
            )}
          </Group>
        </Group>
      </UnstyledButton>

      {/* Collapsible content: scrollable list of rejected sequences */}
      <Collapse in={expanded}>
        <ScrollArea.Autosize mah={500} mt="sm">
          <Stack gap="xs">
            {sequences.map((sequence, index) => (
              <RejectedSequenceItem
                key={`rejected-seq-${sequence.rank || index}`}
                sequence={sequence}
                selectedScore={selectedScore}
              />
            ))}
          </Stack>
        </ScrollArea.Autosize>
      </Collapse>
    </div>
  );
}
