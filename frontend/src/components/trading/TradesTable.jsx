import { Card, Table, Text, Badge, Group } from '@mantine/core';
import { useTradesStore } from '../../stores/tradesStore';
import { formatCurrency, formatDateTime } from '../../utils/formatters';

export function TradesTable() {
  const { trades, pendingOrders } = useTradesStore();

  const hasPending = pendingOrders.length > 0;
  const hasData = trades.length > 0 || hasPending;

  return (
    <Card p="md" style={{ backgroundColor: 'var(--mantine-color-dark-7)', border: '1px solid var(--mantine-color-dark-6)' }}>
      <Group justify="space-between" mb="md">
        <Text size="xs" tt="uppercase" c="dimmed" fw={600} style={{ fontFamily: 'var(--mantine-font-family)' }}>
          Recent Trades
        </Text>
        {hasPending && (
          <Badge size="sm" color="yellow" variant="light">
            {pendingOrders.length} pending
          </Badge>
        )}
      </Group>

      {!hasData ? (
        <Text c="dimmed" size="sm" ta="center" py="xl">
          No trades yet
        </Text>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <Table highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Date</Table.Th>
                <Table.Th>Symbol</Table.Th>
                <Table.Th visibleFrom="sm">Name</Table.Th>
                <Table.Th>Side</Table.Th>
                <Table.Th ta="right">Qty</Table.Th>
                <Table.Th ta="right" visibleFrom="sm">Price</Table.Th>
                <Table.Th ta="right">Value</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {/* Pending orders first */}
              {pendingOrders.map((order) => {
                const isCash = order.symbol.includes('/');
                return (
                  <Table.Tr
                    key={`pending-${order.order_id}`}
                    style={{
                      backgroundColor: 'rgba(255, 193, 7, 0.1)',
                    }}
                  >
                    <Table.Td>
                      <Badge size="xs" color="yellow" variant="filled">
                        PENDING
                      </Badge>
                    </Table.Td>
                    <Table.Td>
                      <Text
                        size="sm"
                        style={{ fontFamily: 'var(--mantine-font-family)' }}
                        c={isCash ? 'violet' : 'yellow'}
                      >
                        {order.symbol}
                      </Text>
                    </Table.Td>
                    <Table.Td visibleFrom="sm">
                      <Text
                        size="sm"
                        c="dimmed"
                        truncate
                        style={{ maxWidth: '128px', fontFamily: 'var(--mantine-font-family)' }}
                      >
                        {order.symbol}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge
                        size="sm"
                        color={order.side === 'BUY' ? 'green' : 'red'}
                        variant="light"
                        style={{ fontFamily: 'var(--mantine-font-family)' }}
                      >
                        {order.side}
                      </Badge>
                    </Table.Td>
                    <Table.Td ta="right">
                      <Text size="sm" style={{ fontFamily: 'var(--mantine-font-family)' }} c="dimmed">
                        {formatCurrency(order.quantity)}
                      </Text>
                    </Table.Td>
                    <Table.Td ta="right" visibleFrom="sm">
                      <Text size="sm" style={{ fontFamily: 'var(--mantine-font-family)' }} c="dimmed">
                        {formatCurrency(order.price)}
                      </Text>
                    </Table.Td>
                    <Table.Td ta="right">
                      <Text size="sm" style={{ fontFamily: 'var(--mantine-font-family)' }} fw={600}>
                        {formatCurrency(order.quantity * order.price)}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
              {/* Executed trades */}
              {trades.map((trade) => {
                const isCash = trade.symbol.includes('/');
                return (
                  <Table.Tr
                    key={trade.id}
                    style={{
                      backgroundColor: isCash ? 'var(--mantine-color-dark-8)' : undefined,
                    }}
                  >
                    <Table.Td>
                      <Text size="sm" c="dimmed">
                        {formatDateTime(trade.executed_at)}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Text
                        size="sm"
                        style={{ fontFamily: 'var(--mantine-font-family)' }}
                        c={isCash ? 'violet' : 'blue'}
                      >
                        {trade.symbol}
                      </Text>
                    </Table.Td>
                    <Table.Td visibleFrom="sm">
                      <Text
                        size="sm"
                        c={isCash ? 'violet' : 'dimmed'}
                        truncate
                        style={{ maxWidth: '128px', fontFamily: 'var(--mantine-font-family)' }}
                      >
                        {trade.name || trade.symbol}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Badge
                        size="sm"
                        color={trade.side === 'BUY' ? 'green' : 'red'}
                        variant="light"
                        style={{ fontFamily: 'var(--mantine-font-family)' }}
                      >
                        {trade.side}
                      </Badge>
                    </Table.Td>
                    <Table.Td ta="right">
                      <Text size="sm" style={{ fontFamily: 'var(--mantine-font-family)' }} c="dimmed">
                        {formatCurrency(trade.quantity)}
                      </Text>
                    </Table.Td>
                    <Table.Td ta="right" visibleFrom="sm">
                      <Text size="sm" style={{ fontFamily: 'var(--mantine-font-family)' }} c="dimmed">
                        {formatCurrency(trade.price)}
                      </Text>
                    </Table.Td>
                    <Table.Td ta="right">
                      <Text size="sm" style={{ fontFamily: 'var(--mantine-font-family)' }} fw={600}>
                        {formatCurrency(trade.quantity * trade.price)}
                      </Text>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </div>
      )}
    </Card>
  );
}
