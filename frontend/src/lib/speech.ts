// Voz para el chat (ver docs/DECISIONS.md ADR-016): reconocimiento y
// síntesis de voz vía la Web Speech API del navegador. La síntesis
// (hablar) corre 100% en el dispositivo, sin red — el reconocimiento
// (escuchar), en la mayoría de navegadores (Chrome incluido), manda el
// audio al servidor del fabricante para transcribirlo. Es una excepción
// documentada y acotada, igual que DeepSeek en ADR-010: no reemplaza el
// plan de un motor de voz autoalojado (Whisper) para producción real.
import { formatCLPSpoken, formatQuantity } from './format'
import {
  isLowStockList,
  isMovement,
  isPeriodSummary,
  isProduct,
  isProductList,
  isProductSalesSummary,
  isReceipt,
  isTopSellingList,
} from './resultShapes'

const SPEECH_LANG = 'es-CL'

// Tipos mínimos de SpeechRecognition — todavía no está en lib.dom.d.ts
// para todos los navegadores objetivo (sigue con prefijo en algunos).
interface SpeechRecognitionResultLike {
  0: { transcript: string }
}
interface SpeechRecognitionEventLike extends Event {
  results: { 0: SpeechRecognitionResultLike }
}
interface SpeechRecognitionLike extends EventTarget {
  lang: string
  interimResults: boolean
  maxAlternatives: number
  start(): void
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onerror: (() => void) | null
  onend: (() => void) | null
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike

function getSpeechRecognitionCtor(): SpeechRecognitionCtor | null {
  if (typeof window === 'undefined') return null
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor
    webkitSpeechRecognition?: SpeechRecognitionCtor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

export function isVoiceInputSupported(): boolean {
  return getSpeechRecognitionCtor() !== null
}

export function isVoiceOutputSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

/** Escucha un solo enunciado y resuelve con el texto transcrito. Rechaza
 * si el navegador no soporta reconocimiento de voz, o si termina sin
 * detectar nada (silencio, error de micrófono, permiso denegado). */
export function listenOnce(): Promise<string> {
  return new Promise((resolve, reject) => {
    const Ctor = getSpeechRecognitionCtor()
    if (!Ctor) {
      reject(new Error('Este navegador no soporta reconocimiento de voz.'))
      return
    }
    const recognition = new Ctor()
    recognition.lang = SPEECH_LANG
    recognition.interimResults = false
    recognition.maxAlternatives = 1
    let settled = false

    recognition.onresult = (event) => {
      settled = true
      resolve(event.results[0][0].transcript)
    }
    recognition.onerror = () => {
      if (settled) return
      settled = true
      reject(new Error('No se pudo reconocer el audio.'))
    }
    recognition.onend = () => {
      if (settled) return
      settled = true
      reject(new Error('No se detectó ningún audio.'))
    }
    recognition.start()
  })
}

/** Lee un texto en voz alta. No hace nada (resuelve de inmediato) si el
 * navegador no soporta síntesis de voz — nunca bloquea el flujo normal
 * de texto. */
export function speak(text: string): Promise<void> {
  return new Promise((resolve) => {
    if (!isVoiceOutputSupported() || !text) {
      resolve()
      return
    }
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = SPEECH_LANG
    utterance.onend = () => resolve()
    utterance.onerror = () => resolve()
    window.speechSynthesis.speak(utterance)
  })
}

const YES_WORDS = ['si', 'confirmo', 'confirma', 'confirmar', 'dale', 'ya', 'correcto', 'afirmativo']
const NO_WORDS = ['no', 'cancela', 'cancelar', 'cancelo', 'negativo']

function normalizeWord(text: string): string {
  return text
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z]/g, '')
}

/** Interpreta localmente (sin pasar por el LLM) si una respuesta hablada
 * es un sí o un no — la confirmación de una mutación nunca depende del
 * juicio del modelo, ver docs/SECURITY.md #5/#8 y ADR-016. */
export function matchYesNo(text: string): 'yes' | 'no' | null {
  const words = text.split(/\s+/).map(normalizeWord)
  if (words.some((w) => YES_WORDS.includes(w))) return 'yes'
  if (words.some((w) => NO_WORDS.includes(w))) return 'no'
  return null
}

const MAX_ITEMS_SPOKEN = 5

function joinWithRemainder(names: string[], total: number): string {
  const shown = names.slice(0, MAX_ITEMS_SPOKEN).join(', ')
  const remainder = total - Math.min(names.length, MAX_ITEMS_SPOKEN)
  return remainder > 0 ? `${shown} y ${remainder} más` : shown
}

/** Resumen hablado del resultado de un intent — mismas formas que
 * ResultView, para que lo que se lee en voz alta diga lo mismo que lo
 * que se ve en pantalla. Vacío ("") si no se reconoce la forma; el
 * llamador debe tener un texto genérico de respaldo. */
export function describeResultForSpeech(result: unknown): string {
  if (isReceipt(result)) {
    const isSale = 'sold_at' in result
    return `${isSale ? 'Venta' : 'Compra'} registrada por ${formatCLPSpoken(result.total)}.`
  }

  if (isMovement(result)) {
    return `Movimiento registrado. Nuevo stock: ${formatQuantity(result.balance_after)}.`
  }

  if (isProductSalesSummary(result)) {
    // Antes que isPeriodSummary: ver resultShapes.ts.
    return (
      `Hoy vendiste ${formatQuantity(result.today.quantity)} de ${result.product_name}, ` +
      `por ${formatCLPSpoken(result.today.total)}.`
    )
  }

  if (isPeriodSummary(result)) {
    return `Hoy vendiste ${formatCLPSpoken(result.today.total)} en ${result.today.count} ventas.`
  }

  if (isProduct(result)) {
    // Misma forma para crear_producto y actualizar_producto (ver
    // ResultView) — frase neutra, no dice "creado" ni "actualizado".
    return (
      `${result.name}: precio ${formatCLPSpoken(result.default_price)}, ` +
      `stock ${formatQuantity(result.current_stock)}.`
    )
  }

  if (isProductList(result)) {
    if (result.length === 0) return 'No hay productos en el catálogo.'
    const nombres = result.map((p) => p.name)
    return `Tienes ${result.length} productos: ${joinWithRemainder(nombres, result.length)}.`
  }

  if (isLowStockList(result)) {
    // Esta forma ahora solo la genera consultar_stock_bajo (alerta real
    // de stock bajo) — la consulta de UN producto puntual usa isProduct
    // (ver consultar_producto), así que aquí no hace falta un caso
    // especial "neutro" para un solo elemento.
    if (result.length === 0) return 'No hay productos con stock bajo.'
    if (result.length === 1) {
      const [product] = result
      return `1 producto con stock bajo: ${product.name}.`
    }
    const nombres = result.map((p) => p.name)
    return `${result.length} productos con stock bajo: ${joinWithRemainder(nombres, result.length)}.`
  }

  if (isTopSellingList(result)) {
    if (result.length === 0) return 'Todavía no hay ventas registradas.'
    const [primero] = result
    return (
      `El producto que más se ha vendido es ${primero.product_name}, ` +
      `con ${formatQuantity(primero.quantity)} unidades.`
    )
  }

  return ''
}
