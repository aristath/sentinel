import { useMemo, useState } from 'react';
import { Badge, Box, Group, SegmentedControl, Stack, Text } from '@mantine/core';
import { useQuery } from '@tanstack/react-query';
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { getSecurityForecast } from '../api/client';
import { catppuccin } from '../theme';
import { buildUsefulYAxisDomain } from '../utils/chartUtils';
import { formatPercent } from '../utils/formatting';

function fmtReturn(value) {
  return value == null ? '-' : formatPercent(value * 100, true, 1);
}

function TooltipBody({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const row = payload[0]?.payload || {};
  return (
    <Box
      style={{
        background: 'var(--mantine-color-dark-7)',
        border: '1px solid var(--mantine-color-dark-4)',
        padding: '6px 8px',
        fontSize: 11,
      }}
    >
      <Text size="xs" fw={600}>{label}</Text>
      <Text size="xs" style={{ color: catppuccin.blue }}>Median {fmtReturn(row.return50)}</Text>
      <Text size="xs" c="dimmed">
        Range {fmtReturn(row.return10)} to {fmtReturn(row.return90)}
      </Text>
    </Box>
  );
}

function buildSeries(points) {
  if (!Array.isArray(points) || points.length === 0) return [];
  return [
    {
      label: 'Now',
      value10: 100,
      value50: 100,
      value90: 100,
      bandLow: 100,
      bandSpread: 0,
      return10: 0,
      return50: 0,
      return90: 0,
    },
    ...points.map((point) => {
      const r10 = Number(point.cumulative_q10 ?? 0);
      const r50 = Number(point.cumulative_q50 ?? 0);
      const r90 = Number(point.cumulative_q90 ?? 0);
      const value10 = 100 * (1 + r10);
      const value90 = 100 * (1 + r90);
      return {
        label: `${point.horizon_step}w`,
        value10,
        value50: 100 * (1 + r50),
        value90,
        bandLow: value10,
        bandSpread: Math.max(0, value90 - value10),
        return10: r10,
        return50: r50,
        return90: r90,
      };
    }),
  ];
}

export function SecurityForecastCard({ symbol, forecastData, forecastScore, forecastReturn4w, chartHeight = 160 }) {
  const [scope, setScope] = useState('grouped');
  const { data: queryData, isLoading, isError } = useQuery({
    queryKey: ['forecast', symbol],
    queryFn: () => getSecurityForecast(symbol),
    enabled: Boolean(symbol) && !forecastData,
    staleTime: 5 * 60 * 1000,
  });
  const data = forecastData || queryData;

  const availableScopes = useMemo(() => {
    const points = data?.points || {};
    return ['grouped', 'solo'].filter((item) => Array.isArray(points[item]) && points[item].length > 0);
  }, [data]);

  const activeScope = availableScopes.includes(scope) ? scope : availableScopes[0];
  const series = useMemo(() => buildSeries(data?.points?.[activeScope]), [data, activeScope]);
  const yDomain = useMemo(
    () => buildUsefulYAxisDomain(series.flatMap((point) => [point.value10, point.value50, point.value90]), {
      minPadding: 0.5,
    }),
    [series]
  );

  if (isLoading || isError || !data || availableScopes.length === 0 || series.length === 0) {
    return null;
  }

  const median = Number(data?.score?.forecast_return_4w ?? forecastReturn4w ?? 0);
  const score = Number(data?.score?.score ?? forecastScore ?? 0.5);
  const color = median >= 0 ? catppuccin.green : catppuccin.red;

  return (
    <Box
      p="xs"
      style={{
        background: catppuccin.base,
        border: `1px solid ${catppuccin.surface0}`,
        height: '100%',
      }}
    >
      <Stack gap={6}>
        <Group justify="space-between" align="center">
          <Group gap="xs" wrap="nowrap">
            <Text size="xs" fw={700} tt="uppercase" c="dimmed">Forecast</Text>
            <Badge size="xs" variant="light" color={median >= 0 ? 'green' : 'red'}>
              {fmtReturn(median)}
            </Badge>
            <Text size="xs" c="dimmed">Timing</Text>
            <Text size="xs" fw={600}>{formatPercent(score * 100, false, 0)}</Text>
          </Group>
          {availableScopes.length > 1 && (
            <SegmentedControl
              size="xs"
              value={activeScope}
              onChange={setScope}
              data={availableScopes.map((item) => ({ value: item, label: item === 'grouped' ? 'Group' : 'Solo' }))}
            />
          )}
        </Group>

        <div style={{ width: '100%', height: chartHeight }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={series} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.18} />
              <XAxis dataKey="label" tick={{ fontSize: 10, fill: catppuccin.overlay1 }} height={18} />
              <YAxis
                tick={{ fontSize: 10, fill: catppuccin.overlay1 }}
                domain={yDomain}
                allowDataOverflow
                tickFormatter={(value) => `${Math.round(value)}`}
                width={30}
              />
              <Tooltip content={<TooltipBody />} />
              <Area dataKey="bandLow" stackId="band" stroke="none" fill="transparent" />
              <Area dataKey="bandSpread" stackId="band" stroke="none" fill={catppuccin.blue} fillOpacity={0.16} />
              <Line
                type="monotone"
                dataKey="value50"
                stroke={color}
                strokeWidth={2}
                dot={{ r: 2.5, fill: color }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </Stack>
    </Box>
  );
}
