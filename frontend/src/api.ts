import type { HiltGraphInput, HiltSymbol } from '@coditation-cnvrt/p360-hitl-viewer'

export type Project = { id: string; name: string; status: string }
export type Collection = { id: string; name: string }
export type Drawing = { id: string; name: string; status: string; current_phase: string; input_file_type: string }
export type UniGraphProject = {
  id: string
  name: string
  state: string
  status: string
  export_type: string
  has_taxonomy: boolean
}
export type Equipment = {
  id: string
  tag: string
  name: string
  entity_class: string
  node_id: string
  job_id: string
  job_name: string
}

export type IsolationPoint = {
  uuid: string
  selection_id?: string
  drawing_entity_id?: string | null
  source_visual_id?: string | null
  visual_id?: string | null
  tag_number?: string | null
  source_component_tag?: string | null
  entity_class?: string | null
  isolation_method?: string | null
  requires_manual_review?: boolean
  positive_isolation_requires_field_confirmation?: boolean
  bbox?: number[]
  bbox_source?: string | null
  bbox_match_method?: string | null
  validation_state?: 'barrier' | 'positive' | 'manual' | 'rejected'
}

export type AssuranceReason = {
  reason_id: string
  code: string
  boundary_id?: string | null
  boundary_component_id?: string | null
  boundary_label?: string | null
  boundary_count?: number
  candidate_id?: string
  check_name?: string
  basis?: string | null
  path_node_ids?: string[]
  path_node_classes?: string[]
  required_action?: string
  terminal?: {
    entity_id?: string | null
    entity_type?: string | null
    entity_class?: string | null
    tag?: string | null
    display_text?: string[]
    partner_mapping_status?: 'resolved' | 'missing' | 'invalid' | 'not_applicable' | string
    terminal_reason?: string
  } | null
}

export type AssuranceExplanation = {
  schema_version: '1.0' | string
  determination: string
  primary_reasons: AssuranceReason[]
  outstanding_requirements: AssuranceReason[]
  summary: {
    primary_reason_count: number
    outstanding_requirement_count: number
  }
}

export type IsolationValidation = {
  assurance_status?: string
  rationale?: string
  terminal?: boolean
  assurance_explanation?: AssuranceExplanation
  expected_boundary_count?: number
  covered_boundary_source_count?: number
  missing_boundary_count?: number
  unselected_boundary_sources?: unknown[]
  unresolved_isolation_obligations?: unknown[]
  unresolved_evidence_checks?: unknown[]
  missing_evidence?: unknown[]
  barrier_candidate_ids?: Array<string | number>
  positive_candidate_ids?: Array<string | number>
  manual_review_candidate_ids?: Array<string | number>
}

export type IsolationPlan = {
  assurance_status: string
  isolation_validation?: IsolationValidation | null
  isolation_points?: IsolationPoint[]
  unselected_boundary_sources?: unknown[]
  manual_visual_isolation_checks?: unknown[]
  downstream_impact?: { status?: string; warnings?: unknown[] } | null
  loto_procedure?: {
    phases?: Array<{
      phase?: number
      ref?: string
      title?: string
      objective?: string
      field_action_required?: unknown[]
    }>
  } | null
}

export type IsolationResult = {
  result_schema_version?: '1.0'
  error: boolean
  message: string
  data: IsolationPlan[]
}

export type IsolationRunAccepted = {
  request_schema_version?: '1.0'
  result_schema_version?: '1.0'
  run_id: string
  status: string
  status_url: string
  events_url: string
}

