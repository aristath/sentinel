import { Paper, Text, Stack, Group, Badge, Collapse, UnstyledButton, ScrollArea } from '@mantine/core';
import { IconChevronDown, IconChevronRight } from '@tabler/icons-react';
import { useState } from 'react';
import { formatCurrency } from '../../utils/formatters';

// Single rejected sequence item
function RejectedSequenceItem({ sequence, selectedScore }) {
  const scoreDiff = selectedScore && sequence.score ? selectedScore - sequence.score : null;

  return (
    <Paper
      p="sm"
      style={{
        border: `1px solid var(--mantine-color-${sequence.feasible ? 'dark-6' : 'red-9'})`,
        backgroundColor: 'var(--mantine-color-dark-8)',
      }}
    >
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <div style={{ flex: 1, minWidth: 0 }}>
          <Group gap="xs" mb="xs" wrap="wrap">
            <Badge size="xs" color="gray" variant="filled">
              #{sequence.rank}
            </Badge>
            {!sequence.feasible && (
              <Badge size="xs" color="red" variant="light">
                INFEASIBLE
              </Badge>
            )}
            {sequence.score !== undefined && (
              <Text size="xs" c={sequence.feasible ? 'dimmed' : 'red'}>
                Score: {sequence.score.toFixed(3)}
              </Text>
            )}
            {scoreDiff !== null && scoreDiff > 0 && (
              <Text size="xs" c="dimmed">
                (-{scoreDiff.toFixed(3)} vs selected)
              </Text>
            )}
          </Group>

          {/* Actions in the sequence */}
          {sequence.actions && sequence.actions.length > 0 && (
            <Group gap="xs" wrap="wrap">
              {sequence.actions.map((action, idx) => (
                <Badge
                  key={`${action.symbol}-${idx}`}
                  size="sm"
                  color={action.side === 'SELL' ? 'red' : 'green'}
                  variant="light"
                >
                  {action.side} {action.symbol} {action.quantity && `x${action.quantity}`}
                </Badge>
              ))}
            </Group>
          )}

          {/* Rejection reason */}
          {sequence.reason && (
            <Text size="xs" c="dimmed" mt="xs">
              {sequence.reason}
            </Text>
          )}
        </div>

        {/* Estimated value */}
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

// Main component
export function RejectedSequencesList({ sequences, selectedScore }) {
  const [expanded, setExpanded] = useState(false);

  if (!sequences || sequences.length === 0) {
    return null;
  }

  // Count feasible vs infeasible
  const feasibleCount = sequences.filter(s => s.feasible).length;
  const infeasibleCount = sequences.length - feasibleCount;

  return (
    <div style={{
      marginTop: 'var(--mantine-spacing-md)',
      borderTop: '1px solid var(--mantine-color-dark-6)',
      paddingTop: 'var(--mantine-spacing-md)',
    }}>
      <UnstyledButton onClick={() => setExpanded(!expanded)} style={{ width: '100%' }}>
        <Group justify="space-between">
          <Group gap="xs">
            {expanded ? <IconChevronDown size={16} /> : <IconChevronRight size={16} />}
            <Text size="sm" c="dimmed" fw={500}>
              Rejected Sequences ({sequences.length.toLocaleString()})
            </Text>
          </Group>
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
