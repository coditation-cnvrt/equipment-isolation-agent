export type IsolationViewMode = 'drawing' | 'isolation'

export type IsolationMapLayer = 'target' | 'points' | 'blockers' | 'downstream'

export type IsolationMapLayers = Record<IsolationMapLayer, boolean>

export const DEFAULT_ISOLATION_MAP_LAYERS: IsolationMapLayers = {
  target: true,
  points: true,
  blockers: true,
  downstream: true,
}
