/**
 * Security Table Component
 *
 * Displays the investment universe (all securities) in a sortable, filterable table.
 * Provides comprehensive security information and management capabilities.
 *
 * Features:
 * - Sortable columns (symbol, name, geography, exchange, sector, qty, price, value, score, priority)
 * - Filtering by geography, industry, search query, minimum score
 * - Column visibility toggle (show/hide columns)
 * - Sparkline charts (1Y or 5Y timeframe)
 * - Inline multiplier editing (numeric input)
 * - Icon-based rating slider (visual multiplier control with 0.2-3.0 range)
 * - Security actions (edit, refresh score, remove)
 * - Concentration alerts (visual indicators for over-concentration)
 * - Tags display with color coding
 * - Buy/Sell indicators
 *
 * This is the main component for viewing and managing the investment universe.
 */
import { Card, Table, TextInput, Select, Group, Button, Text, ActionIcon, Badge, NumberInput, Menu, SegmentedControl, Skeleton } from '@mantine/core';
import { IconEdit, IconRefresh, IconTrash, IconColumns, IconCheck } from '@tabler/icons-react';
import { useSecuritiesStore } from '../../stores/securitiesStore';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { SecuritySparkline } from '../charts/SecuritySparkline';
import { RatingIcon } from './RatingIcon';
import { formatCurrency, formatNumber } from '../../utils/formatters';
import { getTagName, getTagColor } from '../../utils/tagNames';
import { useEffect, useState } from 'react';

/**
 * Security table component
 *
 * Displays all securities in the investment universe with filtering, sorting, and management features.
 *
 * @returns {JSX.Element} Security table with filters, columns, and actions
 */
