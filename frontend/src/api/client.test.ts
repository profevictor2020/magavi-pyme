import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, AuthRequiredError, apiFetch, extractErrorMessage, setAuthRequiredHandler } from './client'
import { clearTokens, setTokens } from './tokenStore'

function jsonResponse(body: unknown, init: { status?: number } = {}) {
  return new Response(JSON.stringify(body), {
    status: init.status ?? 200,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('apiFetch', () => {
  beforeEach(() => {
    clearTokens()
    setAuthRequiredHandler(null)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('adjunta Authorization y X-Company-Id cuando corresponde', async () => {
    setTokens('access-1', 'refresh-1')
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    await apiFetch('/products/', { companyId: 42 })

    const [, requestInit] = fetchMock.mock.calls[0]
    expect(requestInit.headers.Authorization).toBe('Bearer access-1')
    expect(requestInit.headers['X-Company-Id']).toBe('42')
  })

  it('reintenta una vez tras refrescar el access token cuando la API responde 401', async () => {
    setTokens('access-viejo', 'refresh-1')
    const fetchMock = vi
      .fn()
      // 1) request original -> 401
      .mockResolvedValueOnce(jsonResponse({ detail: 'expirado' }, { status: 401 }))
      // 2) POST /auth/refresh/ -> nuevo access
      .mockResolvedValueOnce(jsonResponse({ access: 'access-nuevo' }))
      // 3) reintento con el nuevo access -> 200
      .mockResolvedValueOnce(jsonResponse({ ok: true }))
    vi.stubGlobal('fetch', fetchMock)

    const result = await apiFetch<{ ok: boolean }>('/sales/', { companyId: 1 })

    expect(result).toEqual({ ok: true })
    expect(fetchMock).toHaveBeenCalledTimes(3)
    const lastCallHeaders = fetchMock.mock.calls[2][1].headers
    expect(lastCallHeaders.Authorization).toBe('Bearer access-nuevo')
  })

  it('limpia la sesión y avisa cuando el refresh también falla', async () => {
    setTokens('access-viejo', 'refresh-invalido')
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({}, { status: 401 }))
      .mockResolvedValueOnce(jsonResponse({}, { status: 401 }))
    vi.stubGlobal('fetch', fetchMock)

    const onAuthRequired = vi.fn()
    setAuthRequiredHandler(onAuthRequired)

    await expect(apiFetch('/sales/', { companyId: 1 })).rejects.toBeInstanceOf(AuthRequiredError)
    expect(onAuthRequired).toHaveBeenCalledTimes(1)
  })

  it('lanza ApiError con el cuerpo de la respuesta cuando no es exitosa', async () => {
    setTokens('access-1', 'refresh-1')
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: 'no encontrado' }, { status: 404 }))
    vi.stubGlobal('fetch', fetchMock)

    await expect(apiFetch('/products/999/', { companyId: 1 })).rejects.toMatchObject({
      status: 404,
    })
  })
})

describe('extractErrorMessage', () => {
  it('extrae el campo detail', () => {
    expect(extractErrorMessage(new ApiError(404, { detail: 'no encontrado' }))).toBe('no encontrado')
  })

  it('extrae mensajes de un cuerpo tipo lista (ValidationError de DRF)', () => {
    expect(extractErrorMessage(new ApiError(400, ['La propuesta expiró.']))).toBe('La propuesta expiró.')
  })

  it('devuelve el mensaje de un AuthRequiredError tal cual', () => {
    expect(extractErrorMessage(new AuthRequiredError('Sesión expirada'))).toBe('Sesión expirada')
  })
})
