import { describe, expect, it } from 'vitest'
import { formatCLPSpoken } from './format'
import { describeResultForSpeech, matchYesNo } from './speech'

describe('matchYesNo', () => {
  it('reconoce afirmaciones con distintas palabras y mayúsculas/acentos', () => {
    expect(matchYesNo('sí')).toBe('yes')
    expect(matchYesNo('Confirmo')).toBe('yes')
    expect(matchYesNo('dale')).toBe('yes')
    expect(matchYesNo('ya po')).toBe('yes')
  })

  it('reconoce negaciones', () => {
    expect(matchYesNo('no')).toBe('no')
    expect(matchYesNo('cancela eso')).toBe('no')
  })

  it('devuelve null cuando no hay una palabra clara de sí/no', () => {
    expect(matchYesNo('qué dijiste')).toBeNull()
    expect(matchYesNo('')).toBeNull()
  })
})

describe('formatCLPSpoken', () => {
  it('dice "pesos" en vez de depender del símbolo "$" (que un sintetizador \
puede leer como dólares)', () => {
    expect(formatCLPSpoken('890')).toBe('890 pesos')
  })

  it('no usa separador de miles: un sintetizador de voz lee el "." de \
formatCLP como punto decimal, no como separador ("7.000" se escucha \
como "7", no "siete mil")', () => {
    expect(formatCLPSpoken(7000)).toBe('7000 pesos')
    expect(formatCLPSpoken('10000')).toBe('10000 pesos')
  })
})

describe('describeResultForSpeech', () => {
  it('describe una venta registrada', () => {
    const text = describeResultForSpeech({
      id: 1,
      total: '7500.00',
      status: 'confirmed',
      sold_at: '2026-09-16T12:00:00Z',
      items: [],
    })
    expect(text).toContain('Venta registrada')
    expect(text).toContain('pesos')
  })

  it('describe una compra registrada', () => {
    const text = describeResultForSpeech({
      id: 1,
      total: '7500.00',
      status: 'confirmed',
      purchased_at: '2026-09-16T12:00:00Z',
      items: [],
    })
    expect(text).toContain('Compra registrada')
  })

  it('describe un movimiento de inventario con el nuevo stock', () => {
    const text = describeResultForSpeech({
      id: 1,
      product: 5,
      type: 'in',
      quantity: '20',
      balance_after: '80',
      reason: 'Reposición',
    })
    expect(text).toBe('Movimiento registrado. Nuevo stock: 80.')
  })

  it('describe un resumen de periodo', () => {
    const text = describeResultForSpeech({
      today: { total: '10000', count: 3 },
      week: { total: '50000', count: 12 },
    })
    expect(text).toContain('3 ventas')
    expect(text).toContain('pesos')
  })

  it('describe cuánto se vendió de UN producto puntual (no el total general)', () => {
    // Distinta forma del resumen de periodo (tiene product_id) — debe
    // hablar de unidades vendidas de ESE producto, no de "N ventas" en
    // general (ver isProductSalesSummary en resultShapes.ts).
    const text = describeResultForSpeech({
      product_id: 1,
      product_name: 'Goma',
      today: { quantity: '5.000', total: '4450.00' },
      week: { quantity: '5.000', total: '4450.00' },
    })
    expect(text).toContain('Goma')
    expect(text).toContain('5')
    expect(text).toContain('pesos')
  })

  it('describe un producto recién creado', () => {
    const text = describeResultForSpeech({
      id: 1,
      name: 'Lápices de colores',
      unit: 'unidad',
      default_price: '1000',
      current_stock: '60',
    })
    expect(text).toContain('Lápices de colores')
    expect(text).toContain('60')
    expect(text).toContain('pesos')
  })

  it('describe una lista de productos del catálogo', () => {
    const text = describeResultForSpeech([
      { id: 1, name: 'Café', unit: 'unidad', default_price: '2500', current_stock: '10' },
      { id: 2, name: 'Té', unit: 'unidad', default_price: '2000', current_stock: '5' },
    ])
    expect(text).toContain('2 productos')
    expect(text).toContain('Café')
    expect(text).toContain('Té')
  })

  it('describe el catálogo vacío', () => {
    expect(describeResultForSpeech([])).toBe('No hay productos en el catálogo.')
  })

  it('describe la consulta de UN producto puntual con precio y stock', () => {
    // consultar_producto devuelve un objeto (forma isProduct), no una
    // lista — sirve tanto para "¿cuánto stock tengo de X?" como para
    // "¿cuál es el precio de X?", ambas preguntas dan la misma respuesta.
    const text = describeResultForSpeech({
      id: 1,
      name: 'Goma',
      unit: 'unidad',
      current_stock: '30',
      low_stock_threshold: '0',
      default_price: '890',
    })
    expect(text).toContain('Goma')
    expect(text).toContain('890')
    expect(text).toContain('30')
    expect(text).toContain('pesos')
  })

  it('describe una alerta de stock bajo de un solo producto', () => {
    const text = describeResultForSpeech([
      { id: 1, name: 'Lápices de colores', current_stock: '2', low_stock_threshold: '10' },
    ])
    expect(text).toBe('1 producto con stock bajo: Lápices de colores.')
  })

  it('describe una alerta de stock bajo con varios productos', () => {
    const text = describeResultForSpeech([
      { id: 1, name: 'Café', current_stock: '2', low_stock_threshold: '10' },
      { id: 2, name: 'Té', current_stock: '1', low_stock_threshold: '5' },
    ])
    expect(text).toContain('2 productos con stock bajo')
  })

  it('describe el producto más vendido (solo el primero del ranking)', () => {
    const text = describeResultForSpeech([
      { product_id: 1, product_name: 'Goma', quantity: '10.000', total: '5000.00' },
      { product_id: 2, product_name: 'Lápiz', quantity: '3.000', total: '3000.00' },
    ])
    expect(text).toContain('Goma')
    expect(text).toContain('10')
    expect(text).not.toContain('Lápiz')
  })

  it('describe cuando todavía no hay ventas para el ranking', () => {
    // Mismo array vacío que consultar_catalogo — ver el comentario en
    // isTopSellingList sobre esta ambigüedad ya existente en el proyecto.
    expect(describeResultForSpeech([])).toBe('No hay productos en el catálogo.')
  })

  it('describe un gasto registrado con su categoría', () => {
    const text = describeResultForSpeech({
      id: 1,
      type: 'expense',
      amount: '150000.00',
      reference_type: 'manual',
      category: 'arriendo',
      description: '',
    })
    expect(text).toBe('Gasto registrado: arriendo, 150000 pesos.')
  })

  it('devuelve cadena vacía para formas desconocidas', () => {
    expect(describeResultForSpeech({ foo: 'bar' })).toBe('')
  })
})
