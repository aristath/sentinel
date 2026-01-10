import { Card, Table, TextInput, Select, Group, Button, Text, ActionIcon, Badge, NumberInput, Menu, SegmentedControl, Skeleton } from '@mantine/core';
import { IconEdit, IconRefresh, IconTrash, IconColumns, IconCheck } from '@tabler/icons-react';
import { useSecuritiesStore } from '../../stores/securitiesStore';
import { useAppStore } from '../../stores/appStore';
import { usePortfolioStore } from '../../stores/portfolioStore';
import { SecuritySparkline } from '../charts/SecuritySparkline';
import { formatCurrency } from '../../utils/formatters';
import { getTagName, getTagColor } from '../../utils/tagNames';
import { useEffect, useState } from 'react';

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

  // Load column visibility on mount
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

  const filteredSecurities = getFilteredSecurities();
  const countries = [...new Set(securities.map(s => s.country).filter(Boolean))].sort();
  const industries = [...new Set(securities.map(s => s.industry).filter(Boolean))].sort();

  const handleSort = (field) => {
    if (sortBy === field) {
      setSortBy(field, !sortDesc);
    } else {
      setSortBy(field, true);
    }
  };

  const getPositionAlert = (symbol) => {
    return alerts.find(a => a.type === 'security' && a.name === symbol);
  };

  const getScoreClass = (score) => {
    if (score >= 0.7) return { color: 'green', variant: 'light' };
    if (score >= 0.5) return { color: 'yellow', variant: 'light' };
    if (score >= 0.3) return { color: 'orange', variant: 'light' };
    return { color: 'red', variant: 'light' };
  };

  const getPriorityClass = (score) => {
    if (score >= 80) return { color: 'green', variant: 'light' };
    if (score >= 60) return { color: 'yellow', variant: 'light' };
    if (score >= 40) return { color: 'orange', variant: 'light' };
    return { color: 'red', variant: 'light' };
  };

  const formatScore = (score) => {
    if (score == null || isNaN(score)) return '-';
    return (score * 100).toFixed(1);
  };

  const formatPriority = (priority) => {
    if (priority == null || isNaN(priority)) return '-';
    return priority.toFixed(0);
  };

  // Calculate visible column count for colSpan
  const getVisibleColumnCount = () => {
    let count = 2; // Symbol and Actions are always visible
    if (visibleColumns.chart) count++;
    if (visibleColumns.company) count++;
    if (visibleColumns.country) count++;
    if (visibleColumns.exchange) count++;
    if (visibleColumns.sector) count++;
    if (visibleColumns.tags) count++;
    if (visibleColumns.value) count++;
    if (visibleColumns.score) count++;
    if (visibleColumns.mult) count++;
    if (visibleColumns.bs) count++;
    if (visibleColumns.priority) count++;
    return count;
  };

  const visibleColumnCount = getVisibleColumnCount();

  return (
    <Card p="md">
      <Group justify="space-between" mb="md">
        <Text size="xs" tt="uppercase" c="dimmed" fw={600}>
          Security Universe
        </Text>
        <Group gap="xs">
          <Menu width={200}>
            <Menu.Target>
              <ActionIcon variant="subtle" size="sm" title="Column visibility">
                <IconColumns size={16} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Label>Show Columns</Menu.Label>
              <Menu.Item
                leftSection={visibleColumns.chart ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('chart')}
              >
                Chart
              </Menu.Item>
              <Menu.Item
                leftSection={visibleColumns.company ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('company')}
              >
                Company
              </Menu.Item>
              <Menu.Item
                leftSection={visibleColumns.country ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('country')}
              >
                Country
              </Menu.Item>
              <Menu.Item
                leftSection={visibleColumns.exchange ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('exchange')}
              >
                Exchange
              </Menu.Item>
              <Menu.Item
                leftSection={visibleColumns.sector ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('sector')}
              >
                Sector
              </Menu.Item>
              <Menu.Item
                leftSection={visibleColumns.tags ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('tags')}
              >
                Tags
              </Menu.Item>
              <Menu.Item
                leftSection={visibleColumns.value ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('value')}
              >
                Value
              </Menu.Item>
              <Menu.Item
                leftSection={visibleColumns.score ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('score')}
              >
                Score
              </Menu.Item>
              <Menu.Item
                leftSection={visibleColumns.mult ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('mult')}
              >
                Mult
              </Menu.Item>
              <Menu.Item
                leftSection={visibleColumns.bs ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('bs')}
              >
                B/S
              </Menu.Item>
              <Menu.Item
                leftSection={visibleColumns.priority ? <IconCheck size={14} /> : <span style={{ width: 14 }} />}
                onClick={() => toggleColumnVisibility('priority')}
              >
                Priority
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
          <Button size="xs" onClick={openAddSecurityModal}>
            + Add Security
          </Button>
        </Group>
      </Group>

      {/* Filter Bar */}
      <Group gap="xs" mb="md" wrap="wrap">
        <TextInput
          placeholder="Search symbol or name..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          style={{ flex: 1, minWidth: '200px' }}
          size="xs"
        />
        <Select
          placeholder="All Countries"
          data={['all', ...countries]}
          value={securityFilter}
          onChange={setSecurityFilter}
          size="xs"
          style={{ width: '150px' }}
        />
        <Select
          placeholder="All Sectors"
          data={['all', ...industries]}
          value={industryFilter}
          onChange={setIndustryFilter}
          size="xs"
          style={{ width: '150px' }}
        />
        <Select
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
        <SegmentedControl
          value={sparklineTimeframe}
          onChange={setSparklineTimeframe}
          data={[
            { label: '1 Year', value: '1Y' },
            { label: '5 Years', value: '5Y' },
          ]}
          size="xs"
        />
      </Group>

      {/* Results count */}
      {securities.length > 0 && (
        <Text size="xs" c="dimmed" mb="xs">
          {filteredSecurities.length} of {securities.length} securities
        </Text>
      )}

      {/* Table */}
      <div style={{ overflowX: 'auto' }}>
        <Table highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th style={{ position: 'sticky', left: 0, backgroundColor: 'var(--mantine-color-body)', zIndex: 10 }}>
                <Text
                  size="xs"
                  style={{ cursor: 'pointer' }}
                  onClick={() => handleSort('symbol')}
                >
                  Symbol {sortBy === 'symbol' && (sortDesc ? '▼' : '▲')}
                </Text>
              </Table.Th>
              {visibleColumns.chart && <Table.Th>Chart</Table.Th>}
              {visibleColumns.company && (
                <Table.Th>
                  <Text
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('name')}
                  >
                    Company {sortBy === 'name' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.country && (
                <Table.Th>
                  <Text
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('country')}
                  >
                    Country {sortBy === 'country' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.exchange && (
                <Table.Th>
                  <Text
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('fullExchangeName')}
                  >
                    Exchange {sortBy === 'fullExchangeName' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.sector && (
                <Table.Th>
                  <Text
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('industry')}
                  >
                    Sector {sortBy === 'industry' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.tags && <Table.Th>Tags</Table.Th>}
              {visibleColumns.value && (
                <Table.Th ta="right">
                  <Text
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('position_value')}
                  >
                    Value {sortBy === 'position_value' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.score && (
                <Table.Th ta="right">
                  <Text
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('total_score')}
                  >
                    Score {sortBy === 'total_score' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              {visibleColumns.mult && <Table.Th ta="center">Mult</Table.Th>}
              {visibleColumns.bs && <Table.Th ta="center">B/S</Table.Th>}
              {visibleColumns.priority && (
                <Table.Th ta="right">
                  <Text
                    size="xs"
                    style={{ cursor: 'pointer' }}
                    onClick={() => handleSort('priority_score')}
                  >
                    Priority {sortBy === 'priority_score' && (sortDesc ? '▼' : '▲')}
                  </Text>
                </Table.Th>
              )}
              <Table.Th ta="center">Actions</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {filteredSecurities.length === 0 && securities.length > 0 && (
              <Table.Tr>
                <Table.Td colSpan={visibleColumnCount} ta="center" py="xl">
                  <Text c="dimmed" size="sm">No securities match your filters</Text>
                </Table.Td>
              </Table.Tr>
            )}
            {securities.length === 0 && (
              <Table.Tr>
                <Table.Td colSpan={visibleColumnCount} ta="center" py="xl">
                  <Text c="dimmed" size="sm">No securities in universe</Text>
                </Table.Td>
              </Table.Tr>
            )}
            {filteredSecurities.map((security) => {
              const alert = getPositionAlert(security.symbol);
              return (
                <Table.Tr
                  key={security.symbol}
                  style={{
                    borderLeft: alert
                      ? `4px solid ${alert.severity === 'critical' ? 'var(--mantine-color-red-5)' : 'var(--mantine-color-yellow-5)'}`
                      : undefined,
                  }}
                >
                  <Table.Td style={{ position: 'sticky', left: 0, backgroundColor: 'var(--mantine-color-body)', zIndex: 5 }}>
                    <Text
                      size="sm"
                      style={{ fontFamily: 'var(--mantine-font-family)', cursor: 'pointer' }}
                      c="blue"
                      onClick={() => {
                        useAppStore.getState().openSecurityChart(security.symbol, security.isin);
                      }}
                    >
                      {security.symbol}
                    </Text>
                  </Table.Td>
                  {visibleColumns.chart && (
                    <Table.Td>
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
                    <Table.Td>
                      <Text size="sm" truncate style={{ maxWidth: '128px' }}>
                        {security.name}
                      </Text>
                    </Table.Td>
                  )}
                  {visibleColumns.country && (
                    <Table.Td>
                      <Text size="sm" c="dimmed" truncate style={{ maxWidth: '96px' }}>
                        {security.country || '-'}
                      </Text>
                    </Table.Td>
                  )}
                  {visibleColumns.exchange && (
                    <Table.Td>
                      <Text size="sm" c="dimmed" truncate style={{ maxWidth: '96px' }}>
                        {security.fullExchangeName || '-'}
                      </Text>
                    </Table.Td>
                  )}
                  {visibleColumns.sector && (
                    <Table.Td>
                      <Text size="sm" c="dimmed" truncate style={{ maxWidth: '96px' }}>
                        {security.industry || '-'}
                      </Text>
                    </Table.Td>
                  )}
                  {visibleColumns.tags && (
                    <Table.Td>
                      {security.tags && security.tags.length > 0 ? (
                        <Group gap="xs" wrap="wrap">
                          {security.tags.map((tagId) => (
                            <Badge
                              key={tagId}
                              size="xs"
                              {...getTagColor(tagId)}
                              title={tagId}
                            >
                              {getTagName(tagId)}
                            </Badge>
                          ))}
                        </Group>
                      ) : (
                        <Text size="sm" c="dimmed">-</Text>
                      )}
                    </Table.Td>
                  )}
                  {visibleColumns.value && (
                    <Table.Td ta="right">
                      <Group gap="xs" justify="flex-end">
                        <Text size="sm" style={{ fontFamily: 'var(--mantine-font-family)' }}>
                          {security.position_value ? formatCurrency(security.position_value) : '-'}
                        </Text>
                        {alert && (
                          <Text
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
                    <Table.Td ta="right">
                      <Badge size="sm" {...getScoreClass(security.total_score)}>
                        {formatScore(security.total_score)}
                      </Badge>
                    </Table.Td>
                  )}
                  {visibleColumns.mult && (
                    <Table.Td ta="center">
                      <NumberInput
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
                  {visibleColumns.bs && (
                    <Table.Td ta="center">
                      <Group gap="xs" justify="center">
                        {security.allow_buy && (
                          <div
                            style={{
                              width: '10px',
                              height: '10px',
                              borderRadius: '50%',
                              backgroundColor: 'var(--mantine-color-green-5)',
                            }}
                            title="Buy enabled"
                          />
                        )}
                        {security.allow_sell && (
                          <div
                            style={{
                              width: '10px',
                              height: '10px',
                              borderRadius: '50%',
                              backgroundColor: 'var(--mantine-color-red-5)',
                            }}
                            title="Sell enabled"
                          />
                        )}
                        {!security.allow_buy && !security.allow_sell && <Text c="dimmed">-</Text>}
                      </Group>
                    </Table.Td>
                  )}
                  {visibleColumns.priority && (
                    <Table.Td ta="right">
                      <Badge size="sm" {...getPriorityClass(security.priority_score)}>
                        {formatPriority(security.priority_score)}
                      </Badge>
                    </Table.Td>
                  )}
                  <Table.Td ta="center">
                    <Group gap="xs" justify="center">
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        onClick={() => openEditSecurityModal(security)}
                        title="Edit security"
                      >
                        <IconEdit size={14} />
                      </ActionIcon>
                      <ActionIcon
                        size="sm"
                        variant="subtle"
                        onClick={() => refreshScore(security.isin)}
                        title="Refresh score"
                      >
                        <IconRefresh size={14} />
                      </ActionIcon>
                      <ActionIcon
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
