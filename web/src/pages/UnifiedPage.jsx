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
  Collapse,
} from '@mantine/core';
import { IconPlus, IconArrowRight, IconCash, IconWallet, IconListCheck, IconTrendingUp, IconPencil, IconX, IconChevronDown } from '@tabler/icons-react';
import { SecurityTable } from '../components/SecurityTable';
import { AddSecurityModal } from '../components/AddSecurityModal';
import { DeleteSecurityModal } from '../components/DeleteSecurityModal';
import { SecurityAllocationCard } from '../components/SecurityAllocationCard';
import { JobsCard } from '../components/JobsCard';
import { MarketsOpenCard } from '../components/MarketsOpenCard';
import { PortfolioPnLChart } from '../components/PortfolioPnLChart';
import { PeriodStatsTable } from '../components/PeriodStatsTable';
import { PortfolioRatingCard } from '../components/PortfolioRatingCard';
import { CompositionCard } from '../components/CompositionCard';
import { ForwardReturnCard } from '../components/ForwardReturnCard';
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
  getPortfolioPeriodStats,
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
  { value: 'review', label: 'Review' },
  { value: 'all', label: 'All Securities' },
  { value: 'positions', label: 'Positions Only' },
  { value: 'buys', label: 'Buy Recommendations' },
  { value: 'sells', label: 'Sell Recommendations' },
  { value: 'underweight', label: 'Underweight' },
  { value: 'overweight', label: 'Overweight' },
];

const SORTS = [
  { value: 'priority', label: 'Execution Order' },
  { value: 'allocation_delta', label: 'Allocation Deviation' },
  { value: 'profit_pct', label: 'P/L %' },
  { value: 'value', label: 'Position Value' },
  { value: 'name', label: 'Name (A-Z)' },
  { value: 'symbol', label: 'Symbol (A-Z)' },
];

const COLLAPSED_WIDGETS_STORAGE_KEY = 'sentinel.collapsedWidgets';
const DEFAULT_COLLAPSED_WIDGETS = {
  'inactive-securities': true,
  composition: true,
  'forward-return': true,
};

export function hasDisabledTradePermission(security) {
  return Number(security.allow_buy ?? 1) === 0 || Number(security.allow_sell ?? 1) === 0;
}

export function shouldShowSecurityForFilter(security, filter) {
  switch (filter) {
    case 'review': {
      const allocationGap = Math.abs((security.ideal_allocation || 0) - (security.current_allocation || 0));
      return (
        Boolean(security.recommendation) ||
        Boolean(security.price_warning) ||
        hasDisabledTradePermission(security) ||
        allocationGap > 0.5
      );
    }
    case 'positions':
      return Boolean(security.has_position);
    case 'buys':
      return security.recommendation?.action === 'buy';
    case 'sells':
      return security.recommendation?.action === 'sell';
    case 'underweight':
      return security.ideal_allocation - security.current_allocation > 0.5;
    case 'overweight':
      return security.current_allocation - security.ideal_allocation > 0.5;
    default:
      return true;
  }
}

function readCollapsedWidgets() {
  if (typeof window === 'undefined') return {};
  try {
    const stored = window.localStorage?.getItem(COLLAPSED_WIDGETS_STORAGE_KEY);
    return stored ? { ...DEFAULT_COLLAPSED_WIDGETS, ...JSON.parse(stored) } : DEFAULT_COLLAPSED_WIDGETS;
  } catch {
    return DEFAULT_COLLAPSED_WIDGETS;
  }
}

function writeCollapsedWidgets(collapsedWidgets) {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage?.setItem(COLLAPSED_WIDGETS_STORAGE_KEY, JSON.stringify(collapsedWidgets));
  } catch {
    // Ignore storage failures. The UI remains fully usable without persistence.
  }
}

