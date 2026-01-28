import { useQuery } from '@tanstack/react-query';
import { Grid, Card, Title, Text, Group, Stack, Loader, Badge, RingProgress, Center } from '@mantine/core';
import { getPortfolio, getSchedulerStatus, getRecommendations } from '../api/client';
import { formatCurrency } from '../utils/formatting';

// Dashboard uses 0 decimal places for currency
const formatCurrencyCompact = (value, currency = 'EUR') => formatCurrency(value, currency, 0);

function StatCard({ title, value, subtitle, color = 'blue', className = '' }) {
  return (
    <Card shadow="sm" padding="lg" withBorder className={`stat-card ${className}`}>
      <Text size="sm" c="dimmed" tt="uppercase" fw={500} className="stat-card__title">
        {title}
      </Text>
      <Text size="xl" fw={700} c={color} mt="xs" className="stat-card__value">
        {value}
      </Text>
      {subtitle && (
        <Text size="sm" c="dimmed" mt={4} className="stat-card__subtitle">
          {subtitle}
        </Text>
      )}
    </Card>
  );
}

function DashboardPage() {
  const { data: portfolio, isLoading: portfolioLoading } = useQuery({
    queryKey: ['portfolio'],
    queryFn: getPortfolio,
  });

  const { data: schedulerStatus, isLoading: schedulerLoading } = useQuery({
    queryKey: ['scheduler'],
    queryFn: getSchedulerStatus,
  });

  const { data: recommendationsData } = useQuery({
    queryKey: ['recommendations'],
    queryFn: () => getRecommendations(), // Uses backend setting
  });

  if (portfolioLoading) {
    return (
      <Center h={200}>
        <Loader />
      </Center>
    );
  }

  const totalValue = portfolio?.total_value_eur || 0;
  const positionCount = portfolio?.positions?.length || 0;
  const cashEur = portfolio?.cash?.EUR || 0;
  const pendingActions = recommendationsData?.recommendations?.length || 0;

  const runningJobs = schedulerStatus?.pending?.length || 0;

  return (
    <Stack gap="lg" className="dashboard">
      <Title order={2} className="dashboard__title">Dashboard</Title>

      <Grid className="dashboard__stats-grid">
        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <StatCard
            title="Portfolio Value"
            value={formatCurrencyCompact(totalValue)}
            subtitle={`${positionCount} positions`}
            className="stat-card--portfolio-value"
          />
        </Grid.Col>

        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <StatCard
            title="Cash Balance"
            value={formatCurrencyCompact(cashEur)}
            subtitle="Available EUR"
            color="green"
            className="stat-card--cash-balance"
          />
        </Grid.Col>

        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <StatCard
            title="Pending Actions"
            value={pendingActions}
            subtitle="Recommendations"
            color={pendingActions > 0 ? 'yellow' : 'gray'}
            className="stat-card--pending-actions"
          />
        </Grid.Col>

        <Grid.Col span={{ base: 12, sm: 6, md: 3 }}>
          <StatCard
            title="Scheduler"
            value={runningJobs > 0 ? `${runningJobs} running` : 'Idle'}
            subtitle={`${schedulerStatus?.length || 0} jobs configured`}
            color={runningJobs > 0 ? 'teal' : 'gray'}
            className="stat-card--scheduler"
          />
        </Grid.Col>
      </Grid>

      <Grid className="dashboard__details-grid">
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Card shadow="sm" padding="lg" withBorder className="dashboard__top-positions">
            <Title order={4} mb="md" className="dashboard__card-title">Top Positions</Title>
            <Stack gap="xs" className="dashboard__positions-list">
              {portfolio?.positions?.slice(0, 5).map((pos) => (
                <Group key={pos.symbol} justify="space-between" className={`dashboard__position-row dashboard__position-row--${pos.symbol.toLowerCase().replace(/\./g, '-')}`}>
                  <Text size="sm" fw={500} className="dashboard__position-symbol">{pos.symbol}</Text>
                  <Group gap="xs" className="dashboard__position-stats">
                    <Text size="sm" className="dashboard__position-value">{formatCurrencyCompact(pos.value_eur || 0)}</Text>
                    <Badge
                      size="sm"
                      color={pos.profit_pct >= 0 ? 'green' : 'red'}
                      className={`dashboard__position-pnl ${pos.profit_pct >= 0 ? 'dashboard__position-pnl--positive' : 'dashboard__position-pnl--negative'}`}
                    >
                      {pos.profit_pct >= 0 ? '+' : ''}{(pos.profit_pct || 0).toFixed(1)}%
                    </Badge>
                  </Group>
                </Group>
              ))}
              {(!portfolio?.positions || portfolio.positions.length === 0) && (
                <Text size="sm" c="dimmed" className="dashboard__no-positions">No positions</Text>
              )}
            </Stack>
          </Card>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 6 }}>
          <Card shadow="sm" padding="lg" withBorder className="dashboard__recent-jobs">
            <Title order={4} mb="md" className="dashboard__card-title">Recent Jobs</Title>
            <Stack gap="xs" className="dashboard__jobs-list">
              {schedulerStatus?.slice(0, 5).map((job) => (
                <Group key={job.name} justify="space-between" className={`dashboard__job-row dashboard__job-row--${job.name.replace(/_/g, '-')}`}>
                  <Text size="sm" fw={500} className="dashboard__job-name">{job.name}</Text>
                  <Group gap="xs" className="dashboard__job-status">
                    {job.running ? (
                      <Badge size="sm" color="blue" className="dashboard__job-badge dashboard__job-badge--running">Running</Badge>
                    ) : job.last_run ? (
                      <Text size="sm" c="dimmed" className="dashboard__job-last-run">
                        {new Date(job.last_run).toLocaleTimeString()}
                      </Text>
                    ) : (
                      <Text size="sm" c="dimmed" className="dashboard__job-never-run">Never run</Text>
                    )}
                  </Group>
                </Group>
              ))}
            </Stack>
          </Card>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}

export default DashboardPage;
