import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'
import { clearTokens } from '../api/tokenStore'

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function LoginProbe() {
  const { user, login, logout } = useAuth()
  return (
    <div>
      <span data-testid="user">{user ? user.email : 'anon'}</span>
      <button onClick={() => login('marcela@almacen.cl', 'clave-segura')}>Entrar</button>
      <button onClick={logout}>Salir</button>
    </div>
  )
}

describe('AuthProvider', () => {
  beforeEach(() => {
    clearTokens()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('actualiza el usuario tras un login exitoso, y lo limpia al cerrar sesión', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ access: 'a1', refresh: 'r1' })) // /auth/login/
      .mockResolvedValueOnce(
        jsonResponse({ id: 1, email: 'marcela@almacen.cl', first_name: 'Marcela' }),
      ) // /auth/me/
    vi.stubGlobal('fetch', fetchMock)

    render(
      <AuthProvider>
        <LoginProbe />
      </AuthProvider>,
    )

    expect(screen.getByTestId('user')).toHaveTextContent('anon')

    const user = userEvent.setup()
    await user.click(screen.getByText('Entrar'))

    await waitFor(() => expect(screen.getByTestId('user')).toHaveTextContent('marcela@almacen.cl'))

    await user.click(screen.getByText('Salir'))
    expect(screen.getByTestId('user')).toHaveTextContent('anon')
  })
})
