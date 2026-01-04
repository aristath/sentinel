import { Group, Badge } from '@mantine/core';
import { useAppStore } from '../../stores/appStore';

export function MarketStatus() {
  const { markets } = useAppStore();

  return (
    <Group gap="xs" wrap="wrap" mb="md">
      {Object.entries(markets).map(([geo, market]) => (
        <Badge
          key={geo}
          color={market.open ? 'green' : 'gray'}
          variant="light"
          size="sm"
          title={
            market.open
              ? `${geo} market open (closes ${market.closes_at})`
              : `${geo} market closed (opens ${market.opens_at}${market.opens_date ? ` on ${market.opens_date}` : ''})`
          }
        >
          <Group gap="xs">
            <div
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '50%',
                backgroundColor: market.open
                  ? 'var(--mantine-color-green-5)'
                  : 'var(--mantine-color-gray-6)',
              }}
            />
            <span>{geo}</span>
          </Group>
        </Badge>
      ))}
    </Group>
  );
}

