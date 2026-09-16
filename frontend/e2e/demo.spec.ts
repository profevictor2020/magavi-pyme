import { expect, test, type Page } from '@playwright/test'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const FACTURA_FIXTURE = path.join(__dirname, 'fixtures', 'factura-compra.png')

function uniqueSuffix(): string {
  return `${Date.now()}${Math.floor(Math.random() * 1000)}`
}

async function registerAndCreateCompany(
  page: Page,
  options: { firstName: string; email: string; password: string; companyName: string; rut: string },
) {
  await page.goto('/register')
  await page.fill('#firstName', options.firstName)
  await page.fill('#email', options.email)
  await page.fill('#password', options.password)
  await page.click('button[type=submit]')
  await page.waitForURL('**/companies')

  await page.fill('#companyName', options.companyName)
  await page.fill('#companyRut', options.rut)
  await page.click('form button[type=submit]')
  await page.waitForURL('/')
}

async function createProduct(
  page: Page,
  options: { name: string; price: string; cost: string; initialStock: string },
) {
  await page.click('text=Productos')
  await page.waitForURL('**/products')
  await page.click('text=+ Nuevo')
  await page.locator('form.card .field:has-text("Nombre") input').fill(options.name)
  await page.locator('form.card .field:has-text("Unidad") input').fill('unidad')
  await page.locator('form.card .field:has-text("Precio de venta") input').fill(options.price)
  await page.locator('form.card .field:has-text("Costo") input').fill(options.cost)
  await page.locator('form.card .field:has-text("Stock inicial") input').fill(options.initialStock)
  await page.click('form.card button[type=submit]')
  await expect(page.getByText(options.name).first()).toBeVisible()
}

async function sendChatMessage(page: Page, message: string) {
  await page.click('text=Chat')
  await page.waitForURL('/')
  await page.fill('input[placeholder="Escribe un mensaje…"]', message)
  await page.click('text=Enviar')
}

test.describe('Guion de demo del MVP (docs/ROADMAP.md Fase 12)', () => {
  test('vender por chat, confirmar, ver caja e inventario, y confirmar una compra por foto', async ({
    page,
  }) => {
    const suffix = uniqueSuffix()

    // 1) Abrir MAGAVI desde un celular (viewport móvil, ver playwright.config.ts)
    //    e iniciar sesión (registro + primera empresa).
    await registerAndCreateCompany(page, {
      firstName: 'Marcela',
      email: `marcela.${suffix}@almacen.cl`,
      password: 'ClaveSegura123!',
      companyName: `Almacén Marcela ${suffix}`,
      // Los primeros dígitos de Date.now() casi no cambian entre corridas
      // separadas por minutos — se usan los últimos (más volátiles) para
      // que el RUT no choque con el de una corrida anterior.
      rut: `76${suffix.slice(-6)}-9`,
    })

    await createProduct(page, {
      name: 'Cafe',
      price: '2500',
      cost: '1500',
      initialStock: '50',
    })

    // 2) Preguntar "¿cuánto vendí hoy?" — todavía no hay ventas.
    await sendChatMessage(page, '¿Cuánto vendí hoy?')
    await expect(page.getByText(/Hoy: \$0/)).toBeVisible()

    // 3) Registrar "Vendí 3 cafés a $2.500" → confirmar → se registra.
    await sendChatMessage(page, 'Vendí 3 cafés a 2500')
    await page.waitForSelector('text=Confirmar')
    await page.click('text=Confirmar')
    await expect(page.getByText('✅ Confirmado')).toBeVisible()
    await expect(page.getByText(/Venta #\d+ — \$7\.500/)).toBeVisible()

    // 4) Inventario/caja reflejan el cambio.
    await page.click('text=Caja')
    await page.waitForURL('**/cashbox')
    await expect(page.getByText(/Ingresos: \$7\.500/).first()).toBeVisible()

    await page.click('text=Productos')
    await page.waitForURL('**/products')
    await expect(page.getByText(/Stock: 47\.000/)).toBeVisible()

    // 5) Volver a preguntar "¿cuánto vendí hoy?" → refleja la nueva venta.
    await sendChatMessage(page, '¿Cuánto vendí hoy?')
    await expect(page.getByText(/Hoy: \$7\.500 \(1 ventas\)/)).toBeVisible()

    // 6) Fotografiar un documento de compra → revisar → confirmar.
    await page.click('text=Docs')
    await page.waitForURL('**/documents')
    await page.setInputFiles('input[type=file]', FACTURA_FIXTURE)
    await page.waitForURL('**/documents/*')
    await page.waitForSelector('text=Revisa y confirma', { timeout: 20_000 })

    // El LLM de prueba ya debería haber resuelto "Cafe" contra el
    // catálogo, pero el paso de "revisar" existe justamente para que el
    // usuario pueda corregirlo — se elige explícitamente en vez de
    // asumir que quedó bien pre-cargado.
    const productSelect = page.locator('form.card .field:has-text("Producto") select').first()
    await productSelect.selectOption({ label: 'Cafe' })
    await page.click('form.card button:has-text("Confirmar y registrar")')
    await expect(page.getByText('✅ Confirmado')).toBeVisible()
    await expect(page.getByText(/Compra #\d+/)).toBeVisible()

    // 7) Inventario/movimientos reflejan el cambio (47 + 10 comprados = 57).
    await page.click('text=Productos')
    await page.waitForURL('**/products')
    await expect(page.getByText(/Stock: 57\.000/)).toBeVisible()
  })

  test('los datos de una empresa nunca aparecen en otra (aislamiento, punto 8 del guion)', async ({
    page,
  }) => {
    const suffix = uniqueSuffix()

    // Empresa B, completamente nueva: si algo de la empresa A del test
    // anterior (u otra corrida) se filtrara, aparecería acá.
    await registerAndCreateCompany(page, {
      firstName: 'Pedro',
      email: `pedro.${suffix}@ferreteria.cl`,
      password: 'ClaveSegura123!',
      companyName: `Ferretería Pedro ${suffix}`,
      rut: `77${suffix.slice(-6)}-3`,
    })

    await page.click('text=Productos')
    await page.waitForURL('**/products')
    await expect(page.getByText('No hay productos todavía.')).toBeVisible()

    await page.click('text=Ventas')
    await page.waitForURL('**/sales')
    await expect(page.getByText('No hay ventas registradas todavía.')).toBeVisible()

    await page.click('text=Docs')
    await page.waitForURL('**/documents')
    await expect(page.getByText('No hay documentos subidos todavía.')).toBeVisible()

    await page.click('text=Caja')
    await page.waitForURL('**/cashbox')
    await expect(page.getByText('Ingresos: $0').first()).toBeVisible()

    await sendChatMessage(page, '¿Cuánto vendí hoy?')
    await expect(page.getByText(/Hoy: \$0 \(0 ventas\)/)).toBeVisible()
  })
})
