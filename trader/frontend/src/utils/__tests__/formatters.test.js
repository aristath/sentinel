import { describe, it, expect } from 'vitest';
import { formatCurrency, formatPercent, formatNumber, formatDate, formatDateTime } from '../formatters';

describe('formatters', () => {
  describe('formatCurrency', () => {
    it('formats currency values correctly', () => {
      expect(formatCurrency(1234.56)).toMatch(/1,234.56/);
      expect(formatCurrency(0)).toMatch(/0.00/);
    });

    it('handles null/undefined', () => {
      expect(formatCurrency(null)).toBe('-');
      expect(formatCurrency(undefined)).toBe('-');
    });
  });

  describe('formatPercent', () => {
    it('formats percentages correctly', () => {
      expect(formatPercent(0.5)).toBe('50.0%');
      expect(formatPercent(0.123, 2)).toBe('12.30%');
    });

    it('handles null/undefined', () => {
      expect(formatPercent(null)).toBe('-');
      expect(formatPercent(undefined)).toBe('-');
    });
  });

  describe('formatNumber', () => {
    it('formats numbers correctly', () => {
      expect(formatNumber(123.456)).toBe('123.46');
      expect(formatNumber(123.456, 1)).toBe('123.5');
    });

    it('handles null/undefined', () => {
      expect(formatNumber(null)).toBe('-');
      expect(formatNumber(undefined)).toBe('-');
    });
  });

  describe('formatDate', () => {
    it('formats dates correctly', () => {
      const date = new Date('2024-01-15');
      const formatted = formatDate(date);
      expect(formatted).toBeTruthy();
    });

    it('handles null/undefined', () => {
      expect(formatDate(null)).toBe('-');
      expect(formatDate(undefined)).toBe('-');
    });
  });

  describe('formatDateTime', () => {
    it('formats date-time correctly', () => {
      const date = new Date('2024-01-15T10:30:00');
      const formatted = formatDateTime(date);
      expect(formatted).toBeTruthy();
    });

    it('handles null/undefined', () => {
      expect(formatDateTime(null)).toBe('-');
      expect(formatDateTime(undefined)).toBe('-');
    });
  });
});

