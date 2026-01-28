import { useQuery } from '@tanstack/react-query';
import { Stack, Title, Card, Text, Badge, Group, Loader, Center, Table, NumberInput, Button } from '@mantine/core';
import { useState } from 'react';
import { getRecommendations } from '../api/client';
import { formatCurrency } from '../utils/formatting';

function RecommendationsPage() {
  const [minValue, setMinValue] = useState(100);

  const { data: recommendationsData, isLoading, error, refetch } = useQuery({
    queryKey: ['recommendations', minValue],
    queryFn: () => getRecommendations(minValue),
  });
  const recommendations = recommendationsData?.recommendations;

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
        <Title order={2}>Recommendations</Title>
        <Card shadow="sm" padding="lg" withBorder>
          <Text c="red">Error loading recommendations: {error.message}</Text>
        </Card>
      </Stack>
    );
  }

  return (
    <Stack gap="lg">
      <Title order={2}>Trade Recommendations</Title>

      {/* Filters */}
      <Card shadow="sm" padding="lg" withBorder>
        <Group>
          <NumberInput
            label="Min Value (EUR)"
            value={minValue}
            onChange={setMinValue}
            min={50}
            max={10000}
            step={50}
            w={150}
          />
          <Button
            variant="light"
            onClick={() => refetch()}
            mt="auto"
          >
            Refresh
          </Button>
        </Group>
      </Card>

      {/* Recommendations */}
      <Card shadow="sm" padding="lg" withBorder>
        {!recommendations || recommendations.length === 0 ? (
          <Text c="dimmed">No recommendations at this time</Text>
        ) : (
          <Table striped highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Action</Table.Th>
                <Table.Th>Symbol</Table.Th>
                <Table.Th ta="right">Quantity</Table.Th>
                <Table.Th ta="right">Price</Table.Th>
                <Table.Th ta="right">Value (EUR)</Table.Th>
                <Table.Th>Reason</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {recommendations.map((rec, idx) => (
                <Table.Tr key={`${rec.symbol}-${idx}`}>
                  <Table.Td>
                    <Badge
                      color={rec.action === 'buy' ? 'green' : 'red'}
                      variant="filled"
                      size="lg"
                    >
                      {rec.action.toUpperCase()}
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text fw={600}>{rec.symbol}</Text>
                  </Table.Td>
                  <Table.Td ta="right">
                    <Text>{rec.quantity}</Text>
                    {rec.lot_size > 1 && (
                      <Text size="sm" c="dimmed">lot: {rec.lot_size}</Text>
                    )}
                  </Table.Td>
                  <Table.Td ta="right">
                    {formatCurrency(rec.price, rec.currency)}
                  </Table.Td>
                  <Table.Td ta="right">
                    {formatCurrency(Math.abs(rec.value_delta_eur))}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">{rec.reason}</Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        )}
      </Card>
    </Stack>
  );
}

export default RecommendationsPage;