function UnifiedPage() {
  const [period, setPeriod] = useState('1Y');
  const [filter, setFilter] = useState('review');
  const [sort, setSort] = useState('priority');
  const [search, setSearch] = useState('');
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [securityToDelete, setSecurityToDelete] = useState(null);
  const [collapsedWidgets, setCollapsedWidgets] = useState(readCollapsedWidgets);

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
  const longTermPlan = recommendationsData?.plan;

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

  const { data: periodStats } = useQuery({
    queryKey: ['portfolio-period-stats'],
    queryFn: () => getPortfolioPeriodStats(),
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

  useEffect(() => {
    writeCollapsedWidgets(collapsedWidgets);
  }, [collapsedWidgets]);

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
    mutationFn: ({ symbol }) => addSecurity(symbol),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['unified'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: ({ symbol, sellPosition }) => deleteSecurity(symbol, sellPosition),
    onMutate: async () => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['unified', period] });

      // Snapshot the previous value
      const prev = queryClient.getQueryData(['unified', period]);

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

  const handleAdd = async (symbol) => {
    await addMutation.mutateAsync({ symbol });
  };

  const handleDeleteClick = (security) => {
    setSecurityToDelete(security);
    setDeleteModalOpen(true);
  };

  const handleDelete = async (symbol, sellPosition) => {
    await deleteMutation.mutateAsync({ symbol, sellPosition });
  };

  const toggleWidget = (widgetId) => {
    setCollapsedWidgets((current) => ({
      ...current,
      [widgetId]: !current[widgetId],
    }));
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

    result = result.filter((s) => shouldShowSecurityForFilter(s, filter));

    // Apply sort
    result.sort((a, b) => {
      switch (sort) {
        case 'priority':
          // Planner execution rank is the same order used by the executor.
          const aRank = a.recommendation?.execution_rank ?? Number.POSITIVE_INFINITY;
          const bRank = b.recommendation?.execution_rank ?? Number.POSITIVE_INFINITY;
          return aRank - bRank || a.symbol.localeCompare(b.symbol);
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
        {/* Main Content */}
        <Stack gap="md" className="unified__main" style={{ minWidth: 0 }}>
          <CollapsibleWidget
            id="markets"
            title="Markets"
            collapsed={collapsedWidgets.markets}
            onToggle={toggleWidget}
          >
            <MarketsOpenCard />
          </CollapsibleWidget>

          {/* Jobs Card */}
          <CollapsibleWidget
            id="jobs"
            title="Jobs"
            collapsed={collapsedWidgets.jobs}
            onToggle={toggleWidget}
          >
            <JobsCard />
          </CollapsibleWidget>

          {/* Status Bar */}
          <CollapsibleWidget
            id="status"
            title="Portfolio Status"
            collapsed={collapsedWidgets.status}
            onToggle={toggleWidget}
          >
            <Card shadow="sm" padding="sm" withBorder className="unified__status-bar">
              <Stack gap="sm" className="unified__status-content">
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

                <PlannerTape
                  recommendations={recommendations || []}
                  longTermPlan={longTermPlan}
                  planSummary={planSummary}
                />
              </Stack>
            </Card>
          </CollapsibleWidget>

          {/* P&L Chart */}
          <CollapsibleWidget
            id="pnl"
            title="Portfolio P&L"
            collapsed={collapsedWidgets.pnl}
            onToggle={toggleWidget}
          >
            <Card shadow="sm" padding="sm" withBorder className="unified__pnl-chart">
              <Text size="sm" fw={500} mb="xs">Portfolio P&L</Text>
              <PeriodStatsTable stats={periodStats?.period_stats} />
              <PortfolioPnLChart
                snapshots={pnlData?.snapshots || []}
                summary={pnlData?.summary}
                height={300}
              />
            </Card>
          </CollapsibleWidget>

          {/* Global Controls */}
          <CollapsibleWidget
            id="controls"
            title="Controls"
            collapsed={collapsedWidgets.controls}
            onToggle={toggleWidget}
          >
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
          </CollapsibleWidget>

          {/* Securities Table */}
          <CollapsibleWidget
            id="securities"
            title="Securities"
            collapsed={collapsedWidgets.securities}
            onToggle={toggleWidget}
          >
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
          </CollapsibleWidget>

          {/* Inactive Securities Table */}
          {inactiveSecurities.length > 0 && (
            <CollapsibleWidget
              id="inactive-securities"
              title="Inactive Securities"
              collapsed={collapsedWidgets['inactive-securities']}
              onToggle={toggleWidget}
            >
              <Card shadow="sm" padding="md" withBorder className="unified__inactive-table">
                <Text component="div" size="sm" fw={500} mb="sm">
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
            </CollapsibleWidget>
          )}
        </Stack>

        {/* Right Sidebar - Allocation Cards */}
        <Stack gap="md" className="unified__sidebar">
          <CollapsibleWidget
            id="risk-return"
            title="Risk / Return"
            collapsed={collapsedWidgets['risk-return']}
            onToggle={toggleWidget}
          >
            <PortfolioRatingCard />
          </CollapsibleWidget>
          <CollapsibleWidget
            id="security-allocation"
            title="Security Allocation"
            collapsed={collapsedWidgets['security-allocation']}
            onToggle={toggleWidget}
          >
            <SecurityAllocationCard
              securities={securities}
              recommendations={recommendations}
              longTermPlan={longTermPlan}
              cashAfterPlan={planSummary?.cash_after_plan}
            />
          </CollapsibleWidget>
          <CollapsibleWidget
            id="composition"
            title="Composition"
            collapsed={collapsedWidgets.composition}
            onToggle={toggleWidget}
          >
            <CompositionCard />
          </CollapsibleWidget>
          <CollapsibleWidget
            id="forward-return"
            title="Forward Return Projection"
            collapsed={collapsedWidgets['forward-return']}
            onToggle={toggleWidget}
          >
            <ForwardReturnCard />
          </CollapsibleWidget>
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

function CollapsibleWidget({ id, title, collapsed, onToggle, children }) {
  const isCollapsed = Boolean(collapsed);

  return (
    <section className={`collapsible-widget ${isCollapsed ? 'collapsible-widget--collapsed' : ''}`}>
      <button
        type="button"
        className="collapsible-widget__toggle"
        aria-expanded={!isCollapsed}
        aria-controls={`widget-${id}`}
        onClick={() => onToggle(id)}
      >
        <span className="collapsible-widget__title">{title}</span>
        <IconChevronDown size={16} className="collapsible-widget__icon" aria-hidden="true" />
      </button>
      <Collapse expanded={!isCollapsed} transitionDuration={120}>
        <div id={`widget-${id}`} className="collapsible-widget__content">
          {children}
        </div>
      </Collapse>
    </section>
  );
}

function PlannerTape({ recommendations, longTermPlan, planSummary }) {
  const todayItems = recommendations.map((rec) => {
    const isSell = rec.action === 'sell';
    const pctOfPosition = isSell && rec.current_value_eur > 0
      ? ` ${Math.round((Math.abs(rec.value_delta_eur) / rec.current_value_eur) * 100)}%`
      : '';
    return {
      key: `today-${rec.symbol}-${rec.action}`,
      tone: rec.action,
      label: `${rec.action.toUpperCase()} ${formatEur(Math.abs(rec.value_delta_eur))}${pctOfPosition} ${rec.symbol}`,
      title: rec.is_fallback ? 'Convergence fallback after the configured patience window' : rec.reason,
    };
  });

  const securityTargets = longTermPlan?.targets || [];
  const cashTarget = longTermPlan ? {
    symbol: 'CASH',
    clara_score: null,
    opportunity_score: null,
    target_value_eur: Number(longTermPlan.target_cash_value_eur || 0),
    gap_eur: Number(longTermPlan.cash_gap_eur || 0),
    isCash: true,
  } : null;
  const allTargets = cashTarget && (cashTarget.target_value_eur > 0 || Number(longTermPlan?.current_cash_eur || 0) > 0)
    ? [...securityTargets, cashTarget]
    : securityTargets;
  const targetItems = [...allTargets]
    .sort((a, b) => Math.abs(Number(b.gap_eur || 0)) - Math.abs(Number(a.gap_eur || 0)))
    .slice(0, 6)
    .map((target) => {
      const gap = Number(target.gap_eur || 0);
      const gapText = target.sell_locked ? 'locked' : `${gap >= 0 ? '+' : '-'}${formatEur(Math.abs(gap))}`;
      return {
        key: `target-${target.symbol}`,
        tone: 'target',
        label: `${target.symbol} ${formatEur(target.target_value_eur)} (${gapText})`,
        title: target.isCash
          ? 'Explicit cash allocation required by the target and position constraints'
          : target.sell_locked
            ? `No-sell floor; model target ${formatEur(target.model_target_value_eur || 0)}`
          : `Clara ${Number(target.clara_score || 0).toFixed(2)}, opportunity ${Number(target.opportunity_score || 0).toFixed(2)}`,
      };
    });

  return (
    <div className="planner-tape">
      <PlannerTapeGroup
        icon={<IconListCheck size={15} />}
        title={planSummary?.valid_for_minutes ? `Next ${planSummary.valid_for_minutes} min` : 'Next cycle'}
        items={todayItems}
        empty="No pending actions"
      />
      <IconArrowRight size={15} className="planner-tape__inline-arrow" />
      <PlannerTapeGroup
        icon={<IconTrendingUp size={15} />}
        title={`${longTermPlan?.horizon_months || 12} mo gaps`}
        items={targetItems}
        empty="Target unavailable"
      />
      {longTermPlan && (
        <span className="planner-tape__meta">
          {formatEur(longTermPlan.terminal_portfolio_value_eur || 0)} by {longTermPlan.horizon_end_date} · {formatEur(longTermPlan.avg_monthly_net_deposit_eur || 0)}/mo
          {` · ${securityTargets.length} securities`}
          {planSummary ? ` · cash after today ${formatEur(planSummary.cash_after_plan || 0)}` : ''}
        </span>
      )}
    </div>
  );
}

function PlannerTapeGroup({ icon, title, items, empty }) {
  return (
    <>
      <span className="planner-tape__label">
        {icon}
        {title}:
      </span>
      {items.length > 0 ? items.map((item) => (
        <span
          key={item.key}
          title={item.title}
          className={`planner-tape__pill planner-tape__pill--${item.tone}`}
        >
          {item.label}
        </span>
      )) : (
        <span className="planner-tape__empty">{empty}</span>
      )}
    </>
  );
}

export default UnifiedPage;
