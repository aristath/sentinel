import { useQuery } from '@tanstack/react-query';
import { Stack, Title, Card, Table, Text, Badge, Group, Loader, Center } from '@mantine/core';
import { getPortfolio } from '../api/client';
import { formatCurrency, formatPercent } from '../utils/formatting';

function PortfolioPage() {
  const { data: portfolio, isLoading, error } = useQuery({
    queryKey: ['portfolio'],
    queryFn: getPortfolio,
  });

  if (isLoading) {
    return (
      <Center h={200}>
        <Loader />
      </Center>
    );
  }

  if (error) {
    return (
      <Stack gap="lg">
        <Title order={2}>Portfolio</Title>
        <Card shadow="sm" padding="lg" withBorder>
          <Text c="red">Error loading portfolio: {error.message}</Text>
        </Card>
      </Stack>
    );
  }

  const positions = portfolio?.positions || [];
  const cash = portfolio?.cash || {};
  const totalValue = portfolio?.total_value_eur || 0;

  return (
    <Stack gap="lg" className="portfolio">
      <Group justify="space-between" className="portfolio__header">
        <Title order={2} className="portfolio__title">Portfolio</Title>
        <Text size="lg" fw={600} className="portfolio__total-value">
          Total: {formatCurrency(totalValue)}
        </Text>
      </Group>

      {/* Cash Balances */}
      <Card shadow="sm" padding="lg" withBorder className="portfolio__cash-card">
        <Group justify="space-between" mb="md" className="portfolio__cash-header">
          <Title order={4} className="portfolio__cash-title">Cash Balances</Title>
          <Text size="sm" fw={600} c="dimmed" className="portfolio__cash-total">
            Total: {formatCurrency(portfolio?.total_cash_eur || 0)}
          </Text>
        </Group>
        <Group gap="xl" className="portfolio__cash-balances">
          {Object.entries(cash).map(([currency, amount]) => (
            <div key={currency} className={`portfolio__cash-balance portfolio__cash-balance--${currency.toLowerCase()}`}>
              <Text size="sm" c="dimmed" tt="uppercase" className="portfolio__cash-currency">
                {currency}
              </Text>
              <Text size="lg" fw={600} className="portfolio__cash-amount">
                {formatCurrency(amount, currency)}
              </Text>
            </div>
          ))}
          {Object.keys(cash).length === 0 && (
            <Text c="dimmed" className="portfolio__no-cash">No cash balances</Text>
          )}
        </Group>
      </Card>

      {/* Positions */}
      <Card shadow="sm" padding="lg" withBorder className="portfolio__positions-card">
        <Title order={4} mb="md" className="portfolio__positions-title">Positions</Title>
        {positions.length === 0 ? (
          <Text c="dimmed" className="portfolio__no-positions">No positions</Text>
        ) : (
          <Table striped highlightOnHover className="portfolio__positions-table">
            <Table.Thead className="portfolio__table-head">
              <Table.Tr className="portfolio__table-header-row">
                <Table.Th className="portfolio__th portfolio__th--symbol">Symbol</Table.Th>
                <Table.Th className="portfolio__th portfolio__th--name">Name</Table.Th>
                <Table.Th ta="right" className="portfolio__th portfolio__th--quantity">Quantity</Table.Th>
                <Table.Th ta="right" className="portfolio__th portfolio__th--avg-cost">Avg Cost</Table.Th>
                <Table.Th ta="right" className="portfolio__th portfolio__th--price">Current Price</Table.Th>
                <Table.Th ta="right" className="portfolio__th portfolio__th--value">Value (EUR)</Table.Th>
                <Table.Th ta="right" className="portfolio__th portfolio__th--pnl">P/L %</Table.Th>
                <Table.Th ta="right" className="portfolio__th portfolio__th--weight">Weight</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody className="portfolio__table-body">
              {positions.map((pos) => {
                const profitPct = pos.profit_pct || 0;
                const weight = totalValue > 0 ? ((pos.value_eur || 0) / totalValue * 100) : 0;

                return (
                  <Table.Tr key={pos.symbol} className={`portfolio__position-row portfolio__position-row--${pos.symbol.toLowerCase().replace(/\./g, '-')}`}>
                    <Table.Td className="portfolio__td portfolio__td--symbol">
                      <Text fw={600} className="portfolio__position-symbol">{pos.symbol}</Text>
                    </Table.Td>
                    <Table.Td className="portfolio__td portfolio__td--name">
                      <Text size="sm" c="dimmed" className="portfolio__position-name">{pos.name || '-'}</Text>
                    </Table.Td>
                    <Table.Td ta="right" className="portfolio__td portfolio__td--quantity">{pos.quantity}</Table.Td>
                    <Table.Td ta="right" className="portfolio__td portfolio__td--avg-cost">
                      {formatCurrency(pos.avg_cost || 0, pos.currency || 'EUR')}
                    </Table.Td>
                    <Table.Td ta="right" className="portfolio__td portfolio__td--price">
                      {formatCurrency(pos.current_price || 0, pos.currency || 'EUR')}
                    </Table.Td>
                    <Table.Td ta="right" className="portfolio__td portfolio__td--value">
                      {formatCurrency(pos.value_eur || 0)}
                    </Table.Td>
                    <Table.Td ta="right" className="portfolio__td portfolio__td--pnl">
                      <Badge color={profitPct >= 0 ? 'green' : 'red'} variant="light" className={`portfolio__pnl-badge ${profitPct >= 0 ? 'portfolio__pnl-badge--positive' : 'portfolio__pnl-badge--negative'}`}>
                        {formatPercent(profitPct, true, 2)}
                      </Badge>
                    </Table.Td>
                    <Table.Td ta="right" className="portfolio__td portfolio__td--weight">
                      <Text size="sm" className="portfolio__position-weight">{weight.toFixed(1)}%</Text>
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        )}
      </Card>
    </Stack>
  );
}

export default PortfolioPage;
