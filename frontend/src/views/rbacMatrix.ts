export const DENIED_RBAC_GRANT = 'Not Allowed'

export type RbacGrant = string

export type RbacMatrixRow = {
  office: string
  cells: Record<string, RbacGrant> | null
}

export type RbacMatrix = {
  verbs: string[]
  rows: RbacMatrixRow[]
}

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null
}

/** Validates the public `/matrices/rbac` response without granting fallbacks. */
export function parseRbacMatrix(payload: unknown): RbacMatrix {
  const data = record(payload)
  const verbs = Array.isArray(data?.verbs) ? data.verbs.filter((verb): verb is string => typeof verb === 'string') : []
  const rows = Array.isArray(data?.rows) ? data.rows.map((item): RbacMatrixRow => {
    const row = record(item)
    const rawCells = record(row?.cells)
    const cells = rawCells && Object.fromEntries(
      Object.entries(rawCells).filter(([, grant]): grant is RbacGrant => typeof grant === 'string'),
    )
    return { office: typeof row?.office === 'string' ? row.office : 'Unknown office', cells }
  }) : []
  return { verbs, rows }
}

/** Missing or malformed cells are always denied; they never grant authority. */
export function rbacGrant(row: RbacMatrixRow, verb: string): RbacGrant {
  return row.cells?.[verb] ?? DENIED_RBAC_GRANT
}
