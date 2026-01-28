/**
 * useAllocation Hook - Fetch allocation data from backend API.
 *
 * Provides current allocations, targets, and mutations for saving.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getAllocation,
  getAllocationTargets,
  getAvailableGeographies,
  getAvailableIndustries,
  saveGeographyTargets,
  saveIndustryTargets,
  deleteGeographyTarget,
  deleteIndustryTarget,
} from '../api/client';

export function useAllocation() {
  return useQuery({
    queryKey: ['allocation', 'current'],
    queryFn: getAllocation,
  });
}

export function useAllocationTargets() {
  return useQuery({
    queryKey: ['allocation', 'targets'],
    queryFn: getAllocationTargets,
  });
}

export function useAvailableGeographies() {
  return useQuery({
    queryKey: ['allocation', 'geographies'],
    queryFn: getAvailableGeographies,
  });
}

export function useAvailableIndustries() {
  return useQuery({
    queryKey: ['allocation', 'industries'],
    queryFn: getAvailableIndustries,
  });
}

export function useSaveGeographyTargets() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (targets) => saveGeographyTargets(targets),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['allocation', 'current'] });
      queryClient.invalidateQueries({ queryKey: ['allocation', 'targets'] });
    },
  });
}

export function useSaveIndustryTargets() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (targets) => saveIndustryTargets(targets),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['allocation', 'current'] });
      queryClient.invalidateQueries({ queryKey: ['allocation', 'targets'] });
    },
  });
}

export function useDeleteGeographyTarget() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (name) => deleteGeographyTarget(name),
    onMutate: async (name) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['allocation', 'geographies'] });
      await queryClient.cancelQueries({ queryKey: ['allocation', 'targets'] });

      // Snapshot the previous values
      const prevGeographies = queryClient.getQueryData(['allocation', 'geographies']);
      const prevTargets = queryClient.getQueryData(['allocation', 'targets']);

      // Optimistically update geographies list
      queryClient.setQueryData(['allocation', 'geographies'], (old) => {
        if (!old) return old;
        return {
          geographies: old.geographies.filter((g) => g !== name),
        };
      });

      // Optimistically update targets
      queryClient.setQueryData(['allocation', 'targets'], (old) => {
        if (!old) return old;
        const { [name]: removed, ...rest } = old.geography || {};
        return { ...old, geography: rest };
      });

      return { prevGeographies, prevTargets };
    },
    onError: (err, name, ctx) => {
      // Rollback on error
      if (ctx?.prevGeographies) {
        queryClient.setQueryData(['allocation', 'geographies'], ctx.prevGeographies);
      }
      if (ctx?.prevTargets) {
        queryClient.setQueryData(['allocation', 'targets'], ctx.prevTargets);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['allocation'] });
      queryClient.invalidateQueries({ queryKey: ['recommendations'] });
      queryClient.invalidateQueries({ queryKey: ['unified'] });
    },
  });
}

export function useDeleteIndustryTarget() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (name) => deleteIndustryTarget(name),
    onMutate: async (name) => {
      // Cancel any outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['allocation', 'industries'] });
      await queryClient.cancelQueries({ queryKey: ['allocation', 'targets'] });

      // Snapshot the previous values
      const prevIndustries = queryClient.getQueryData(['allocation', 'industries']);
      const prevTargets = queryClient.getQueryData(['allocation', 'targets']);

      // Optimistically update industries list
      queryClient.setQueryData(['allocation', 'industries'], (old) => {
        if (!old) return old;
        return {
          industries: old.industries.filter((i) => i !== name),
        };
      });

      // Optimistically update targets
      queryClient.setQueryData(['allocation', 'targets'], (old) => {
        if (!old) return old;
        const { [name]: removed, ...rest } = old.industry || {};
        return { ...old, industry: rest };
      });

      return { prevIndustries, prevTargets };
    },
    onError: (err, name, ctx) => {
      // Rollback on error
      if (ctx?.prevIndustries) {
        queryClient.setQueryData(['allocation', 'industries'], ctx.prevIndustries);
      }
      if (ctx?.prevTargets) {
        queryClient.setQueryData(['allocation', 'targets'], ctx.prevTargets);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['allocation'] });
      queryClient.invalidateQueries({ queryKey: ['recommendations'] });
      queryClient.invalidateQueries({ queryKey: ['unified'] });
    },
  });
}
