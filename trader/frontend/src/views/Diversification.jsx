import { Grid } from '@mantine/core';
import { CountryRadarCard } from '../components/charts/CountryRadarCard';
import { IndustryRadarCard } from '../components/charts/IndustryRadarCard';
import { ConcentrationAlerts } from '../components/portfolio/ConcentrationAlerts';

export function Diversification() {
  return (
    <div>
      <ConcentrationAlerts />
      <Grid mt="md">
        <Grid.Col span={{ base: 12, md: 6 }}>
          <CountryRadarCard />
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <IndustryRadarCard />
        </Grid.Col>
      </Grid>
    </div>
  );
}