export type IsolationRunStatus = {
  run_id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | string
  equipment_tag: string
  runner: string
  created_at: number
  started_at?: number | null
  finished_at?: number | null
  request?: {
    request_schema_version?: '1.0'
    job_id?: string
    job_name?: string
    cnvrt_project_id?: string
    collection_id?: string
    unigraph_project_id?: string
    selected_asset?: {
      hilt_entity_id: string
      tag: string
      entity_class?: string
      selection_source: 'hilt_equipment_list' | 'hilt_canvas'
    }
    work_scope?: { intrusive_work?: boolean; high_risk_service?: boolean }
  }
  agent?: {
    progress?: { kind?: string; tool?: string; updated_at?: number }
    models_used?: string[]
    orchestration_error?: { kind?: string; code?: number | null; status?: string | null; message?: string } | null
  } | null
  error?: { kind?: string; message?: string } | null
}

export type IsolationPlanSourceRun = {
  run_id: string
  runner: string
  status: string
  equipment_tag: string
  created_at?: string | null
  assurance_status?: string | null
  job_id: string
  job_name: string
  cnvrt_project_id: string
  collection_id: string
  unigraph_project_id: string
  request: IsolationRunStatus['request'] & { collection_name?: string }
  agent?: IsolationRunStatus['agent'] | null
  result_url: string
  trace_url: string
}

export type IsolationPlanVersionSummary = {
  plan_version_id: string
  parent_plan_version_id?: string | null
  version_no: number
  derivation_status: string
  input_hash: string
  model_hash: string
  derived_at: string
  superseded_at?: string | null
  source_run: IsolationPlanSourceRun
}

export type SavedIsolationPlan = {
  plan_id: string
  plan_number: string
  active_plan_version_id?: string | null
  mode: string
  lifecycle_state: string
  area_code?: string | null
  created_at: string
  latest_plan_version_id: string
  latest_version: IsolationPlanVersionSummary
  versions?: IsolationPlanVersionSummary[]
}

export type CreateIsolationRunInput = {
  equipmentTag: string
  equipmentHiltEntityId: string
  equipmentEntityClass: string
  jobName: string
  jobId: string
  cnvrtProjectId: string
  collectionId: string
  collectionName: string
  unigraphProjectId: string
  intrusiveWork: boolean
  highRiskService: boolean
}

import { authenticationRequiredEvent, getStoredAccessToken } from './auth-storage'

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8088').replace(/\/$/, '')

