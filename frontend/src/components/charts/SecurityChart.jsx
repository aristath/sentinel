import { useEffect, useRef, useState, useImperativeHandle, forwardRef, useCallback } from 'react';
import { createChart, ColorType } from 'lightweight-charts';
import { api } from '../../api/client';
import { Select, Button, Group, Loader, Text } from '@mantine/core';
import { setSecurityChartRefreshFn } from '../../stores/eventHandlers';

export const SecurityChart = forwardRef(({ isin, symbol, onClose }, ref) => {
  const chartContainerRef = useRef(null);
  const chartRef = useRef(null);
  const lineSeriesRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedRange, setSelectedRange] = useState('1Y');
  const [selectedSource, setSelectedSource] = useState('tradernet');

  // Memoize chart data loading function
  const loadChartData = useCallback(async () => {
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
  }, [isin, selectedRange, selectedSource]);

  // Expose refresh function via ref
  useImperativeHandle(ref, () => ({
    refresh: loadChartData,
  }), [loadChartData]);

  useEffect(() => {
    if (!chartContainerRef.current || !isin) return;

    // Create chart with Catppuccin Mocha colors
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: '#1e1e2e' }, // Catppuccin Mocha Base
        textColor: '#cdd6f4', // Catppuccin Mocha Text
      },
      grid: {
        vertLines: { color: '#313244' }, // Catppuccin Mocha Surface 0
        horzLines: { color: '#313244' }, // Catppuccin Mocha Surface 0
      },
      width: chartContainerRef.current.clientWidth,
      height: 400,
    });

    const lineSeries = chart.addLineSeries({
      color: '#89b4fa', // Catppuccin Mocha Blue
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

  // Load chart data when range, source, or isin changes
  useEffect(() => {
    if (isin && lineSeriesRef.current) {
      loadChartData();
    }
  }, [isin, selectedRange, selectedSource, loadChartData]);

  // Register refresh function with event handler
  useEffect(() => {
    if (isin) {
      setSecurityChartRefreshFn(() => {
        if (lineSeriesRef.current) {
          loadChartData();
        }
      });

      return () => {
        setSecurityChartRefreshFn(null);
      };
    }
  }, [isin, loadChartData]);

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
});
