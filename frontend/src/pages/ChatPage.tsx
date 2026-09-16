import { useId, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { assistantApi } from '../api/endpoints'
import { extractErrorMessage } from '../api/client'
import { useCompany } from '../context/CompanyContext'
import { intentLabel, paramLabel } from '../lib/format'
import { ResultView } from '../components/ResultView'

type PendingStatus = 'pending' | 'confirmed' | 'cancelled'

interface PendingActionVM {
  id: number
  intent: string
  parameters: Record<string, unknown>
  status: PendingStatus
  result?: unknown
  error?: string
}

interface ChatMessageVM {
  id: string
  role: 'user' | 'assistant'
  text: string
  pendingAction?: PendingActionVM
  result?: unknown
}

let messageCounter = 0
function nextId(): string {
  messageCounter += 1
  return `m${messageCounter}`
}

function ParametersView({ parameters }: { parameters: Record<string, unknown> }) {
  const items = parameters.items
  return (
    <dl className="params-view">
      {Object.entries(parameters)
        .filter(([key, value]) => key !== 'items' && value !== '' && value !== null)
        .map(([key, value]) => (
          <div key={key}>
            <dt>{paramLabel(key)}</dt>
            <dd>{String(value)}</dd>
          </div>
        ))}
      {Array.isArray(items) && items.length > 0 && (
        <div>
          <dt>Ítems</dt>
          <dd>
            <ul>
              {items.map((item, index) => (
                <li key={`${index}-${JSON.stringify(item)}`}>
                  {Object.entries(item as Record<string, unknown>)
                    .map(([k, v]) => `${paramLabel(k)}: ${v}`)
                    .join(' · ')}
                </li>
              ))}
            </ul>
          </dd>
        </div>
      )}
    </dl>
  )
}

function PendingActionCard({
  pendingAction,
  onConfirm,
  onCancel,
}: {
  pendingAction: PendingActionVM
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <div className="pending-card">
      <strong>{intentLabel(pendingAction.intent)}</strong>
      <ParametersView parameters={pendingAction.parameters} />
      {pendingAction.status === 'pending' && (
        <div className="pending-actions">
          <button className="btn" type="button" onClick={onConfirm}>
            Confirmar
          </button>
          <button className="btn btn-secondary" type="button" onClick={onCancel}>
            Cancelar
          </button>
        </div>
      )}
      {pendingAction.status === 'confirmed' && (
        <>
          <p className="pending-status pending-status-confirmed">✅ Confirmado</p>
          {pendingAction.result !== undefined && <ResultView result={pendingAction.result} />}
        </>
      )}
      {pendingAction.status === 'cancelled' && (
        <p className="pending-status">❌ Cancelado</p>
      )}
      {pendingAction.error && <p className="error-banner">{pendingAction.error}</p>}
    </div>
  )
}

export function ChatPage() {
  const { activeCompany } = useCompany()
  const companyId = activeCompany!.id
  const [messages, setMessages] = useState<ChatMessageVM[]>([])
  const [conversationId, setConversationId] = useState<number | null>(null)
  const [input, setInput] = useState('')
  const [isSending, setIsSending] = useState(false)
  const inputId = useId()
  const listRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      listRef.current?.scrollTo?.({ top: listRef.current.scrollHeight, behavior: 'smooth' })
    })
  }

  const appendMessage = (message: ChatMessageVM) => {
    setMessages((prev) => [...prev, message])
    scrollToBottom()
  }

  const updatePendingAction = (messageId: string, patch: Partial<PendingActionVM>) => {
    setMessages((prev) =>
      prev.map((message) =>
        message.id === messageId && message.pendingAction
          ? { ...message, pendingAction: { ...message.pendingAction, ...patch } }
          : message,
      ),
    )
  }

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    const text = input.trim()
    if (!text || isSending) return

    appendMessage({ id: nextId(), role: 'user', text })
    setInput('')
    setIsSending(true)

    try {
      const response = await assistantApi.chat(companyId, text, conversationId)
      setConversationId(response.conversation_id)

      if (response.status === 'no_entendido' || response.status === 'error') {
        appendMessage({ id: nextId(), role: 'assistant', text: response.message })
      } else if (response.status === 'executed') {
        appendMessage({
          id: nextId(),
          role: 'assistant',
          text: 'Listo, aquí está la información.',
          result: response.result,
        })
      } else {
        appendMessage({
          id: nextId(),
          role: 'assistant',
          text: `Tengo listo: ${intentLabel(response.intent)}. ¿Confirmas?`,
          pendingAction: {
            id: response.pending_action_id,
            intent: response.intent,
            parameters: response.parameters,
            status: 'pending',
          },
        })
      }
    } catch (err) {
      appendMessage({ id: nextId(), role: 'assistant', text: extractErrorMessage(err) })
    } finally {
      setIsSending(false)
    }
  }

  const handleConfirm = async (messageId: string, pendingActionId: number) => {
    try {
      const response = await assistantApi.confirmIntent(companyId, pendingActionId)
      updatePendingAction(messageId, { status: 'confirmed', result: response.result })
    } catch (err) {
      updatePendingAction(messageId, { error: extractErrorMessage(err) })
    }
  }

  const handleCancel = async (messageId: string, pendingActionId: number) => {
    try {
      await assistantApi.cancelIntent(companyId, pendingActionId)
      updatePendingAction(messageId, { status: 'cancelled' })
    } catch (err) {
      updatePendingAction(messageId, { error: extractErrorMessage(err) })
    }
  }

  return (
    <div className="chat-page">
      <div className="chat-list" ref={listRef}>
        {messages.length === 0 && (
          <p className="chat-empty">
            Cuéntame qué necesitas: "Vendí 3 cafés a 2500", "¿Cuánto vendí hoy?",
            "Compré 20 cafés a 1500 a Distribuidora ABC"…
          </p>
        )}
        {messages.map((message) => (
          <div key={message.id} className={`chat-bubble chat-bubble-${message.role}`}>
            <p>{message.text}</p>
            {message.result !== undefined && <ResultView result={message.result} />}
            {message.pendingAction && (
              <PendingActionCard
                pendingAction={message.pendingAction}
                onConfirm={() => handleConfirm(message.id, message.pendingAction!.id)}
                onCancel={() => handleCancel(message.id, message.pendingAction!.id)}
              />
            )}
          </div>
        ))}
        {isSending && <div className="chat-bubble chat-bubble-assistant chat-typing">Pensando…</div>}
      </div>

      <form className="chat-input-bar" onSubmit={handleSubmit}>
        <label htmlFor={inputId} className="sr-only">
          Mensaje
        </label>
        <input
          id={inputId}
          type="text"
          placeholder="Escribe un mensaje…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={isSending}
        />
        <button className="btn" type="submit" disabled={isSending || !input.trim()}>
          Enviar
        </button>
      </form>
    </div>
  )
}
