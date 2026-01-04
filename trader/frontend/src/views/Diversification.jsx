import { Grid, Stack, Paper, Text } from '@mantine/core';
import { CountryRadarCard } from '../components/charts/CountryRadarCard';
import { IndustryRadarCard } from '../components/charts/IndustryRadarCard';
import { ConcentrationAlerts } from '../components/portfolio/ConcentrationAlerts';
import { GroupingManager } from '../components/portfolio/GroupingManager';

export function Diversification() {
  return (
    <Stack gap="md">
      <ConcentrationAlerts />
      <Grid mt="md">
        <Grid.Col span={{ base: 12, md: 6 }}>
          <CountryRadarCard />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <IndustryRadarCard />
        </Grid.Col>
      </Grid>
      <Paper p="md" withBorder mt="md">
        <Text size="sm" fw={500} mb="xs" tt="uppercase">Custom Grouping</Text>
        <Text size="xs" c="dimmed" mb="md">
          Create custom groups for countries and industries to simplify constraints and improve optimizer performance.
        </Text>
        <GroupingManager />
      </Paper>
    </Stack>
  );
}
