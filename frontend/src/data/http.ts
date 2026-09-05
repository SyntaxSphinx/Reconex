async function readDetail(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    return undefined
  }
}

export function apiErrorMessage(status: number, detail: unknown, fallback: string): string {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (
    detail &&
    typeof detail === 'object' &&
    'detail' in detail &&
    typeof (detail as { detail: unknown }).detail === 'string'
  ) {
    return (detail as { detail: string }).detail
  }
  return `${fallback} (${status})`
}

export async function apiGet<T>(path: string, fallback: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(apiErrorMessage(response.status, await readDetail(response), fallback))
  }
  return (await response.json()) as T
}

export async function apiGetOrNull<T>(path: string, fallback: string): Promise<T | null> {
  const response = await fetch(path)
  if (response.status === 404) return null
  if (!response.ok) {
    throw new Error(apiErrorMessage(response.status, await readDetail(response), fallback))
  }
  return (await response.json()) as T
}

export async function apiPost<T>(
  path: string,
  fallback: string,
  body?: unknown,
): Promise<T> {
  const response = await fetch(path, {
    method: 'POST',
    headers:
      body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    throw new Error(apiErrorMessage(response.status, await readDetail(response), fallback))
  }
  return (await response.json()) as T
}
