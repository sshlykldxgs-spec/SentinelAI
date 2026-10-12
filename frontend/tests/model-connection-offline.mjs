import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const baseURL = process.env.SENTINEL_TEST_URL || 'http://127.0.0.1:5173'
const browser = await chromium.launch({ headless: true })
const secret = 'offline-connection-canary'

try {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } })
    const errors = []
    let testCalls = 0
    let saved = false
    page.on('pageerror', error => errors.push(error.name))
    await page.route('**/api/**', async route => {
      const { pathname } = new URL(route.request().url())
      let body
      if (pathname === '/api/bootstrap') {
        body = { documents: [], runs: [], demo_document_ids: [], default_question: '', metrics: null,
          live_available: saved, approvals: [], model_config: {
            configured: saved, base_url: saved ? 'https://mock.invalid/v1' : '',
            model: saved ? 'offline-model' : '', max_output_tokens: null,
            configuration_source: saved ? 'process_memory' : 'environment',
          } }
      } else if (pathname === '/api/health' || pathname === '/api/session') {
        body = { status: 'ok' }
      } else if (pathname === '/api/model/config' && route.request().method() === 'POST') {
        const payload = route.request().postDataJSON()
        assert.equal(payload.api_key, saved ? '' : secret)
        saved = true
        body = { saved: true, storage: 'process_memory' }
      } else if (pathname === '/api/model/test') {
        testCalls += 1
        body = testCalls === 1
          ? { ok: true, model: 'offline-model', elapsed_seconds: 0.731, message: '模型连接成功。',
              response_summary: '收到非空文本响应并正常结束；五阶段结构化工作流需另行验收。' }
          : { ok: false, model: 'offline-model', elapsed_seconds: 0.182,
              error: { code: 'UNEXPECTED_RESPONSE', message: '接口未返回正常结束的非空文本响应；请核对模型或接口兼容性。' } }
      } else {
        throw new Error(`Unexpected API request: ${pathname}`)
      }
      await route.fulfill({ json: body })
    })
    try {
      await page.goto(baseURL, { waitUntil: 'networkidle' })
      await page.getByRole('button', { name: '模型配置', exact: true }).first().click()
      await page.getByRole('heading', { name: '模型配置', exact: true }).waitFor()
      await page.getByRole('textbox', { name: 'API Base URL', exact: true }).fill('https://mock.invalid/v1')
      await page.getByRole('textbox', { name: 'Model Name', exact: true }).fill('offline-model')
      const key = page.getByRole('textbox', { name: 'API Key', exact: true })
      await key.fill(secret)
      await page.getByRole('button', { name: '测试连接', exact: true }).click()
      await page.getByText('模型连接成功。', { exact: true }).waitFor()
      await page.getByText('收到非空文本响应并正常结束；五阶段结构化工作流需另行验收。').waitFor()
      await page.getByText('模型：offline-model · 0.731s').waitFor()
      assert.equal(await key.inputValue(), '')
      assert.ok(!(await page.locator('body').innerText()).includes(secret))
      await page.getByRole('button', { name: '测试连接', exact: true }).click()
      await page.getByText('接口未返回正常结束的非空文本响应；请核对模型或接口兼容性。').waitFor()
      assert.equal(testCalls, 2)
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
      assert.deepEqual(errors, [])
      console.log(`${width}px: connection status, model, elapsed time, safe summary and error feedback passed (offline API only)`)
    } finally {
      await page.close()
    }
  }
} finally {
  await browser.close()
}
