/**
 * useCategories Hook - Fetch categories from backend API.
 *
 * Provides combined default + existing categories from the database.
 *
 * Usage:
 *   const { data: categories, isLoading, error } = useCategories();
 *   // categories.geographies: ['US', 'Europe', ...]
 *   // categories.industries: ['Technology', 'Healthcare', ...]
 */

import { useQuery } from '@tanstack/react-query';
import { getCategories } from '../api/client';

/**
 * Hook to fetch and cache categories.
 *
 * @returns {Object} Query result with data, isLoading, error, etc.
 */
export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: getCategories,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    gcTime: 30 * 60 * 1000, // Keep in cache for 30 minutes
  });
}

/**
 * Parse a comma-separated string into an array.
 * Also handles arrays (returns them as-is after filtering).
 *
 * @param {string|string[]} value - Comma-separated string (e.g., "US, Europe") or array
 * @returns {string[]} Array of trimmed values
 */
export function parseCommaSeparated(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.filter(Boolean);
  return value.split(',').map((v) => v.trim()).filter(Boolean);
}

export default useCategories;
