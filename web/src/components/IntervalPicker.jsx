import { useState, useEffect } from 'react';
import { Group, SegmentedControl, NumberInput } from '@mantine/core';

const UNITS = [
  { label: 'Minutes', value: 'minutes' },
  { label: 'Hours', value: 'hours' },
  { label: 'Days', value: 'days' },
];

const MULTIPLIERS = { minutes: 1, hours: 60, days: 1440 };

function toDisplay(minutes) {
  if (minutes % 1440 === 0 && minutes >= 1440) return { unit: 'days', value: minutes / 1440 };
  if (minutes % 60 === 0 && minutes >= 60) return { unit: 'hours', value: minutes / 60 };
  return { unit: 'minutes', value: minutes };
}

export function IntervalPicker({ value, onChange, size = 'xs', label }) {
  const display = toDisplay(value);
  const [unit, setUnit] = useState(display.unit);
  const [num, setNum] = useState(display.value);

  useEffect(() => {
    const d = toDisplay(value);
    setUnit(d.unit);
    setNum(d.value);
  }, [value]);

  const emit = (newNum, newUnit) => {
    const minutes = newNum * MULTIPLIERS[newUnit];
    if (minutes > 0) onChange(minutes);
  };

  return (
    <Group gap="xs" wrap="nowrap">
      {label && <span style={{ fontSize: '0.75rem', color: 'var(--mantine-color-dimmed)' }}>{label}</span>}
      <NumberInput
        value={num}
        onChange={(val) => {
          setNum(val);
          if (val >= 1) emit(val, unit);
        }}
        min={1}
        max={100}
        w={70}
        size={size}
      />
      <SegmentedControl
        value={unit}
        onChange={(u) => {
          setUnit(u);
          emit(num, u);
        }}
        data={UNITS}
        size={size}
      />
    </Group>
  );
}
