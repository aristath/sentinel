/**
 * Unified Page
 *
 * Single page showing all securities as cards with full information.
 * Includes global controls for timeframe, filtering, and sorting.
 */
import { useEffect, useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { notifications } from '@mantine/notifications';
import {
  Stack,
  Group,
  SegmentedControl,
  Select,
  TextInput,
  NumberInput,
  Text,
  Badge,
  Card,
  Button,
  ActionIcon,
  Table,
} from '@mantine/core';
import { IconPlus, IconArrowRight, IconCash, IconWallet, IconListCheck, IconTrendingUp, IconPencil, IconX } from '@tabler/icons-react';
import { SecurityTable } from '../components/SecurityTable';
import { AddSecurityModal } from '../components/AddSecurityModal';
import { DeleteSecurityModal } from '../components/DeleteSecurityModal';
import { SecurityAllocationCard } from '../components/SecurityAllocationCard';
import { AllocationRadarCard } from '../components/AllocationRadarCard';
import { JobsCard } from '../components/JobsCard';
import { MarketsOpenCard } from '../components/MarketsOpenCard';
import { PortfolioPnLChart } from '../components/PortfolioPnLChart';
import LoadingState from '../components/LoadingState';
import ErrorState from '../components/ErrorState';
import {
  getUnifiedView,
  getSecurities,
  updateSecurity,
  addSecurity,
  deleteSecurity,
  getPortfolio,
  getRecommendations,
  getCashFlows,
  getPortfolioPnLHistory,
  getSettings,
  updateSetting,
} from '../api/client';

import { formatEur, formatCurrencySymbol as formatCurrency } from '../utils/formatting';
import './UnifiedPage.css';

const PERIODS = [
  { value: '1M', label: '1M' },
  { value: '1Y', label: '1Y' },
  { value: '5Y', label: '5Y' },
  { value: '10Y', label: '10Y' },
];

const FILTERS = [
  { value: 'all', label: 'All Securities' },
  { value: 'positions', label: 'Positions Only' },
  { value: 'buys', label: 'Buy Recommendations' },
  { value: 'sells', label: 'Sell Recommendations' },
  { value: 'underweight', label: 'Underweight' },
  { value: 'overweight', label: 'Overweight' },
];

const SORTS = [
  { value: 'priority', label: 'Priority (Recommendation)' },
  { value: 'allocation_delta', label: 'Allocation Deviation' },
  { value: 'profit_pct', label: 'P/L %' },
  { value: 'value', label: 'Position Value' },
  { value: 'name', label: 'Name (A-Z)' },
  { value: 'symbol', label: 'Symbol (A-Z)' },
];

function UnifiedPage() {
  const [period, setPeriod] = useState('1Y');
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('priority');
  const [search, setSearch] = useState('');
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [securityToDelete, setSecurityToDelete] = useState(null);

  const queryClient = useQueryClient();

  const { data: securities, isLoading, error } = useQuery({
    queryKey: ['unified', period],
    queryFn: () => getUnifiedView(period),
    refetchInterval: 60000, // Refresh every minute
  });

  const { data: allSecurities } = useQuery({
    queryKey: ['securities'],
    queryFn: getSecurities,
    refetchInterval: 60000,
  });

  const inactiveSecurities = useMemo(() => {
    if (!allSecurities) return [];
    return allSecurities.filter((s) => !s.active);
  }, [allSecurities]);

  const { data: portfolio } = useQuery({
    queryKey: ['portfolio'],
    queryFn: getPortfolio,
    refetchInterval: 60000,
  });

  const { data: recommendationsData } = useQuery({
    queryKey: ['recommendations'],
    queryFn: () => getRecommendations(), // Uses backend setting
    refetchInterval: 60000,
  });
  const recommendations = recommendationsData?.recommendations;
  const planSummary = recommendationsData?.summary;

  const { data: cashFlows } = useQuery({
    queryKey: ['cashflows'],
    queryFn: getCashFlows,
    refetchInterval: 300000, // Refresh every 5 minutes
  });

  const { data: pnlData } = useQuery({
    queryKey: ['portfolio-pnl'],
    queryFn: () => getPortfolioPnLHistory(),
    refetchInterval: 300000, // Refresh every 5 minutes
  });

  // Settings for simulated cash
  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: getSettings,
  });
  const isResearchMode = settings?.trading_mode === 'research';
  const simulatedCash = settings?.simulated_cash_eur;
  const [editingCash, setEditingCash] = useState(false);
  const [cashValue, setCashValue] = useState('');

  const cashMutation = useMutation({
    mutationFn: (value) => updateSetting('simulated_cash_eur', value),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      queryClient.invalidateQueries({ queryKey: ['portfolio'] });
      queryClient.invalidateQueries({ queryKey: ['recommendations'] });
      setEditingCash(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ symbol, data }) => updateSecurity(symbol, data),
    onMutate: async ({ symbol, data }) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['unified', period] });

      // Snapshot the previous value
      const prev = queryClient.getQueryData(['unified', period]);

      // Optimistically update the security
      queryClient.setQueryData(['unified', period], (old) => {
        if (!old) return old;
        return old.map((sec) =>
          sec.symbol === symbol ? { ...sec, ...data } : sec
        );
      });

      return { prev };
    },
    onError: (err, variables, ctx) => {
      // Rollback on error
      if (ctx?.prev) {
        queryClient.setQueryData(['unified', period], ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['unified'] });
    },
  });


  const addMutation = useMutation({
    mutationFn: ({ symbol, geography, industry }) => addSecurity(symbol, geography, industry),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unified'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ symbol, sellPosition }) => deleteSecurity(symbol, sellPosition),
    onMutate: async ({ symbol }) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['unified', period] });

      // Snapshot the previous value
      const prev = queryClient.getQueryData(['unified', period]);

      // Optimistically remove the security
      queryClient.setQueryData(['unified', period], (old) => {
        if (!old) return old;
        return old.filter((sec) => sec.symbol !== symbol);
      });

      return { prev };
    },
    onError: (err, variables, ctx) => {
      // Rollback on error
      if (ctx?.prev) {
        queryClient.setQueryData(['unified', period], ctx.prev);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['unified'] });
    },
  });

  const handleUpdate = async (symbol, data) => {
    await updateMutation.mutateAsync({ symbol, data });
  };

  const handleAdd = async (symbol, geography, industry) => {
    await addMutation.mutateAsync({ symbol, geography, industry });
  };

  const handleDeleteClick = (security) => {
    setSecurityToDelete(security);
    setDeleteModalOpen(true);
  };

  const handleDelete = async (symbol, sellPosition) => {
    await deleteMutation.mutateAsync({ symbol, sellPosition });
  };

  // Filter and sort securities
  const filteredSecurities = useMemo(() => {
    if (!securities) return [];

    let result = [...securities];

    // Apply search filter
    if (search) {
      const term = search.toLowerCase();
      result = result.filter(
        (s) =>
          s.symbol.toLowerCase().includes(term) ||
          (s.name && s.name.toLowerCase().includes(term)) ||
          (s.geography && s.geography.toLowerCase().includes(term)) ||
          (s.industry && s.industry.toLowerCase().includes(term))
      );
    }

    // Apply filter
    switch (filter) {
      case 'positions':
        result = result.filter((s) => s.has_position);
        break;
      case 'buys':
        result = result.filter((s) => s.recommendation?.action === 'buy');
        break;
      case 'sells':
        result = result.filter((s) => s.recommendation?.action === 'sell');
        break;
      case 'underweight':
        result = result.filter((s) => s.ideal_allocation - s.current_allocation > 0.5);
        break;
      case 'overweight':
        result = result.filter((s) => s.current_allocation - s.ideal_allocation > 0.5);
        break;
    }

    // Apply sort
    result.sort((a, b) => {
      switch (sort) {
        case 'priority':
          // Higher priority first, then by symbol
          const aPriority = a.recommendation?.priority || 0;
          const bPriority = b.recommendation?.priority || 0;
          return bPriority - aPriority || a.symbol.localeCompare(b.symbol);
        case 'allocation_delta':
          // Largest absolute deviation first
          const aDelta = Math.abs(a.ideal_allocation - a.current_allocation);
          const bDelta = Math.abs(b.ideal_allocation - b.current_allocation);
          return bDelta - aDelta;
        case 'profit_pct':
          return (b.profit_pct || 0) - (a.profit_pct || 0);
        case 'value':
          return (b.value_eur || 0) - (a.value_eur || 0);
        case 'name':
          return (a.name || a.symbol).localeCompare(b.name || b.symbol);
        case 'symbol':
          return a.symbol.localeCompare(b.symbol);
        default:
          return 0;
      }
    });

    return result;
  }, [securities, filter, sort, search]);

  // Summary stats
  const stats = useMemo(() => {
    if (!securities) return { total: 0, positions: 0, buys: 0, sells: 0 };
    return {
      total: securities.length,
      positions: securities.filter((s) => s.has_position).length,
      buys: securities.filter((s) => s.recommendation?.action === 'buy').length,
      sells: securities.filter((s) => s.recommendation?.action === 'sell').length,
    };
  }, [securities]);

  if (isLoading) {
    return <LoadingState message="Loading securities..." />;
  }

  if (error) {
    return <ErrorState message={`Error loading securities: ${error.message}`} />;
  }

  return (
    <>
      <div className="unified">
        {/* Left Sidebar - Allocation Cards */}
        <Stack gap="md" className="unified__sidebar">
          <MarketsOpenCard />
          <SecurityAllocationCard
            securities={securities}
            recommendations={recommendations}
          />
          <AllocationRadarCard
            type="geography"
            securities={securities}
            recommendations={recommendations}
          />
          <AllocationRadarCard
            type="industry"
            securities={securities}
            recommendations={recommendations}
          />
        </Stack>

        {/* Main Content */}
        <Stack gap="md" className="unified__main" style={{ minWidth: 0 }}>
          {/* Jobs Card */}
          <JobsCard />

          {/* Status Bar */}
          <Card shadow="sm" padding="sm" withBorder className="unified__status-bar">
            <Stack gap="xs" className="unified__status-content">
              {/* Top row: Portfolio and Cash */}
              <Group gap="xl" className="unified__status-row unified__status-row--summary">
                {/* Portfolio Value */}
                <Group gap="xs" className="unified__status-section unified__status-section--portfolio">
                  <IconWallet size={22} style={{ opacity: 0.6 }} className="unified__status-icon" />
                  <Text size="lg" c="dimmed" className="unified__status-label">Portfolio:</Text>
                  <Text size="lg" fw={600} className="unified__status-value unified__status-value--portfolio">
                    {formatEur(portfolio?.total_value_eur || 0)}
                  </Text>
                </Group>

                {/* Cash */}
                <Group gap="xs" className="unified__status-section unified__status-section--cash">
                  <IconCash size={22} style={{ opacity: 0.6 }} className="unified__status-icon" />
                  <Text size="lg" c="dimmed" className="unified__status-label">Cash:</Text>
                  {editingCash ? (
                    <NumberInput
                      size="sm"
                      value={cashValue}
                      onChange={setCashValue}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') cashMutation.mutate(cashValue === '' ? null : cashValue);
                        if (e.key === 'Escape') setEditingCash(false);
                      }}
                      suffix=" €"
                      decimalScale={2}
                      autoFocus
                      style={{ width: 150 }}
                    />
                  ) : (
                    <>
                      <Text size="lg" fw={600} className="unified__status-value unified__status-value--cash-total">
                        {formatEur(portfolio?.total_cash_eur || 0)}
                      </Text>
                      {simulatedCash != null && (
                        <>
                          <Badge size="sm" variant="light" color="yellow">simulated</Badge>
                          <ActionIcon
                            size="sm"
                            variant="subtle"
                            color="red"
                            onClick={() => cashMutation.mutate(null)}
                            title="Clear simulated cash"
                          >
                            <IconX size={14} />
                          </ActionIcon>
                        </>
                      )}
                      {isResearchMode && (
                        <ActionIcon
                          size="sm"
                          variant="subtle"
                          onClick={() => { setCashValue(portfolio?.total_cash_eur || 0); setEditingCash(true); }}
                          title="Edit simulated cash"
                        >
                          <IconPencil size={14} />
                        </ActionIcon>
                      )}
                    </>
                  )}
                  {!editingCash && portfolio?.cash && Object.keys(portfolio.cash).length > 0 && simulatedCash == null && (
                    <Text size="lg" c="dimmed" className="unified__status-cash-breakdown">
                      ({Object.entries(portfolio.cash).map(([curr, amt], i) => (
                        <span key={curr} className={`unified__status-cash-item unified__status-cash-item--${curr.toLowerCase()}`}>
                          {i > 0 && ', '}
                          {formatCurrency(amt, curr)}
                        </span>
                      ))})
                    </Text>
                  )}
                </Group>
              </Group>

              {/* Middle row: Cash Flows */}
              {cashFlows && (
                <Group gap="xl" className="unified__status-row unified__status-row--cashflows">
                  <Group gap="xs" className="unified__status-section unified__status-section--cashflows">
                    <IconTrendingUp size={18} style={{ opacity: 0.6 }} className="unified__status-icon" />
                    <Text size="sm" c="dimmed">Deposits:</Text>
                    <Text size="sm" fw={500} c="green">{formatEur(cashFlows.deposits || 0)}</Text>
                    <Text size="sm" c="dimmed">Withdrawals:</Text>
                    <Text size="sm" fw={500} c="red">{formatEur(cashFlows.withdrawals || 0)}</Text>
                    <Text size="sm" c="dimmed">Dividends:</Text>
                    <Text size="sm" fw={500} c="green">{formatEur(cashFlows.dividends || 0)}</Text>
                    <Text size="sm" c="dimmed">Fees:</Text>
                    <Text size="sm" fw={500} c="red">{formatEur((cashFlows.fees || 0) + (cashFlows.taxes || 0))}</Text>
                    <Text size="sm" c="dimmed">—</Text>
                    <Text size="sm" c="dimmed">Total Profit:</Text>
                    <Text size="sm" fw={600} c={(cashFlows.total_profit || 0) >= 0 ? 'green' : 'red'}>
                      {formatEur(cashFlows.total_profit || 0)}
                    </Text>
                  </Group>
                </Group>
              )}

              {/* Bottom row: Plan */}
              <Group gap="xs" wrap="wrap" className="unified__status-row unified__status-row--plan">
                <Group gap="xs" className="unified__status-section unified__status-section--plan">
                  <IconListCheck size={18} style={{ opacity: 0.6 }} className="unified__status-icon" />
                  <Text size="sm" c="dimmed" className="unified__status-label">Plan:</Text>
                </Group>
                {recommendations && recommendations.length > 0 ? (
                  <Group gap={6} wrap="wrap" className="unified__status-plan-steps">
                    {recommendations.map((rec, i) => {
                      const isSell = rec.action === 'sell';
                      const pctOfPosition = isSell && rec.current_value_eur > 0
                        ? ` (${Math.round((Math.abs(rec.value_delta_eur) / rec.current_value_eur) * 100)}%)`
                        : '';
                      return (
                        <Group gap={4} key={rec.symbol} className={`unified__status-plan-step unified__status-plan-step--${rec.action}`}>
                          {i > 0 && <IconArrowRight size={14} style={{ opacity: 0.4 }} className="unified__status-plan-arrow" />}
                          <Badge
                            size="md"
                            color={isSell ? 'red' : 'green'}
                            variant="light"
                            className={`unified__status-plan-badge unified__status-plan-badge--${rec.action}`}
                          >
                            {rec.action.toUpperCase()} {formatEur(Math.abs(rec.value_delta_eur))}{pctOfPosition} {rec.symbol}
                          </Badge>
                        </Group>
                      );
                    })}
                    {/* Cash after plan */}
                    {planSummary && (
                      <Text size="sm" c="dimmed" fw={500} className="unified__status-plan-cash-result">
                        After plan: <span style={{ color: planSummary.cash_after_plan >= 0 ? 'var(--mantine-color-green-6)' : 'var(--mantine-color-red-6)' }}>{formatEur(planSummary.cash_after_plan)}</span>
                      </Text>
                    )}
                  </Group>
                ) : (
                  <Text size="sm" c="dimmed" fs="italic" className="unified__status-no-plan">No pending actions</Text>
                )}
              </Group>
            </Stack>
          </Card>

          {/* P&L Chart */}
          <Card shadow="sm" padding="sm" withBorder className="unified__pnl-chart">
            <Text size="sm" fw={500} mb="xs">Portfolio P&L</Text>
            <PortfolioPnLChart
              snapshots={pnlData?.snapshots || []}
              summary={pnlData?.summary}
              height={300}
            />
          </Card>

          {/* Global Controls */}
          <Card shadow="sm" padding="md" withBorder className="unified__controls">
            <Group justify="space-between" wrap="wrap" gap="md" className="unified__controls-row">
              {/* Period Selector */}
              <Group gap="sm" className="unified__period">
                <Text size="sm" fw={500} className="unified__period-label">Period:</Text>
                <SegmentedControl
                  value={period}
                  onChange={setPeriod}
                  data={PERIODS}
                  size="sm"
                  className="unified__period-selector"
                />
              </Group>

              {/* Search */}
              <TextInput
                placeholder="Search..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                size="sm"
                w={200}
                className="unified__search"
              />

              {/* Filter */}
              <Select
                value={filter}
                onChange={setFilter}
                data={FILTERS}
                size="sm"
                w={180}
                className="unified__filter"
              />

              {/* Sort */}
              <Select
                value={sort}
                onChange={setSort}
                data={SORTS}
                size="sm"
                w={200}
                className="unified__sort"
              />

              {/* Add Security Button */}
              <Button
                leftSection={<IconPlus size={16} />}
                size="sm"
                variant="light"
                onClick={() => setAddModalOpen(true)}
                className="unified__add-btn"
              >
                Add Security
              </Button>
            </Group>

            {/* Stats */}
            <Group gap="md" mt="sm" className="unified__stats">
              <Badge variant="light" color="gray" className="unified__stat unified__stat--total">{stats.total} securities</Badge>
              <Badge variant="light" color="blue" className="unified__stat unified__stat--positions">{stats.positions} positions</Badge>
              <Badge variant="light" color="green" className="unified__stat unified__stat--buys">{stats.buys} buy signals</Badge>
              <Badge variant="light" color="red" className="unified__stat unified__stat--sells">{stats.sells} sell signals</Badge>
              <Badge variant="light" color="gray" className="unified__stat unified__stat--shown">{filteredSecurities.length} shown</Badge>
            </Group>
          </Card>

          {/* Securities Table */}
          {filteredSecurities.length === 0 ? (
            <Card shadow="sm" padding="lg" withBorder className="unified__empty-state">
              <Text c="dimmed" ta="center" className="unified__empty-text">No securities match your filters</Text>
            </Card>
          ) : (
            <Card shadow="sm" padding="md" withBorder className="unified__securities-table">
              <SecurityTable
                securities={filteredSecurities}
                onUpdate={handleUpdate}
                onDelete={handleDeleteClick}
              />
            </Card>
          )}

          {/* Inactive Securities Table */}
          {inactiveSecurities.length > 0 && (
            <Card shadow="sm" padding="md" withBorder className="unified__inactive-table">
              <Text size="sm" fw={500} mb="sm">
                Inactive Securities
                <Badge variant="light" color="gray" size="sm" ml="xs">{inactiveSecurities.length}</Badge>
              </Text>
              <Table.ScrollContainer minWidth={400}>
                <Table highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th><Text fw={600} size="sm">Symbol</Text></Table.Th>
                      <Table.Th><Text fw={600} size="sm">Name</Text></Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {inactiveSecurities.map((sec) => (
                      <Table.Tr key={sec.symbol}>
                        <Table.Td><Text size="sm" fw={500}>{sec.symbol}</Text></Table.Td>
                        <Table.Td><Text size="sm" c="dimmed">{sec.name || '-'}</Text></Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Table.ScrollContainer>
            </Card>
          )}
        </Stack>
      </div>

      {/* Modals */}
      <AddSecurityModal
        opened={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onAdd={handleAdd}
      />
      <DeleteSecurityModal
        opened={deleteModalOpen}
        onClose={() => {
          setDeleteModalOpen(false);
          setSecurityToDelete(null);
        }}
        onDelete={handleDelete}
        security={securityToDelete}
      />
    </>
  );
}

export default UnifiedPage;
