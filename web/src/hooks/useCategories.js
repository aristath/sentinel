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

const API_BASE = '/api';

/**
 * Fetch categories from the backend API.
 * @returns {Promise<{geographies: string[], industries: string[]}>}
 */
async function fetchCategories() {
  const response = await fetch(`${API_BASE}/meta/categories`);
  if (!response.ok) {
    throw new Error('Failed to fetch categories');
  }
  return response.json();
}

/**
 * Hook to fetch and cache categories.
 *
 * @returns {Object} Query result with data, isLoading, error, etc.
 */
export function useCategories() {
  return useQuery({
    queryKey: ['categories'],
    queryFn: fetchCategories,
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
    gcTime: 30 * 60 * 1000, // Keep in cache for 30 minutes
  });
}

/**
 * Get geography options formatted for Mantine TagsInput.
 *
 * @param {string[]} geographies - Array of geography values
 * @returns {string[]} Options for TagsInput component
 */
export function getGeographyOptions(geographies = []) {
  return geographies;
}

/**
 * Get industry options formatted for Mantine TagsInput.
 *
 * @param {string[]} industries - Array of industry values
 * @returns {string[]} Options for TagsInput component
 */
export function getIndustryOptions(industries = []) {
  return industries;
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
