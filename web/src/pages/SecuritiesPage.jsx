import { useQuery } from '@tanstack/react-query';
import { Stack, Title, Card, Table, Text, Badge, Loader, Center, TextInput, Group } from '@mantine/core';
import { useState, useMemo } from 'react';
import { getSecurities } from '../api/client';

function SecuritiesPage() {
  const [search, setSearch] = useState('');

  const { data: securities, isLoading, error } = useQuery({
    queryKey: ['securities'],
    queryFn: getSecurities,
  });

  const filteredSecurities = useMemo(() => {
    if (!securities) return [];
    if (!search) return securities;

    const term = search.toLowerCase();
    return securities.filter(
      (sec) =>
        sec.symbol.toLowerCase().includes(term) ||
        (sec.name && sec.name.toLowerCase().includes(term)) ||
        (sec.geography && sec.geography.toLowerCase().includes(term)) ||
        (sec.industry && sec.industry.toLowerCase().includes(term))
    );
  }, [securities, search]);

  if (isLoading) {
    return (
      <Center h={200} className="securities__loading">
        <Loader />
      </Center>
    );
  }

  if (error) {
    return (
      <Stack gap="lg" className="securities securities--error">
        <Title order={2} className="securities__title">Securities Universe</Title>
        <Card shadow="sm" padding="lg" withBorder className="securities__error-card">
          <Text c="red" className="securities__error-text">Error loading securities: {error.message}</Text>
        </Card>
      </Stack>
    );
  }

  return (
    <Stack gap="lg" className="securities">
      <Group justify="space-between" className="securities__header">
        <Title order={2} className="securities__title">Securities Universe</Title>
        <Text c="dimmed" className="securities__count">{securities?.length || 0} securities</Text>
      </Group>

      <TextInput
        placeholder="Search by symbol, name, geography, or industry..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="securities__search"
      />

      <Card shadow="sm" padding="lg" withBorder className="securities__table-card">
        {filteredSecurities.length === 0 ? (
          <Text c="dimmed" className="securities__empty">No securities found</Text>
        ) : (
          <Table striped highlightOnHover className="securities__table">
            <Table.Thead className="securities__table-head">
              <Table.Tr className="securities__header-row">
                <Table.Th className="securities__th securities__th--symbol">Symbol</Table.Th>
                <Table.Th className="securities__th securities__th--name">Name</Table.Th>
                <Table.Th className="securities__th securities__th--currency">Currency</Table.Th>
                <Table.Th className="securities__th securities__th--geography">Geography</Table.Th>
                <Table.Th className="securities__th securities__th--industry">Industry</Table.Th>
                <Table.Th ta="center" className="securities__th securities__th--lot">Lot Size</Table.Th>
                <Table.Th ta="center" className="securities__th securities__th--status">Status</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody className="securities__table-body">
              {filteredSecurities.map((sec) => (
                <Table.Tr key={sec.symbol} className={`securities__row securities__row--${sec.symbol.toLowerCase().replace(/\./g, '-')}`}>
                  <Table.Td className="securities__td securities__td--symbol">
                    <Text fw={600} className="securities__symbol">{sec.symbol}</Text>
                  </Table.Td>
                  <Table.Td className="securities__td securities__td--name">
                    <Text size="sm" className="securities__name">{sec.name || '-'}</Text>
                  </Table.Td>
                  <Table.Td className="securities__td securities__td--currency">
                    <Badge variant="light" color="gray" className="securities__currency-badge">{sec.currency}</Badge>
                  </Table.Td>
                  <Table.Td className="securities__td securities__td--geography">
                    <Text size="sm" className="securities__geography">{sec.geography || '-'}</Text>
                  </Table.Td>
                  <Table.Td className="securities__td securities__td--industry">
                    <Text size="sm" className="securities__industry">{sec.industry || '-'}</Text>
                  </Table.Td>
                  <Table.Td ta="center" className="securities__td securities__td--lot">
                    <Text size="sm" className="securities__lot">{sec.min_lot || 1}</Text>
                  </Table.Td>
                  <Table.Td ta="center" className="securities__td securities__td--status">
                    <Group gap="xs" justify="center" className="securities__status-badges">
                      {sec.active ? (
                        <Badge color="green" size="sm" className="securities__badge securities__badge--active">Active</Badge>
                      ) : (
                        <Badge color="gray" size="sm" className="securities__badge securities__badge--inactive">Inactive</Badge>
                      )}
                      {sec.allow_buy === 0 && (
                        <Badge color="red" size="sm" className="securities__badge securities__badge--no-buy">No Buy</Badge>
                      )}
                      {sec.allow_sell === 0 && (
                        <Badge color="red" size="sm" className="securities__badge securities__badge--no-sell">No Sell</Badge>
                      )}
                    </Group>
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

export default SecuritiesPage;
