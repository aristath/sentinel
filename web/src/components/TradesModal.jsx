import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Modal,
  Stack,
  Text,
  Badge,
  Button,
  Loader,
  Center,
  Group,
  Select,
  Table,
  ScrollArea,
  Pagination,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconRefresh } from '@tabler/icons-react';
import { useState } from 'react';
import { getTrades, syncTrades, getSecurities } from '../api/client';
import { formatNumber } from '../utils/formatting';

function formatDate(dateStr) {
  if (!dateStr) return '-';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function TradesModal({ opened, onClose }) {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({
    symbol: null,
    side: null,
    startDate: null,
    endDate: null,
  });
  const pageSize = 20;

  const { data: securitiesData } = useQuery({
    queryKey: ['securities'],
    queryFn: getSecurities,
    staleTime: 60000,
  });

  const symbolOptions = securitiesData
    ? [{ value: '', label: 'All symbols' }, ...securitiesData.map(s => ({ value: s.symbol, label: s.symbol }))]
    : [{ value: '', label: 'All symbols' }];

  const { data, isLoading, error } = useQuery({
    queryKey: ['trades', page, filters],
    queryFn: () => getTrades({
      symbol: filters.symbol || undefined,
      side: filters.side || undefined,
      start_date: filters.startDate ? filters.startDate.toISOString().split('T')[0] : undefined,
      end_date: filters.endDate ? filters.endDate.toISOString().split('T')[0] : undefined,
      limit: pageSize,
      offset: (page - 1) * pageSize,
    }),
    enabled: opened,
    refetchInterval: 30000,
  });

  const syncMutation = useMutation({
    mutationFn: syncTrades,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trades'] });
    },
  });

  const trades = data?.trades || [];
  const totalCount = data?.total || 0;  // Use total count for pagination
  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
    setPage(1);
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title="Trade History"
      size="xl"
      className="trades-modal"
    >
      <Stack gap="md">
        <Group justify="space-between" align="flex-end">
          <Group gap="sm">
            <Select
              label="Symbol"
              placeholder="All"
              data={symbolOptions}
              value={filters.symbol || ''}
              onChange={(val) => handleFilterChange('symbol', val || null)}
              clearable
              searchable
              w={140}
              size="sm"
            />
            <Select
              label="Side"
              placeholder="All"
              data={[
                { value: '', label: 'All' },
                { value: 'BUY', label: 'Buy' },
                { value: 'SELL', label: 'Sell' },
              ]}
              value={filters.side || ''}
              onChange={(val) => handleFilterChange('side', val || null)}
              w={100}
              size="sm"
            />
            <DatePickerInput
              label="From"
              placeholder="Start date"
              value={filters.startDate}
              onChange={(val) => handleFilterChange('startDate', val)}
              clearable
              w={130}
              size="sm"
            />
            <DatePickerInput
              label="To"
              placeholder="End date"
              value={filters.endDate}
              onChange={(val) => handleFilterChange('endDate', val)}
              clearable
              w={130}
              size="sm"
            />
          </Group>
          <Button
            variant="light"
            size="sm"
            leftSection={<IconRefresh size={16} />}
            onClick={() => syncMutation.mutate()}
            loading={syncMutation.isPending}
          >
            Sync from Broker
          </Button>
        </Group>

        {isLoading ? (
          <Center py="xl">
            <Loader />
          </Center>
        ) : error ? (
          <Center py="xl">
            <Text c="red">Error loading trades: {error.message}</Text>
          </Center>
        ) : trades.length === 0 ? (
          <Center py="xl">
            <Text c="dimmed">No trades found</Text>
          </Center>
        ) : (
          <ScrollArea>
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Date</Table.Th>
                  <Table.Th>Symbol</Table.Th>
                  <Table.Th>Side</Table.Th>
                  <Table.Th ta="right">Qty</Table.Th>
                  <Table.Th ta="right">Price</Table.Th>
                  <Table.Th ta="right">Value</Table.Th>
                  <Table.Th ta="right">Commission</Table.Th>
                  <Table.Th>Currency</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {trades.map((trade) => {
                  const raw = trade.raw_data || {};
                  // Tradernet API field names: q=quantity, p=price, v=value, curr_c=currency
                  const qty = raw.q || 0;
                  const price = raw.p || 0;
                  const value = raw.v || (qty * price);
                  const commission = raw.commiss_exchange || 0;
                  const currency = raw.curr_c || '-';

                  return (
                    <Table.Tr key={trade.broker_trade_id}>
                      <Table.Td>{formatDate(trade.executed_at)}</Table.Td>
                      <Table.Td>
                        <Text size="sm" fw={500}>{trade.symbol}</Text>
                      </Table.Td>
                      <Table.Td>
                        <Badge
                          color={trade.side === 'BUY' ? 'green' : 'red'}
                          variant="light"
                          size="sm"
                        >
                          {trade.side}
                        </Badge>
                      </Table.Td>
                      <Table.Td ta="right">{formatNumber(qty, 0)}</Table.Td>
                      <Table.Td ta="right">{formatNumber(price, 2)}</Table.Td>
                      <Table.Td ta="right">{formatNumber(value, 2)}</Table.Td>
                      <Table.Td ta="right">{formatNumber(commission, 2)}</Table.Td>
                      <Table.Td>{currency}</Table.Td>
                    </Table.Tr>
                  );
                })}
              </Table.Tbody>
            </Table>
          </ScrollArea>
        )}

        {totalPages > 1 && (
          <Center>
            <Pagination
              value={page}
              onChange={setPage}
              total={totalPages}
              size="sm"
            />
          </Center>
        )}
      </Stack>
    </Modal>
  );
}
