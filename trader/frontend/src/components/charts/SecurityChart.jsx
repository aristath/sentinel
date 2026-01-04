import { useEffect, useRef, useState } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import { api } from '../../api/client';
import { Select, Button, Group, Loader, Text } from '@mantine/core';

export function SecurityChart({ isin, symbol, onClose }) {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const lineSeriesRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedRange, setSelectedRange] = useState('1Y');
  const [selectedSource, setSelectedSource] = useState('tradernet');

  useEffect(() => {
    if (!chartContainerRef.current || !isin) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#1A1B1E' },
        textColor: '#D1D5DB',
      },
      grid: {
        vertLines: { color: '#374151' },
        horzLines: { color: '#374151' },
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
    });

    const lineSeries = chart.addLineSeries({
      color: '#3B82F6',
      lineWidth: 2,
    });

    chartRef.current = chart;
    lineSeriesRef.current = lineSeries;

    // Handle resize
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({
          width: chartContainerRef.current.clientWidth,
        });
      }
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      if (chartRef.current) {
        chartRef.current.remove();
        chartRef.current = null;
        lineSeriesRef.current = null;
      }
    };
  }, [isin]);

  useEffect(() => {
    if (isin && lineSeriesRef.current) {
      loadChartData();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedRange, selectedSource, isin]);

  const loadChartData = async () => {
    if (!isin) return;

    setLoading(true);
    setError(null);

    try {
      const data = await api.fetchSecurityChart(isin, selectedRange, selectedSource);

      if (!data || data.length === 0) {
        setError('No chart data available');
        if (lineSeriesRef.current) {
          lineSeriesRef.current.setData([]);
        }
        return;
      }

      // Transform data for Lightweight Charts
      const chartData = data.map(item => ({
        time: item.time,
        value: item.value || item.close || item.price,
      }));

      if (lineSeriesRef.current) {
        lineSeriesRef.current.setData(chartData);
        chartRef.current.timeScale().fitContent();
      }
    } catch (err) {
      console.error('Failed to load security chart:', err);
      setError('Failed to load chart data');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <Group justify="space-between" mb="md">
        <Text size="lg" fw={600}>
          {symbol} Chart
        </Text>
        <Group gap="xs">
          <Select
            size="xs"
            data={[
              { value: '1M', label: '1 Month' },
              { value: '3M', label: '3 Months' },
              { value: '6M', label: '6 Months' },
              { value: '1Y', label: '1 Year' },
              { value: '2Y', label: '2 Years' },
              { value: '5Y', label: '5 Years' },
              { value: '10Y', label: '10 Years' },
            ]}
            value={selectedRange}
            onChange={(val) => setSelectedRange(val || '1Y')}
            style={{ width: '120px' }}
          />
          <Select
            size="xs"
            data={[
              { value: 'tradernet', label: 'Tradernet' },
              { value: 'yahoo', label: 'Yahoo' },
            ]}
            value={selectedSource}
            onChange={(val) => setSelectedSource(val || 'tradernet')}
            style={{ width: '120px' }}
          />
          {onClose && (
            <Button size="xs" variant="subtle" onClick={onClose}>
              Close
            </Button>
          )}
        </Group>
      </Group>

      {loading && (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
          <Loader />
        </div>
      )}

      {error && (
        <Text c="red" ta="center" py="xl">
          {error}
        </Text>
      )}

      <div
        ref={chartContainerRef}
        style={{ width: '100%', height: '400px' }}
      />
    </div>
  );
}

