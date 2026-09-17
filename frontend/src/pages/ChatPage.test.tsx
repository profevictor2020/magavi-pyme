import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ChatPage } from './ChatPage'
import { assistantApi } from '../api/endpoints'
import type { Company } from '../api/types'

vi.mock('../context/CompanyContext', () => ({
  useCompany: () => ({
    activeCompany: { id: 7, name: 'Almacén Marcela', rut: '1-9', is_active: true, created_at: '', role: 'owner' } satisfies Company,
  }),
}))

vi.mock('../api/endpoints', () => ({
  assistantApi: {
    chat: vi.fn(),
    confirmIntent: vi.fn(),
    cancelIntent: vi.fn(),
  },
}))

const mockedAssistantApi = vi.mocked(assistantApi)

describe('ChatPage', () => {
  it('propone una acción y la confirma, mostrando el resultado registrado', async () => {
    mockedAssistantApi.chat.mockResolvedValue({
      conversation_id: 1,
      status: 'pending_confirmation',
      pending_action_id: 55,
      intent: 'crear_venta',
      parameters: { items: [{ product_id: 5, quantity: '3', unit_price: '2500' }] },
      expires_at: '2026-09-16T12:00:00Z',
    })
    mockedAssistantApi.confirmIntent.mockResolvedValue({
      status: 'confirmed',
      result: {
        id: 1,
        sold_at: '2026-09-16T12:00:00Z',
        customer_name: '',
        total: '7500.00',
        status: 'confirmed',
        source: 'assistant',
        created_at: '2026-09-16T12:00:00Z',
        items: [{ id: 1, product: 5, quantity: '3', unit_price: '2500.00', subtotal: '7500.00' }],
      },
    })

    const user = userEvent.setup()
    render(<ChatPage />)

    await user.type(screen.getByPlaceholderText('Escribe un mensaje…'), 'Vendí 3 cafés a 2500')
    await user.click(screen.getByText('Enviar'))

    await waitFor(() => expect(screen.getByText('Confirmar')).toBeInTheDocument())
    expect(mockedAssistantApi.chat).toHaveBeenCalledWith(7, 'Vendí 3 cafés a 2500', null)

    await user.click(screen.getByText('Confirmar'))

    await waitFor(() => expect(screen.getByText('✅ Confirmado')).toBeInTheDocument())
    expect(mockedAssistantApi.confirmIntent).toHaveBeenCalledWith(7, 55)
    expect(screen.getAllByText(/\$7\.500|\$7,500/).length).toBeGreaterThan(0)
  })

  it('permite cancelar una propuesta pendiente', async () => {
    mockedAssistantApi.chat.mockResolvedValue({
      conversation_id: 2,
      status: 'pending_confirmation',
      pending_action_id: 56,
      intent: 'ajustar_inventario',
      parameters: { product_id: 5, cantidad: '-2', motivo: 'merma' },
      expires_at: '2026-09-16T12:00:00Z',
    })
    mockedAssistantApi.cancelIntent.mockResolvedValue({ status: 'cancelled' })

    const user = userEvent.setup()
    render(<ChatPage />)

    await user.type(screen.getByPlaceholderText('Escribe un mensaje…'), 'se echaron a perder 2 cafes')
    await user.click(screen.getByText('Enviar'))

    await waitFor(() => expect(screen.getByText('Cancelar')).toBeInTheDocument())
    await user.click(screen.getByText('Cancelar'))

    await waitFor(() => expect(screen.getByText('❌ Cancelado')).toBeInTheDocument())
    expect(mockedAssistantApi.cancelIntent).toHaveBeenCalledWith(7, 56)
  })

  it('muestra el mensaje del asistente cuando no logra entender', async () => {
    mockedAssistantApi.chat.mockResolvedValue({
      conversation_id: 3,
      status: 'no_entendido',
      message: '¿Puedes darme más detalles?',
    })

    const user = userEvent.setup()
    render(<ChatPage />)

    await user.type(screen.getByPlaceholderText('Escribe un mensaje…'), 'vendí unos cafés')
    await user.click(screen.getByText('Enviar'))

    await waitFor(() => expect(screen.getByText('¿Puedes darme más detalles?')).toBeInTheDocument())
  })

  it('muestra la respuesta directa del asistente cuando no hace falta ejecutar una acción', async () => {
    mockedAssistantApi.chat.mockResolvedValue({
      conversation_id: 3,
      status: 'answered',
      message: 'Ese gasto de servicios no tiene una descripción registrada.',
    })

    const user = userEvent.setup()
    render(<ChatPage />)

    await user.type(screen.getByPlaceholderText('Escribe un mensaje…'), 'y este gasto de qué es')
    await user.click(screen.getByText('Enviar'))

    await waitFor(() =>
      expect(
        screen.getByText('Ese gasto de servicios no tiene una descripción registrada.'),
      ).toBeInTheDocument(),
    )
  })
})