export function SecurityTable() {
  const {
    securities,
    sparklineTimeframe,
    securityFilter,
    industryFilter,
    searchQuery,
    minScore,
    sortBy,
    sortDesc,
    visibleColumns,
    setSecurityFilter,
    setIndustryFilter,
    setSearchQuery,
    setMinScore,
    setSortBy,
    getFilteredSecurities,
    refreshScore,
    removeSecurity,
    updateMultiplier,
    fetchColumnVisibility,
    toggleColumnVisibility,
    fetchSparklines,
    setSparklineTimeframe,
  } = useSecuritiesStore();
  const [sparklinesLoading, setSparklinesLoading] = useState(true);
  const { openEditSecurityModal, openAddSecurityModal } = useAppStore();
  const { alerts } = usePortfolioStore();

  // Load column visibility preferences on mount
  useEffect(() => {
    fetchColumnVisibility();
  }, [fetchColumnVisibility]);

  // Load sparklines when component mounts or timeframe changes
  useEffect(() => {
    const loadSparklines = async () => {
      setSparklinesLoading(true);
      await fetchSparklines();
      setSparklinesLoading(false);
    };
    loadSparklines();
  }, [fetchSparklines, sparklineTimeframe]);

  // Get filtered and sorted securities
  const filteredSecurities = getFilteredSecurities();

  // Extract unique geographies and industries for filter dropdowns
  const geographies = [...new Set(securities.map(s => s.geography).filter(Boolean))].sort();
  const industries = [...new Set(securities.map(s => s.industry).filter(Boolean))].sort();

  /**
   * Handles column sorting
   *
   * Toggles sort direction if clicking the same column, otherwise sets new sort field.
   *
   * @param {string} field - Field name to sort by
   */
  const handleSort = (field) => {
    if (sortBy === field) {
      // Toggle direction if same field
      setSortBy(field, !sortDesc);
    } else {
      // New field, default to descending
      setSortBy(field, true);
    }
  };

  /**
   * Gets concentration alert for a security (if position is over-concentrated)
   *
   * @param {string} symbol - Security symbol
   * @returns {Object|undefined} Alert object or undefined
   */
  const getPositionAlert = (symbol) => {
    return alerts.find(a => a.type === 'security' && a.name === symbol);
  };

  /**
   * Gets badge color class for score value
   *
   * Score ranges:
   * - >= 0.7: green (high score)
   * - >= 0.5: yellow (medium-high)
   * - >= 0.3: orange (medium-low)
   * - < 0.3: red (low score)
   *
   * @param {number} score - Score value (0.0 to 1.0)
   * @returns {Object} Badge props with color and variant
   */
  const getScoreClass = (score) => {
    if (score >= 0.7) return { color: 'green', variant: 'light' };
    if (score >= 0.5) return { color: 'yellow', variant: 'light' };
    if (score >= 0.3) return { color: 'orange', variant: 'light' };
    return { color: 'red', variant: 'light' };
  };

  /**
   * Gets badge color class for priority score value
   *
   * Priority ranges:
   * - >= 80: green (high priority)
   * - >= 60: yellow (medium-high)
   * - >= 40: orange (medium-low)
   * - < 40: red (low priority)
   *
   * @param {number} score - Priority score (0-100)
   * @returns {Object} Badge props with color and variant
   */
  const getPriorityClass = (score) => {
    if (score >= 80) return { color: 'green', variant: 'light' };
    if (score >= 60) return { color: 'yellow', variant: 'light' };
    if (score >= 40) return { color: 'orange', variant: 'light' };
    return { color: 'red', variant: 'light' };
  };

  /**
   * Formats score as percentage string
   *
   * @param {number|null|undefined} score - Score value (0.0 to 1.0)
   * @returns {string} Formatted score (e.g., "85.5") or "-" for invalid values
   */
  const formatScore = (score) => {
    if (score == null || isNaN(score)) return '-';
    return (score * 100).toFixed(1);
  };

  /**
   * Formats priority score as integer string
   *
   * @param {number|null|undefined} priority - Priority score (0-100)
   * @returns {string} Formatted priority (e.g., "85") or "-" for invalid values
   */
  const formatPriority = (priority) => {
    if (priority == null || isNaN(priority)) return '-';
    return priority.toFixed(0);
  };

  /**
   * Calculates the number of visible columns for colSpan in empty state
   *
   * Symbol and Actions columns are always visible.
   *
   * @returns {number} Count of visible columns
   */
  const getVisibleColumnCount = () => {
    let count = 2; // Symbol and Actions are always visible
    if (visibleColumns.chart) count++;
    if (visibleColumns.company) count++;
    if (visibleColumns.geography) count++;
    if (visibleColumns.exchange) count++;
    if (visibleColumns.sector) count++;
    if (visibleColumns.tags) count++;
    if (visibleColumns.qty) count++;
    if (visibleColumns.price) count++;
    if (visibleColumns.value) count++;
    if (visibleColumns.score) count++;
    if (visibleColumns.mult) count++;
    if (visibleColumns.rating) count++;
    if (visibleColumns.bs) count++;
    if (visibleColumns.priority) count++;
    return count;
  };

  const visibleColumnCount = getVisibleColumnCount();

  return (
    <Card className="security-table" p="md">
      {/* Header with title and action buttons */}
      <Group className="security-table__header" justify="space-between" mb="md">
        <Text className="security-table__title" size="xs" tt="uppercase" c="dimmed" fw={600}>
          Security Universe
        </Text>
        <Group className="security-table__header-actions" gap="xs">
          {/* Column visibility menu */}
          <Menu width={200}>
            <Menu.Target>
              <ActionIcon className="security-table__columns-btn" variant="subtle" size="sm" title="Column visibility">
                <IconColumns size={16} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown className="security-table__columns-dropdown">
              <Menu.Label>Show Columns</Menu.Label>
              {/* Column toggle menu items - checkmark indicates visible column */}
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.chart ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('chart')}
              >
                Chart
              </Menu.Item>
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.company ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('company')}
              >
                Company
              </Menu.Item>
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.geography ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('geography')}
              >
                Geography
              </Menu.Item>
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.exchange ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('exchange')}
              >
                Exchange
              </Menu.Item>
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.sector ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('sector')}
              >
                Sector
              </Menu.Item>
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.tags ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('tags')}
              >
                Tags
              </Menu.Item>
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.qty ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('qty')}
              >
                Qty
              </Menu.Item>
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.price ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('price')}
              >
                Price
              </Menu.Item>
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.value ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('value')}
              >
                Value
              </Menu.Item>
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.score ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('score')}
              >
                Score
              </Menu.Item>
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.mult ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('mult')}
              >
                Mult
              </Menu.Item>
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.rating ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('rating')}
              >
                Rating
              </Menu.Item>
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.bs ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('bs')}
              >
                B/S
              </Menu.Item>
              <Menu.Item
                className="security-table__column-toggle"
                leftSection={visibleColumns.priority ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('priority')}
              >
                Priority
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
          {/* Add security button */}
          <Button className="security-table__add-btn" size="xs" onClick={openAddSecurityModal}>
            + Add Security
          </Button>
        </Group>
      </Group>

      {/* Filter Bar - search, geography, industry, score, and sparkline timeframe */}
      <Group className="security-table__filters" gap="xs" mb="md" wrap="wrap">
        {/* Search input - filters by symbol or name */}
        <TextInput
          className="security-table__search"
          placeholder="Search symbol or name..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ flex: 1, minWidth: '200px' }}
          size="xs"
        />
        {/* Geography filter dropdown */}
        <Select
          className="security-table__geography-filter"
          placeholder="All Geographies"
          data={['all', ...geographies]}
          value={securityFilter}
          onChange={setSecurityFilter}
          size="xs"
          style={{ width: '150px' }}
        />
        {/* Industry/sector filter dropdown */}
        <Select
          className="security-table__sector-filter"
          placeholder="All Sectors"
          data={['all', ...industries]}
          value={industryFilter}
          onChange={setIndustryFilter}
          size="xs"
          style={{ width: '150px' }}
        />
        {/* Minimum score filter */}
        <Select
          className="security-table__score-filter"
          placeholder="Any Score"
          data={[
            { value: '0', label: 'Any Score' },
            { value: '0.3', label: 'Score >= 0.3' },
            { value: '0.5', label: 'Score >= 0.5' },
            { value: '0.7', label: 'Score >= 0.7' },
          ]}
          value={minScore.toString()}
          onChange={(val) => setMinScore(parseFloat(val || '0'))}
          size="xs"
          style={{ width: '120px' }}
        />
        {/* Sparkline timeframe selector (1Y or 5Y) */}
        <SegmentedControl
          className="security-table__timeframe"
          value={sparklineTimeframe}
          onChange={setSparklineTimeframe}
          data={[
            { label: '1 Year', value: '1Y' },
            { label: '5 Years', value: '5Y' },
          ]}
          size="xs"
        />
      </Group>

      {/* Results count - shows filtered vs total */}
      {securities.length > 0 && (
        <Text className="security-table__count" size="xs" c="dimmed" mb="xs">
          {filteredSecurities.length} of {securities.length} securities
        </Text>
      )}

      {/* Table with horizontal scroll support */}
      <div className="security-table__wrapper" style={{ overflowX: 'auto' }}>
        <Table className="security-table__table" highlightOnHover>
          <Table.Thead className="security-table__thead">
            <Table.Tr className="security-table__header-row">
              {/* Symbol column - sticky on left, sortable */}
              <Table.Th className="security-table__th security-table__th--symbol" style={{ position: 'sticky', left: 0, backgroundColor: 'var(--mantine-color-body)', zIndex: 10 }}>
                <Text
                  className="security-table__sort-label"
                  size="xs"
                  style={{ cursor: 'pointer' }}
                  onClick={() => handleSort('symbol')}
                >
                  Symbol {sortBy === 'symbol' && (sortDesc ? '▼' : '▲')}
                </Text>
              </Table.Th>
              {visibleColumns.chart && <Table.Th className="security-table__th security-table__th--chart">Chart</Table.Th>}
              {visibleColumns.company && (
                <Table.Th className="security-table__th security-table__th--company">
                  <Text
                    className="security-table__sort-label"
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('name')}
                  >
                    Company {sortBy === 'name' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.geography && (
                <Table.Th className="security-table__th security-table__th--geography">
                  <Text
                    className="security-table__sort-label"
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('geography')}
                  >
                    Geography {sortBy === 'geography' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.exchange && (
                <Table.Th className="security-table__th security-table__th--exchange">
                  <Text
                    className="security-table__sort-label"
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('fullExchangeName')}
                  >
                    Exchange {sortBy === 'fullExchangeName' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.sector && (
                <Table.Th className="security-table__th security-table__th--sector">
                  <Text
                    className="security-table__sort-label"
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('industry')}
                  >
                    Sector {sortBy === 'industry' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.tags && <Table.Th className="security-table__th security-table__th--tags">Tags</Table.Th>}
              {visibleColumns.qty && (
                <Table.Th className="security-table__th security-table__th--qty" ta="right">
                  <Text
                    className="security-table__sort-label"
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('position_quantity')}
                  >
                    Qty {sortBy === 'position_quantity' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.price && (
                <Table.Th className="security-table__th security-table__th--price" ta="right">
                  <Text
                    className="security-table__sort-label"
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('current_price')}
                  >
                    Price {sortBy === 'current_price' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.value && (
                <Table.Th className="security-table__th security-table__th--value" ta="right">
                  <Text
                    className="security-table__sort-label"
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('position_value')}
                  >
                    Value {sortBy === 'position_value' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.score && (
                <Table.Th className="security-table__th security-table__th--score" ta="right">
                  <Text
                    className="security-table__sort-label"
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('total_score')}
                  >
                    Score {sortBy === 'total_score' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.mult && <Table.Th className="security-table__th security-table__th--mult" ta="center">Mult</Table.Th>}
              {visibleColumns.rating && <Table.Th className="security-table__th security-table__th--rating" ta="center">Rating</Table.Th>}
              {visibleColumns.bs && <Table.Th className="security-table__th security-table__th--bs" ta="center">B/S</Table.Th>}
              {visibleColumns.priority && (
                <Table.Th className="security-table__th security-table__th--priority" ta="right">
                  <Text
                    className="security-table__sort-label"
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('priority_score')}
                  >
                    Priority {sortBy === 'priority_score' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              <Table.Th className="security-table__th security-table__th--actions" ta="center">Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody className="security-table__tbody">
            {filteredSecurities.length === 0 && securities.length > 0 && (
              <Table.Tr className="security-table__empty-row">
                <Table.Td colSpan={visibleColumnCount} ta="center" py="xl">
                  <Text className="security-table__empty-message" c="dimmed" size="sm">No securities match your filters</Text>
                </Table.Td>
              </Table.Tr>
            )}
            {securities.length === 0 && (
              <Table.Tr className="security-table__empty-row">
                <Table.Td colSpan={visibleColumnCount} ta="center" py="xl">
                  <Text className="security-table__empty-message" c="dimmed" size="sm">No securities in universe</Text>
                </Table.Td>
              </Table.Tr>
            )}
            {/* Table rows for each filtered security */}
            {filteredSecurities.map((security) => {
              // Check for concentration alert for this security
              const alert = getPositionAlert(security.symbol);
              return (
                <Table.Tr
                  className={`security-table__row ${alert ? `security-table__row--${alert.severity}` : ''}`}
                  key={security.symbol}
                  style={{
                    // Left border indicates concentration alert (red for critical, yellow for warning)
                    borderLeft: alert
                      ? `4px solid ${alert.severity === 'critical' ? 'var(--mantine-color-red-5)' : 'var(--mantine-color-yellow-5)'}`
                      : undefined,
                  }}
                >
                  {/* Symbol column - sticky, clickable to open chart */}
                  <Table.Td className="security-table__td security-table__td--symbol" style={{ position: 'sticky', left: 0, backgroundColor: 'var(--mantine-color-body)', zIndex: 5 }}>
                    <Text
                      className="security-table__symbol-link"
                      size="sm"
                      style={{ fontFamily: 'var(--mantine-font-family)', cursor: 'pointer' }}
                      c="blue"
                      onClick={() => {
                        // Open security chart modal
                        useAppStore.getState().openSecurityChart(security.symbol, security.isin);
                      }}
                    >
                      {security.symbol}
                    </Text>
                  </Table.Td>
                  {/* Sparkline chart column - shows price trend */}
                  {visibleColumns.chart && (
                    <Table.Td className="security-table__td security-table__td--chart">
                      {sparklinesLoading ? (
                        <Skeleton height={32} width={80} />
                      ) : (
                        <SecuritySparkline
                          symbol={security.symbol}
                          hasPosition={security.position_value > 0}
                          avgPrice={security.avg_price}
                          currentPrice={security.current_price}
                        />
                      )}
                    </Table.Td>
                  )}
                  {visibleColumns.company && (
                    <Table.Td className="security-table__td security-table__td--company">
                      <Text className="security-table__company-name" size="sm" truncate style={{ maxWidth: '128px' }}>
                        {security.name}
                      </Text>
                    </Table.Td>
                  )}
                  {visibleColumns.geography && (
                    <Table.Td className="security-table__td security-table__td--geography">
                      <Text className="security-table__geography" size="sm" c="dimmed" truncate style={{ maxWidth: '96px' }}>
                        {security.geography || '-'}
                      </Text>
                    </Table.Td>
                  )}
                  {visibleColumns.exchange && (
                    <Table.Td className="security-table__td security-table__td--exchange">
                      <Text className="security-table__exchange" size="sm" c="dimmed" truncate style={{ maxWidth: '96px' }}>
                        {security.fullExchangeName || '-'}
                      </Text>
                    </Table.Td>
                  )}
                  {visibleColumns.sector && (
                    <Table.Td className="security-table__td security-table__td--sector">
                      <Text className="security-table__sector" size="sm" c="dimmed" truncate style={{ maxWidth: '96px' }}>
                        {security.industry || '-'}
                      </Text>
                    </Table.Td>
                  )}
                  {/* Tags column - displays security tags with color coding */}
                  {visibleColumns.tags && (
                    <Table.Td className="security-table__td security-table__td--tags">
                      {security.tags && security.tags.length > 0 ? (
                        <Group className="security-table__tags" gap="xs" wrap="wrap">
                          {security.tags.map((tagId) => (
                            <Badge
                              className="security-table__tag"
                              key={tagId}
                              size="xs"
                              {...getTagColor(tagId)}  // Color based on tag category
                              title={tagId}
                            >
                              {getTagName(tagId)}
                            </Badge>
                          ))}
                        </Group>
                      ) : (
                        <Text className="security-table__no-tags" size="sm" c="dimmed">-</Text>
                      )}
                    </Table.Td>
                  )}
                  {/* Qty column - displays position quantity as integer */}
                  {visibleColumns.qty && (
                    <Table.Td className="security-table__td security-table__td--qty" ta="right">
                      <Text className="security-table__qty" size="sm" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                        {security.position_quantity ? formatNumber(security.position_quantity, 0) : '-'}
                      </Text>
                    </Table.Td>
                  )}
                  {/* Price column - displays current price with currency formatting */}
                  {visibleColumns.price && (
                    <Table.Td className="security-table__td security-table__td--price" ta="right">
                      <Text className="security-table__price" size="sm" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                        {security.current_price ? formatCurrency(security.current_price, security.currency || 'EUR') : '-'}
                      </Text>
                    </Table.Td>
                  )}
                  {/* Value column - position value with concentration alert indicator */}
                  {visibleColumns.value && (
                    <Table.Td className="security-table__td security-table__td--value" ta="right">
                      <Group className="security-table__value-group" gap="xs" justify="flex-end">
                        <Text className="security-table__value" size="sm" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                          {security.position_value ? formatCurrency(security.position_value) : '-'}
                        </Text>
                        {/* Concentration alert icon - red circle for critical, yellow warning for warning */}
                        {alert && (
                          <Text
                            className={`security-table__alert-icon security-table__alert-icon--${alert.severity}`}
                            size="xs"
                            c={alert.severity === 'critical' ? 'red' : 'yellow'}
                            title={`Position concentration: ${(alert.current_pct * 100).toFixed(1)}% (Limit: ${(alert.limit_pct * 100).toFixed(0)}%)`}
                          >
                            {alert.severity === 'critical' ? '🔴' : '⚠️'}
                          </Text>
                        )}
                      </Group>
                    </Table.Td>
                  )}
                  {visibleColumns.score && (
                    <Table.Td className="security-table__td security-table__td--score" ta="right">
                      <Badge className="security-table__score-badge" size="sm" {...getScoreClass(security.total_score)}>
                        {formatScore(security.total_score)}
                      </Badge>
                    </Table.Td>
                  )}
                  {/* Multiplier column - inline editing of priority multiplier */}
                  {visibleColumns.mult && (
                    <Table.Td className="security-table__td security-table__td--mult" ta="center">
                      <NumberInput
                        className="security-table__mult-input"
                        size="xs"
                        value={security.priority_multiplier || 1}
                        min={0.1}
                        max={3}
                        step={0.1}
                        onChange={(val) => updateMultiplier(security.isin, val)}
                        style={{ width: '60px' }}
                      />
                    </Table.Td>
                  )}
                  {/* Rating column - visual icon-based multiplier control */}
                  {visibleColumns.rating && (
                    <Table.Td className="security-table__td security-table__td--rating" ta="center">
                      <RatingIcon
                        isin={security.isin}
                        currentMultiplier={security.priority_multiplier || 1.0}
                      />
                    </Table.Td>
                  )}
                  {/* Buy/Sell indicators - shows which actions are allowed */}
                  {visibleColumns.bs && (
                    <Table.Td className="security-table__td security-table__td--bs" ta="center">
                      <Group className="security-table__bs-indicators" gap="xs" justify="center">
                        {/* Green dot = buy enabled */}
                        {security.allow_buy && (
                          <div
                            className="security-table__bs-indicator security-table__bs-indicator--buy"
                            style={{
                              width: '10px',
                              height: '10px',
                              borderRadius: '50%',
                              backgroundColor: 'var(--mantine-color-green-5)',
                            }}
                            title="Buy enabled"
                          />
                        )}
                        {/* Red dot = sell enabled */}
                        {security.allow_sell && (
                          <div
                            className="security-table__bs-indicator security-table__bs-indicator--sell"
                            style={{
                              width: '10px',
                              height: '10px',
                              borderRadius: '50%',
                              backgroundColor: 'var(--mantine-color-red-5)',
                            }}
                            title="Sell enabled"
                          />
                        )}
                        {/* Dash if neither buy nor sell is enabled */}
                        {!security.allow_buy && !security.allow_sell && <Text c="dimmed">-</Text>}
                      </Group>
                    </Table.Td>
                  )}
                  {visibleColumns.priority && (
                    <Table.Td className="security-table__td security-table__td--priority" ta="right">
                      <Badge className="security-table__priority-badge" size="sm" {...getPriorityClass(security.priority_score)}>
                        {formatPriority(security.priority_score)}
                      </Badge>
                    </Table.Td>
                  )}
                  {/* Actions column - edit, refresh score, remove */}
                  <Table.Td className="security-table__td security-table__td--actions" ta="center">
                    <Group className="security-table__actions" gap="xs" justify="center">
                      {/* Edit security button */}
                      <ActionIcon
                        className="security-table__action-btn security-table__action-btn--edit"
                        size="sm"
                        variant="subtle"
                        onClick={() => openEditSecurityModal(security)}
                        title="Edit security"
                      >
                        <IconEdit size={14} />
                      </ActionIcon>
                      {/* Refresh score button - triggers score recalculation */}
                      <ActionIcon
                        className="security-table__action-btn security-table__action-btn--refresh"
                        size="sm"
                        variant="subtle"
                        onClick={() => refreshScore(security.isin)}
                        title="Refresh score"
                      >
                        <IconRefresh size={14} />
                      </ActionIcon>
                      {/* Remove security button - removes from investment universe */}
                      <ActionIcon
                        className="security-table__action-btn security-table__action-btn--remove"
                        size="sm"
                        variant="subtle"
                        color="red"
                        onClick={() => removeSecurity(security.isin)}
                        title="Remove from universe"
                      >
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Group>
                  </Table.Td>
                </Table.Tr>
              );
            })}
          </Table.Tbody>
        </Table>
      </div>
    </Card>
  );
}
