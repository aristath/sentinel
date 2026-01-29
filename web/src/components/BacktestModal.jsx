import { useState, useRef, useCallback } from 'react';
import {
  Modal,
  Stack,
  Group,
  Text,
  NumberInput,
  Select,
  Button,
  Progress,
  Table,
  ScrollArea,
  Paper,
  SimpleGrid,
  Badge,
  Checkbox,
  TextInput,
  Loader,
  Box,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconPlayerPlay, IconPlayerStop, IconRefresh, IconDatabase, IconSearch, IconDownload, IconChartLine, IconCalculator } from '@tabler/icons-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import dayjs from 'dayjs';
import { catppuccin } from '../theme';
import { formatCurrency, formatPercent } from '../utils/formatting';

export function BacktestModal({ opened, onClose }) {
  // Configuration state
  const [startDate, setStartDate] = useState(dayjs().subtract(5, 'year').toDate());
  const [endDate, setEndDate] = useState(dayjs().subtract(1, 'day').toDate());
  const [initialCapital, setInitialCapital] = useState(10000);
  const [monthlyDeposit, setMonthlyDeposit] = useState(500);
  const [rebalanceFrequency, setRebalanceFrequency] = useState('weekly');

  // Securities selection state
  const [useExistingUniverse, setUseExistingUniverse] = useState(true);
  const [pickRandom, setPickRandom] = useState(true);
  const [randomCount, setRandomCount] = useState(10);
  const [symbols, setSymbols] = useState('');

  // Running state
  const [status, setStatus] = useState('idle'); // idle, running, completed, error
  const [progress, setProgress] = useState(0);
  const [currentDate, setCurrentDate] = useState('');
  const [portfolioValue, setPortfolioValue] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');

  // Phase tracking state
  const [phase, setPhase] = useState('');
  const [currentItem, setCurrentItem] = useState('');
  const [itemsDone, setItemsDone] = useState(0);
  const [itemsTotal, setItemsTotal] = useState(0);

  // Result state
  const [result, setResult] = useState(null);

  // EventSource reference for cancellation
  const eventSourceRef = useRef(null);

  const formatDate = (date) => dayjs(date).format('YYYY-MM-DD');

  const startBacktest = useCallback(() => {
    setStatus('running');
    setProgress(0);
    setCurrentDate('');
    setPortfolioValue(0);
    setErrorMessage('');
    setResult(null);
    setPhase('');
    setCurrentItem('');
    setItemsDone(0);
    setItemsTotal(0);

    const params = new URLSearchParams({
      start_date: formatDate(startDate),
      end_date: formatDate(endDate),
      initial_capital: initialCapital.toString(),
      monthly_deposit: monthlyDeposit.toString(),
      rebalance_frequency: rebalanceFrequency,
      use_existing_universe: useExistingUniverse.toString(),
      pick_random: pickRandom.toString(),
      random_count: randomCount.toString(),
      symbols: symbols,
    });

    const eventSource = new EventSource(`/api/backtest/run?${params}`);
    eventSourceRef.current = eventSource;

    eventSource.addEventListener('progress', (event) => {
      const data = JSON.parse(event.data);
      setProgress(data.progress_pct);
      setCurrentDate(data.current_date);
      setPortfolioValue(data.portfolio_value);
      setPhase(data.phase || '');
      setCurrentItem(data.current_item || '');
      setItemsDone(data.items_done || 0);
      setItemsTotal(data.items_total || 0);

      if (data.status === 'error') {
        setStatus('error');
        setErrorMessage(data.message || 'Unknown error');
        eventSource.close();
      } else if (data.status === 'cancelled') {
        setStatus('idle');
        eventSource.close();
      }
    });

    eventSource.addEventListener('result', (event) => {
      const data = JSON.parse(event.data);
      setResult(data);
      setStatus('completed');
      eventSource.close();
    });

    eventSource.addEventListener('error', (event) => {
      if (eventSource.readyState === EventSource.CLOSED) {
        return; // Normal close
      }
      setStatus('error');
      setErrorMessage('Connection lost');
      eventSource.close();
    });

    eventSource.onerror = () => {
      if (eventSource.readyState === EventSource.CLOSED) {
        return;
      }
      setStatus('error');
      setErrorMessage('Connection error');
      eventSource.close();
    };
  }, [startDate, endDate, initialCapital, monthlyDeposit, rebalanceFrequency, useExistingUniverse, pickRandom, randomCount, symbols]);

  const cancelBacktest = useCallback(async () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }
    try {
      await fetch('/api/backtest/cancel', { method: 'POST' });
    } catch (e) {
      // Ignore
    }
    setStatus('idle');
  }, []);

  const resetBacktest = useCallback(() => {
    setStatus('idle');
    setResult(null);
    setProgress(0);
    setCurrentDate('');
    setPortfolioValue(0);
    setErrorMessage('');
    setPhase('');
    setCurrentItem('');
    setItemsDone(0);
    setItemsTotal(0);
  }, []);

  const handleClose = useCallback(() => {
    if (status === 'running') {
      cancelBacktest();
    }
    onClose();
  }, [status, cancelBacktest, onClose]);

  // Prepare chart data (sample every N points to avoid overcrowding)
  const getChartData = () => {
    if (!result?.snapshots) return [];
    const snapshots = result.snapshots;
    const step = Math.max(1, Math.floor(snapshots.length / 100));
    return snapshots
      .filter((_, i) => i % step === 0 || i === snapshots.length - 1)
      .map((s) => ({
        date: s.date,
        value: s.total_value,
      }));
  };

  return (
    <Modal
      opened={opened}
      onClose={handleClose}
      title={<Text fw={600}>Backtest Portfolio</Text>}
      size={status === 'completed' ? 'xl' : 'md'}
    >
      {status === 'idle' && (
        <Stack gap="md">
          <DatePickerInput
            label="Start Date"
            value={startDate}
            onChange={setStartDate}
            maxDate={dayjs().subtract(1, 'month').toDate()}
            clearable={false}
          />

          <DatePickerInput
            label="End Date"
            value={endDate}
            onChange={setEndDate}
            minDate={startDate}
            maxDate={dayjs().subtract(1, 'day').toDate()}
            clearable={false}
          />

          <NumberInput
            label="Initial Capital"
            description="Starting portfolio value in EUR"
            value={initialCapital}
            onChange={setInitialCapital}
            min={100}
            max={10000000}
            step={1000}
            prefix="EUR "
            thousandSeparator=","
          />

          <NumberInput
            label="Monthly Deposit"
            description="Amount to add on the 1st of each month"
            value={monthlyDeposit}
            onChange={setMonthlyDeposit}
            min={0}
            max={100000}
            step={100}
            prefix="EUR "
            thousandSeparator=","
          />

          <Select
            label="Rebalance Frequency"
            description="How often to rebalance the portfolio"
            value={rebalanceFrequency}
            onChange={setRebalanceFrequency}
            data={[
              { value: 'daily', label: 'Daily' },
              { value: 'weekly', label: 'Weekly (Recommended)' },
              { value: 'monthly', label: 'Monthly' },
            ]}
          />

          {/* Securities Selection */}
          <Paper p="sm" withBorder>
            <Text size="sm" fw={500} mb="sm">Securities Selection</Text>

            <Checkbox
              label="Use existing universe"
              description="Use all active securities from current database"
              checked={useExistingUniverse}
              onChange={(e) => setUseExistingUniverse(e.currentTarget.checked)}
              mb="sm"
            />

            {!useExistingUniverse && (
              <>
                <Checkbox
                  label="Pick random securities"
                  description="Randomly select securities from available symbols"
                  checked={pickRandom}
                  onChange={(e) => setPickRandom(e.currentTarget.checked)}
                  mb="sm"
                  ml="md"
                />

                {pickRandom ? (
                  <NumberInput
                    label="Number of securities"
                    description="How many random securities to select"
                    value={randomCount}
                    onChange={setRandomCount}
                    min={1}
                    max={100}
                    ml="md"
                  />
                ) : (
                  <TextInput
                    label="Symbols"
                    description="Comma-separated list (e.g., AAPL.US, MSFT.US, GOOGL.US)"
                    placeholder="AAPL.US, MSFT.US, GOOGL.US"
                    value={symbols}
                    onChange={(e) => setSymbols(e.currentTarget.value)}
                    ml="md"
                  />
                )}
              </>
            )}
          </Paper>

          <Button
            leftSection={<IconPlayerPlay size={18} />}
            onClick={startBacktest}
            fullWidth
            mt="md"
          >
            Run Backtest
          </Button>
        </Stack>
      )}

      {status === 'running' && (
        <Stack gap="md" align="center">
          {/* Phase indicator */}
          <Group gap="xs">
            {phase === 'prepare_db' && (
              <>
                <Loader size="sm" />
                <IconDatabase size={20} color="var(--mantine-color-blue-6)" />
                <Text size="lg" fw={500}>Preparing database...</Text>
              </>
            )}
            {phase === 'discover_symbols' && (
              <>
                <Loader size="sm" />
                <IconSearch size={20} color="var(--mantine-color-blue-6)" />
                <Text size="lg" fw={500}>Discovering securities...</Text>
              </>
            )}
            {phase === 'download_prices' && (
              <>
                <IconDownload size={20} color="var(--mantine-color-blue-6)" />
                <Text size="lg" fw={500}>Downloading historical data...</Text>
              </>
            )}
            {phase === 'calculate_scores' && (
              <>
                <Loader size="sm" />
                <IconCalculator size={20} color="var(--mantine-color-blue-6)" />
                <Text size="lg" fw={500}>Calculating scores...</Text>
              </>
            )}
            {phase === 'simulate' && (
              <>
                <IconChartLine size={20} color="var(--mantine-color-blue-6)" />
                <Text size="lg" fw={500}>Running simulation...</Text>
              </>
            )}
            {!phase && (
              <>
                <Loader size="sm" />
                <Text size="lg" fw={500}>Starting backtest...</Text>
              </>
            )}
          </Group>

          {/* Progress bar */}
          <Progress
            value={progress}
            size="xl"
            radius="xl"
            striped
            animated
            w="100%"
          />

          {/* Phase-specific details */}
          <Box w="100%">
            {phase === 'download_prices' && itemsTotal > 0 && (
              <Group justify="space-between" w="100%">
                <Text size="sm" c="dimmed">
                  {currentItem && `Processing: ${currentItem}`}
                </Text>
                <Text size="sm" c="dimmed">
                  {itemsDone} / {itemsTotal} symbols
                </Text>
              </Group>
            )}

            {phase === 'simulate' && (
              <Group justify="space-between" w="100%">
                <Text size="sm" c="dimmed">
                  Simulating: {currentDate}
                </Text>
                <Text size="sm" c="dimmed">
                  {progress.toFixed(1)}%
                </Text>
              </Group>
            )}
          </Box>

          {portfolioValue > 0 && phase === 'simulate' && (
            <Text size="lg">
              Portfolio Value: {formatCurrency(portfolioValue, 'EUR', 0)}
            </Text>
          )}

          <Button
            color="red"
            variant="outline"
            leftSection={<IconPlayerStop size={18} />}
            onClick={cancelBacktest}
            mt="md"
          >
            Cancel
          </Button>
        </Stack>
      )}

      {status === 'error' && (
        <Stack gap="md" align="center">
          <Text size="lg" c="red" fw={500}>
            Backtest Failed
          </Text>
          <Text c="dimmed">{errorMessage}</Text>
          <Button
            variant="outline"
            leftSection={<IconRefresh size={18} />}
            onClick={resetBacktest}
            mt="md"
          >
            Try Again
          </Button>
        </Stack>
      )}

      {status === 'completed' && result && (
        <Stack gap="md">
          {/* Performance Metrics */}
          <SimpleGrid cols={2} spacing="sm">
            <Paper p="sm" withBorder>
              <Text size="sm" c="dimmed">Total Invested</Text>
              <Text size="lg" fw={500}>{formatCurrency(result.total_deposits, 'EUR', 0)}</Text>
            </Paper>
            <Paper p="sm" withBorder>
              <Text size="sm" c="dimmed">Final Value</Text>
              <Text size="lg" fw={500}>{formatCurrency(result.final_value, 'EUR', 0)}</Text>
            </Paper>
            <Paper p="sm" withBorder>
              <Text size="sm" c="dimmed">Total Return</Text>
              <Text
                size="lg"
                fw={500}
                c={result.total_return >= 0 ? 'teal' : 'red'}
              >
                {formatCurrency(result.total_return, 'EUR', 0)} ({formatPercent(result.total_return_pct, true, 2)})
              </Text>
            </Paper>
            <Paper p="sm" withBorder>
              <Text size="sm" c="dimmed">CAGR</Text>
              <Text
                size="lg"
                fw={500}
                c={result.cagr >= 0 ? 'teal' : 'red'}
              >
                {formatPercent(result.cagr, true, 2)}
              </Text>
            </Paper>
            <Paper p="sm" withBorder>
              <Text size="sm" c="dimmed">Max Drawdown</Text>
              <Text size="lg" fw={500} c="orange">
                -{result.max_drawdown.toFixed(2)}%
              </Text>
            </Paper>
            <Paper p="sm" withBorder>
              <Text size="sm" c="dimmed">Sharpe Ratio</Text>
              <Text size="lg" fw={500}>
                {result.sharpe_ratio.toFixed(2)}
              </Text>
            </Paper>
          </SimpleGrid>

          {/* Equity Curve Chart */}
          <Paper p="sm" withBorder>
            <Text size="sm" fw={500} mb="sm">Equity Curve</Text>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={getChartData()}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 10 }}
                  tickFormatter={(d) => dayjs(d).format('MMM YY')}
                />
                <YAxis
                  tick={{ fontSize: 10 }}
                  tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
                />
                <Tooltip
                  formatter={(value) => [formatCurrency(value, 'EUR', 0), 'Value']}
                  labelFormatter={(label) => dayjs(label).format('MMM D, YYYY')}
                />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke={catppuccin.blue}
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </Paper>

          {/* Security Breakdown */}
          {result.security_performance?.length > 0 && (
            <Paper p="sm" withBorder>
              <Text size="sm" fw={500} mb="sm">Security Performance</Text>
              <ScrollArea h={200}>
                <Table striped highlightOnHover>
                  <Table.Thead>
                    <Table.Tr>
                      <Table.Th>Symbol</Table.Th>
                      <Table.Th>Invested</Table.Th>
                      <Table.Th>Final Value</Table.Th>
                      <Table.Th>Return</Table.Th>
                      <Table.Th>Trades</Table.Th>
                    </Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {result.security_performance.map((sp) => (
                      <Table.Tr key={sp.symbol}>
                        <Table.Td>
                          <Text size="sm" fw={500}>{sp.symbol}</Text>
                          <Text size="sm" c="dimmed">{sp.name}</Text>
                        </Table.Td>
                        <Table.Td>{formatCurrency(sp.total_invested, 'EUR', 0)}</Table.Td>
                        <Table.Td>{formatCurrency(sp.final_value, 'EUR', 0)}</Table.Td>
                        <Table.Td>
                          <Badge
                            color={sp.total_return >= 0 ? 'teal' : 'red'}
                            variant="light"
                          >
                            {formatPercent(sp.return_pct, true, 2)}
                          </Badge>
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm">
                            {sp.num_buys} buys, {sp.num_sells} sells
                          </Text>
                        </Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </ScrollArea>
            </Paper>
          )}

          {/* Trade Summary */}
          <Group justify="space-between">
            <Text size="sm" c="dimmed">
              Total Trades: {result.trades?.length || 0}
            </Text>
            <Button
              variant="outline"
              leftSection={<IconRefresh size={18} />}
              onClick={resetBacktest}
            >
              Run Another Backtest
            </Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
