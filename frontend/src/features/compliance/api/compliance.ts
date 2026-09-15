/**
 * API hooks for compliance frameworks.
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import type { Framework, FrameworkRequirement, CountermeasureStandardMapping } from '@/features/compliance/types/compliance'

// Types for instance-level mappings

export interface InstanceCountermeasureStandard {
  id: number
  countermeasure: number
  requirement: number
  frameworkName: string
  frameworkSlug: string
  sectionCode: string
  requirementDescription: string
  sufficiency: 'full' | 'partial'
  createdAt: string
  updatedAt: string
}

// Query keys
export const complianceKeys = {
  all: ['compliance'] as const,
  frameworks: () => [...complianceKeys.all, 'frameworks'] as const,
  framework: (id: number) => [...complianceKeys.all, 'framework', id] as const,
  requirements: (frameworkId?: number) => [...complianceKeys.all, 'requirements', frameworkId] as const,
  countermeasureMappings: (countermeasureId?: number) => [...complianceKeys.all, 'mappings', countermeasureId] as const,
  instanceMappings: (countermeasureId: number) =>
    [...complianceKeys.all, 'instance-mappings', countermeasureId] as const,
  complianceDrift: (threatModelId: string) =>
    [...complianceKeys.all, 'drift', threatModelId] as const,
}

/**
 * Fetch all compliance frameworks.
 */
export function useFrameworks() {
  return useQuery({
    queryKey: complianceKeys.frameworks(),
    queryFn: async () => {
      const response = await api.get<{ results: Framework[] } | Framework[]>('/frameworks/')
      return Array.isArray(response) ? response : response.results
    },
  })
}

/**
 * Fetch a single framework by ID.
 */
export function useFramework(id: number | null) {
  return useQuery({
    queryKey: complianceKeys.framework(id!),
    queryFn: () => api.get<Framework>(`/frameworks/${id}/`),
    enabled: id !== null,
  })
}

/**
 * Fetch requirements for a framework.
 */
export function useFrameworkRequirements(frameworkId: number | null) {
  return useQuery({
    queryKey: complianceKeys.requirements(frameworkId ?? undefined),
    queryFn: async () => {
      const url = frameworkId
        ? `/requirements/?framework=${frameworkId}`
        : '/requirements/'
      const response = await api.get<{ results: FrameworkRequirement[] } | FrameworkRequirement[]>(url)
      return Array.isArray(response) ? response : response.results
    },
    enabled: frameworkId !== null,
  })
}

/**
 * Fetch countermeasure-standard mappings.
 */
export function useCountermeasureMappings(countermeasureId?: number) {
  return useQuery({
    queryKey: complianceKeys.countermeasureMappings(countermeasureId),
    queryFn: async () => {
      const url = countermeasureId
        ? `/countermeasure-standards/?countermeasure_library=${countermeasureId}`
        : '/countermeasure-standards/'
      const response = await api.get<{ results: CountermeasureStandardMapping[] } | CountermeasureStandardMapping[]>(url)
      return Array.isArray(response) ? response : response.results
    },
  })
}

// ============================================
// Instance-level Compliance Mappings
// ============================================

/**
 * Fetch instance-level compliance mappings for a countermeasure.
 * Unified: works for both component and flow countermeasures.
 */
export function useInstanceMappings(countermeasureId: number | null) {
  return useQuery({
    queryKey: complianceKeys.instanceMappings(countermeasureId!),
    queryFn: async () => {
      const response = await api.get<{ results: InstanceCountermeasureStandard[] } | InstanceCountermeasureStandard[]>(
        `/instance-countermeasure-standards/?countermeasure=${countermeasureId}`
      )
      return Array.isArray(response) ? response : response.results
    },
    enabled: countermeasureId !== null,
  })
}

/**
 * Create an instance-level compliance mapping for a countermeasure.
 * Unified: works for both component and flow countermeasures.
 */
export function useCreateInstanceMapping() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: {
      countermeasure: number
      requirement: number
      sufficiency: 'full' | 'partial'
    }) =>
      api.post<InstanceCountermeasureStandard>('/instance-countermeasure-standards/', {
        countermeasure: data.countermeasure,
        requirement: data.requirement,
        sufficiency: data.sufficiency,
      }),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({
        queryKey: complianceKeys.instanceMappings(variables.countermeasure),
      })
      queryClient.invalidateQueries({ queryKey: ['threat-model-threats'] })
    },
  })
}

/**
 * Update an instance-level compliance mapping.
 */
export function useUpdateInstanceMapping() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: {
      id: number
      sufficiency: 'full' | 'partial'
    }) =>
      api.patch<InstanceCountermeasureStandard>(`/instance-countermeasure-standards/${data.id}/`, {
        sufficiency: data.sufficiency,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: complianceKeys.all })
      queryClient.invalidateQueries({ queryKey: ['threat-model-threats'] })
    },
  })
}

/**
 * Delete an instance-level compliance mapping.
 */
export function useDeleteInstanceMapping() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (id: number) => api.delete(`/instance-countermeasure-standards/${id}/`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: complianceKeys.all })
      queryClient.invalidateQueries({ queryKey: ['threat-model-threats'] })
    },
  })
}

// ============================================
// Compliance Drift Detection
// ============================================

export interface ComplianceDriftResult {
  hasDrift: boolean
  totalAdditions: number
  totalRemovals: number
  totalUpdates: number
  affectedCountermeasures: number
}

export interface RefreshComplianceResult {
  standardsAdded: number
  standardsRemoved: number
  standardsUpdated: number
  countermeasuresAffected: number
}

/**
 * Check for compliance drift between instance and library mappings.
 */
export function useComplianceDrift(threatModelId: string | undefined) {
  return useQuery({
    queryKey: complianceKeys.complianceDrift(threatModelId!),
    queryFn: () =>
      api.get<ComplianceDriftResult>(`/threat-models/${threatModelId}/compliance_drift/`),
    enabled: !!threatModelId,
    staleTime: 60_000,
  })
}

/**
 * Refresh instance compliance mappings from library sources.
 */
export function useRefreshCompliance() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (threatModelId: string) =>
      api.post<RefreshComplianceResult>(`/threat-models/${threatModelId}/refresh_compliance/`),
    onSuccess: (_, threatModelId) => {
      queryClient.invalidateQueries({
        queryKey: complianceKeys.complianceDrift(threatModelId),
      })
      queryClient.invalidateQueries({ queryKey: complianceKeys.all })
      queryClient.invalidateQueries({ queryKey: ['threat-model-threats'] })
    },
  })
}
