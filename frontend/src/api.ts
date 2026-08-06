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
export type Equipment = { id: string; tag: string; name: string; entity_class: string }

const apiBaseUrl = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:8088').replace(/\/$/, '')

async function getItems<T>(path: string): Promise<T[]> {
  const response = await fetch(`${apiBaseUrl}${path}`)
  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`)
  }
  const body = (await response.json()) as { items?: T[] }
  return body.items ?? []
}

async function postItems<T>(path: string, body: object): Promise<T[]> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw new Error(`Request failed (${response.status})`)
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