function requestHeaders(json = false): HeadersInit {
  const headers: Record<string, string> = {}
  if (json) headers['Content-Type'] = 'application/json'
  const accessToken = getStoredAccessToken()
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`
  return headers
}

async function responseError(response: Response): Promise<Error> {
  let message = `Request failed (${response.status})`
  try {
    const body = await response.json() as { detail?: string | { message?: string } }
    const detail = body.detail
    if (typeof detail === 'string') message = detail
    else if (detail?.message) message = detail.message
  } catch {
    // Keep the HTTP status fallback when the body is not JSON.
  }
  if (response.status === 401) {
    window.dispatchEvent(new Event(authenticationRequiredEvent))
    message = 'Your CNVRT authentication has expired. Sign in again.'
  }
  return new Error(message)
}

async function getItems<T>(path: string): Promise<T[]> {
  const response = await fetch(`${apiBaseUrl}${path}`, { headers: requestHeaders() })
  if (!response.ok) throw await responseError(response)
  const body = (await response.json()) as { items?: T[] }
  return body.items ?? []
}

async function postItems<T>(path: string, body: object): Promise<T[]> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: 'POST',
    headers: requestHeaders(true),
    body: JSON.stringify(body),
  })
  if (!response.ok) throw await responseError(response)
  return ((await response.json()) as { items?: T[] }).items ?? []
}

export const getProjects = () => getItems<Project>('/planning-context/projects')
export const getCollections = (projectId: string) =>
  getItems<Collection>(`/planning-context/projects/${projectId}/collections`)
export const getDrawings = (projectId: string, collectionId: string) =>
  getItems<Drawing>(`/planning-context/projects/${projectId}/collections/${collectionId}/drawings`)
export const getUniGraphProjects = (projectId: string, collectionId: string) =>
  getItems<UniGraphProject>(`/planning-context/projects/${projectId}/collections/${collectionId}/unigraph-projects`)
export const getEquipment = (cnvrtProjectId: string, collectionId: string, unigraphProjectId: string, collectionName: string) =>
  postItems<Equipment>('/equipment', { cnvrt_project_id: cnvrtProjectId, collection_id: collectionId, unigraph_project_id: unigraphProjectId, collection_name: collectionName })
export const drawingImageUrl = (projectId: string, collectionId: string, drawingId: string) =>
  `${apiBaseUrl}/planning-context/projects/${projectId}/collections/${collectionId}/drawings/${drawingId}/image`
export async function getHiltGraph(jobId: string): Promise<HiltGraphInput> {
  const response = await fetch(`${apiBaseUrl}/planning-context/drawings/${jobId}/hilt-graph`, { headers: requestHeaders() })
  if (!response.ok) throw await responseError(response)
  return (await response.json()) as HiltGraphInput
}
export async function getHiltSymbols(symbolProjectId: string): Promise<HiltSymbol[]> {
  const response = await fetch(`${apiBaseUrl}/planning-context/symbol-projects/${symbolProjectId}/symbols`, { headers: requestHeaders() })
  if (!response.ok) throw await responseError(response)
  const payload = await response.json() as unknown
  if (!Array.isArray(payload)) throw new Error('Project symbol response is not a list')
  return payload as HiltSymbol[]
}
export async function getEquipmentBBox(jobId: string, nodeId: string): Promise<number[]> {
  const response = await fetch(`${apiBaseUrl}/planning-context/drawings/${jobId}/equipment/${nodeId}/bbox`, { headers: requestHeaders() })
  if (!response.ok) return []
  return ((await response.json()) as { bbox?: number[] }).bbox ?? []
}

export async function createIsolationRun(input: CreateIsolationRunInput): Promise<IsolationRunAccepted> {
  const response = await fetch(`${apiBaseUrl}/isolation-runs`, {
    method: 'POST',
    headers: requestHeaders(true),
    body: JSON.stringify({
      request_schema_version: '1.0',
      equipment_tag: input.equipmentTag,
      selected_asset: {
        hilt_entity_id: input.equipmentHiltEntityId,
        tag: input.equipmentTag,
        entity_class: input.equipmentEntityClass,
        selection_source: 'hilt_equipment_list',
      },
      job_name: input.jobName,
      job_id: input.jobId,
      cnvrt_project_id: input.cnvrtProjectId,
      collection_id: input.collectionId,
      collection_name: input.collectionName,
      unigraph_project_id: input.unigraphProjectId,
      work_scope: {
        intrusive_work: input.intrusiveWork,
        high_risk_service: input.highRiskService,
      },
    }),
  })
  if (!response.ok) throw await responseError(response)
  return await response.json() as IsolationRunAccepted
}

export async function createIsolationPlanFromRun(runId: string, areaCode?: string): Promise<SavedIsolationPlan> {
  const response = await fetch(`${apiBaseUrl}/isolation-plans/from-run`, {
    method: 'POST',
    headers: requestHeaders(true),
    body: JSON.stringify({ run_id: runId, area_code: areaCode?.trim() || null }),
  })
  if (!response.ok) throw await responseError(response)
  return await response.json() as SavedIsolationPlan
}

export async function getIsolationPlans(filters: {
  equipmentTag?: string
  jobId?: string
  cnvrtProjectId?: string
  collectionId?: string
  unigraphProjectId?: string
  lifecycleState?: string
  planNumber?: string
  limit?: number
} = {}): Promise<SavedIsolationPlan[]> {
  const params = new URLSearchParams()
  if (filters.equipmentTag) params.set('equipment_tag', filters.equipmentTag)
  if (filters.jobId) params.set('job_id', filters.jobId)
  if (filters.cnvrtProjectId) params.set('cnvrt_project_id', filters.cnvrtProjectId)
  if (filters.collectionId) params.set('collection_id', filters.collectionId)
  if (filters.unigraphProjectId) params.set('unigraph_project_id', filters.unigraphProjectId)
  if (filters.lifecycleState) params.set('lifecycle_state', filters.lifecycleState)
  if (filters.planNumber) params.set('plan_number', filters.planNumber)
  params.set('limit', String(filters.limit ?? 20))
  return getItems<SavedIsolationPlan>(`/isolation-plans?${params.toString()}`)
}

export async function getIsolationPlan(planId: string): Promise<SavedIsolationPlan> {
  const response = await fetch(`${apiBaseUrl}/isolation-plans/${encodeURIComponent(planId)}`, { headers: requestHeaders() })
  if (!response.ok) throw await responseError(response)
  return await response.json() as SavedIsolationPlan
}

export async function getIsolationRuns(filters: {
  equipmentTag?: string
  jobId?: string
  cnvrtProjectId?: string
  collectionId?: string
  unigraphProjectId?: string
  status?: string
  limit?: number
} = {}): Promise<IsolationRunStatus[]> {
  const params = new URLSearchParams()
  if (filters.equipmentTag) params.set('equipment_tag', filters.equipmentTag)
  if (filters.jobId) params.set('job_id', filters.jobId)
  if (filters.cnvrtProjectId) params.set('cnvrt_project_id', filters.cnvrtProjectId)
  if (filters.collectionId) params.set('collection_id', filters.collectionId)
  if (filters.unigraphProjectId) params.set('unigraph_project_id', filters.unigraphProjectId)
  if (filters.status) params.set('status', filters.status)
  params.set('limit', String(filters.limit ?? 20))
  return getItems<IsolationRunStatus>(`/isolation-runs?${params.toString()}`)
}

export type IsolationRunEvent = {
  kind: string
  payload?: Record<string, unknown>
}

export async function streamIsolationRunEvents(
  runId: string,
  callbacks: {
    onEvent?: (event: IsolationRunEvent) => void
    onDone?: (status?: string) => void
  },
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${apiBaseUrl}/isolation-runs/${encodeURIComponent(runId)}/events`, {
    headers: { ...requestHeaders(), Accept: 'text/event-stream' },
    signal,
  })
  if (!response.ok) throw await responseError(response)
  if (!response.body) throw new Error('The run event stream has no response body.')

  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  let eventName = 'message'
  let dataLines: string[] = []

  const dispatch = () => {
    if (!dataLines.length) return
    const rawData = dataLines.join('\n')
    let data: unknown
    try {
      data = JSON.parse(rawData)
    } catch {
      data = { kind: eventName, payload: { text: rawData } }
    }
    if (eventName === 'done') {
      const payload = data as { status?: string }
      callbacks.onDone?.(payload.status)
    } else {
      const event = data as IsolationRunEvent
      callbacks.onEvent?.(event.kind ? event : { kind: eventName, payload: data as Record<string, unknown> })
    }
    eventName = 'message'
    dataLines = []
  }

  while (true) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    const lines = buffer.split(/\r?\n/)
    buffer = lines.pop() ?? ''
    for (const line of lines) {
      if (!line) dispatch()
      else if (line.startsWith('event:')) eventName = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
    }
  }
  if (buffer) {
    if (buffer.startsWith('data:')) dataLines.push(buffer.slice(5).trimStart())
    dispatch()
  }
}

export async function getIsolationRun(runId: string): Promise<IsolationRunStatus> {
  const response = await fetch(`${apiBaseUrl}/isolation-runs/${encodeURIComponent(runId)}`, { headers: requestHeaders() })
  if (!response.ok) throw await responseError(response)
  return await response.json() as IsolationRunStatus
}

export async function getIsolationResult(runId: string): Promise<IsolationResult> {
  const response = await fetch(`${apiBaseUrl}/isolation-runs/${encodeURIComponent(runId)}/result`, { headers: requestHeaders() })
  if (!response.ok) throw await responseError(response)
  return await response.json() as IsolationResult
}
