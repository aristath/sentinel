/**
 * Security Table Component
 *
 * Compact table view of securities showing key metrics with
 * expandable rows for detailed information and settings.
 * All columns are sortable.
 */
import { useState, useMemo } from 'react';
import {
  Table,
  Text,
  Badge,
  Group,
  ActionIcon,
  Tooltip,
  Box,
  UnstyledButton,
} from '@mantine/core';
import { IconAlertTriangle, IconChevronUp, IconChevronDown, IconSelector, IconChevronRight } from '@tabler/icons-react';
import { SecurityExpandedRow } from './SecurityExpandedRow';
import { formatCurrencySymbol as formatCurrency, formatPercent } from '../utils/formatting';

// Sortable column header component
function SortableHeader({ children, sorted, reversed, onSort }) {
  const Icon = sorted ? (reversed ? IconChevronUp : IconChevronDown) : IconSelector;
  return (
    <UnstyledButton onClick={onSort} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <Text fw={600} size="sm">{children}</Text>
      <Icon size={14} style={{ opacity: sorted ? 1 : 0.5 }} />
    </UnstyledButton>
  );
}

export function SecurityTable({ securities, onUpdate, onDelete }) {
  const [expandedSymbols, setExpandedSymbols] = useState(new Set());
  const [sortColumn, setSortColumn] = useState(null);
  const [sortReversed, setSortReversed] = useState(false);

  const toggleExpanded = (symbol) => {
    setExpandedSymbols((prev) => {
      const next = new Set(prev);
      if (next.has(symbol)) {
        next.delete(symbol);
      } else {
        next.add(symbol);
      }
      return next;
    });
  };

  const handleSort = (column) => {
    if (sortColumn === column) {
      setSortReversed(!sortReversed);
    } else {
      setSortColumn(column);
      setSortReversed(false);
    }
  };

  // Sort securities based on current sort state
  const sortedSecurities = useMemo(() => {
    if (!sortColumn) return securities;

    const sorted = [...securities].sort((a, b) => {
      let aVal, bVal;

      switch (sortColumn) {
        case 'symbol':
          aVal = a.symbol || '';
          bVal = b.symbol || '';
          return aVal.localeCompare(bVal);
        case 'value':
          aVal = a.value_eur || 0;
          bVal = b.value_eur || 0;
          break;
        case 'allocation':
          // Sort by post-plan allocation
          aVal = a.post_plan_allocation || 0;
          bVal = b.post_plan_allocation || 0;
          break;
        case 'ideal':
          aVal = a.ideal_allocation || 0;
          bVal = b.ideal_allocation || 0;
          break;
        case 'pnl':
          aVal = a.profit_pct || 0;
          bVal = b.profit_pct || 0;
          break;
        case 'recommendation':
          // Sort by recommendation value (buys positive, sells negative)
          aVal = a.recommendation ? (a.recommendation.action === 'buy' ? 1 : -1) * Math.abs(a.recommendation.value_delta_eur || 0) : 0;
          bVal = b.recommendation ? (b.recommendation.action === 'buy' ? 1 : -1) * Math.abs(b.recommendation.value_delta_eur || 0) : 0;
          break;
        default:
          return 0;
      }

      // For non-string comparisons
      if (typeof aVal === 'string') return aVal.localeCompare(bVal);
      return aVal - bVal;
    });

    return sortReversed ? sorted.reverse() : sorted;
  }, [securities, sortColumn, sortReversed]);

  const numColumns = 7;

  const allExpanded = sortedSecurities.length > 0 && sortedSecurities.every((s) => expandedSymbols.has(s.symbol));
  const noneExpanded = expandedSymbols.size === 0;

  const toggleAll = () => {
    if (allExpanded) {
      setExpandedSymbols(new Set());
    } else {
      setExpandedSymbols(new Set(sortedSecurities.map((s) => s.symbol)));
    }
  };

  return (
    <Table.ScrollContainer minWidth={700}>
      <Table highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th w={40}>
              <Tooltip label={allExpanded ? 'Collapse all' : 'Expand all'}>
                <ActionIcon
                  variant="subtle"
                  size="sm"
                  onClick={toggleAll}
                  style={{
                    transform: allExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                    transition: 'transform 150ms ease',
                  }}
                >
                  <IconChevronRight size={16} />
                </ActionIcon>
              </Tooltip>
            </Table.Th>
            <Table.Th>
              <SortableHeader sorted={sortColumn === 'symbol'} reversed={sortReversed} onSort={() => handleSort('symbol')}>
                Symbol
              </SortableHeader>
            </Table.Th>
            <Table.Th>
              <SortableHeader sorted={sortColumn === 'value'} reversed={sortReversed} onSort={() => handleSort('value')}>
                Value
              </SortableHeader>
            </Table.Th>
            <Table.Th>
              <SortableHeader sorted={sortColumn === 'allocation'} reversed={sortReversed} onSort={() => handleSort('allocation')}>
                Allocation
              </SortableHeader>
            </Table.Th>
            <Table.Th>
              <SortableHeader sorted={sortColumn === 'ideal'} reversed={sortReversed} onSort={() => handleSort('ideal')}>
                Ideal
              </SortableHeader>
            </Table.Th>
            <Table.Th>
              <SortableHeader sorted={sortColumn === 'pnl'} reversed={sortReversed} onSort={() => handleSort('pnl')}>
                P/L
              </SortableHeader>
            </Table.Th>
            <Table.Th>
              <SortableHeader sorted={sortColumn === 'recommendation'} reversed={sortReversed} onSort={() => handleSort('recommendation')}>
                Recommendation
              </SortableHeader>
            </Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {sortedSecurities.map((security) => {
            const {
              symbol,
              name,
              current_allocation,
              post_plan_allocation,
              ideal_allocation,
              profit_pct,
              profit_value_eur,
              value_eur,
              has_position,
              recommendation,
              price_warning,
              active,
            } = security;

            const isExpanded = expandedSymbols.has(symbol);

            // Compare post-plan to current for coloring
            const allocationDelta = post_plan_allocation - current_allocation;
            const isIncreasing = allocationDelta > 0.5;
            const isDecreasing = allocationDelta < -0.5;

            // Compare ideal to post-plan for ideal column coloring
            const idealDelta = ideal_allocation - post_plan_allocation;
            const isUnderIdeal = idealDelta > 0.5;
            const isOverIdeal = idealDelta < -0.5;

            return (
              <>
                <Table.Tr
                  key={symbol}
                  onClick={() => toggleExpanded(symbol)}
                  style={{ cursor: 'pointer' }}
                >
                  {/* Expand Button */}
                  <Table.Td>
                    <ActionIcon
                      variant="subtle"
                      size="sm"
                      style={{
                        transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                        transition: 'transform 150ms ease',
                      }}
                    >
                      <IconChevronRight size={16} />
                    </ActionIcon>
                  </Table.Td>

                  {/* Symbol / Name */}
                  <Table.Td>
                    <Group gap="xs">
                      {price_warning && (
                        <Tooltip label={price_warning}>
                          <IconAlertTriangle size={14} color="var(--mantine-color-yellow-6)" />
                        </Tooltip>
                      )}
                      <Box>
                        <Group gap="xs">
                          <Text fw={600} size="sm">{symbol}</Text>
                          {!active && <Badge color="gray" size="xs">Inactive</Badge>}
                        </Group>
                        <Text size="xs" c="dimmed" lineClamp={1}>{name}</Text>
                      </Box>
                    </Group>
                  </Table.Td>

                  {/* Value */}
                  <Table.Td>
                    {has_position ? (
                      <Text size="sm">{formatCurrency(value_eur, 'EUR')}</Text>
                    ) : (
                      <Text size="sm" c="dimmed">-</Text>
                    )}
                  </Table.Td>

                  {/* Allocation (current → post-plan) */}
                  <Table.Td>
                    <Group gap={4}>
                      <Text size="sm">{formatPercent(current_allocation, false)}</Text>
                      <Text size="sm" c="dimmed">{'\u2192'}</Text>
                      <Text
                        size="sm"
                        fw={500}
                        c={isIncreasing ? 'green' : isDecreasing ? 'red' : undefined}
                      >
                        {formatPercent(post_plan_allocation, false)}
                      </Text>
                    </Group>
                  </Table.Td>

                  {/* Ideal Allocation */}
                  <Table.Td>
                    <Text
                      size="sm"
                      c={isUnderIdeal ? 'yellow' : isOverIdeal ? 'yellow' : 'dimmed'}
                    >
                      {formatPercent(ideal_allocation, false)}
                    </Text>
                  </Table.Td>

                  {/* P/L */}
                  <Table.Td>
                    {has_position ? (
                      <Group gap={4}>
                        <Text
                          size="sm"
                          fw={500}
                          c={profit_pct >= 0 ? 'green' : 'red'}
                        >
                          {formatPercent(profit_pct)}
                        </Text>
                        <Text
                          size="sm"
                          c={profit_value_eur >= 0 ? 'green' : 'red'}
                        >
                          ({formatCurrency(profit_value_eur, 'EUR')})
                        </Text>
                      </Group>
                    ) : (
                      <Text size="sm" c="dimmed">-</Text>
                    )}
                  </Table.Td>

                  {/* Recommendation */}
                  <Table.Td>
                    {recommendation ? (
                      <Badge
                        color={recommendation.action === 'buy' ? 'green' : 'red'}
                        variant="light"
                        size="sm"
                      >
                        {recommendation.action.toUpperCase()} {formatCurrency(Math.abs(recommendation.value_delta_eur), 'EUR')}
                      </Badge>
                    ) : (
                      <Text size="sm" c="dimmed">-</Text>
                    )}
                  </Table.Td>
                </Table.Tr>

                {/* Expanded Row */}
                {isExpanded && (
                  <Table.Tr key={`${symbol}-expanded`}>
                    <Table.Td colSpan={numColumns} p={0}>
                      <SecurityExpandedRow
                        security={security}
                        onUpdate={onUpdate}
                        onDelete={onDelete}
                      />
                    </Table.Td>
                  </Table.Tr>
                )}
              </>
            );
          })}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
