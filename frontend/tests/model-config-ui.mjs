import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const baseURL = process.env.SENTINEL_TEST_URL || 'http://127.0.0.1:15178'
const browser = await chromium.launch({ headless: true })
const canary = 'offline-browser-canary'
const errors = []

try {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 950 } })
    page.on('pageerror', error => errors.push(error.name))
    let postedRuns = 0
    page.on('request', request => {
      if (new URL(request.url()).pathname === '/api/runs' && request.method() === 'POST') postedRuns += 1
    })
    await page.goto(baseURL, { waitUntil: 'networkidle' })
    const navigate = async label => {
      if (width === 390) await page.getByRole('button', { name: '打开导航' }).click()
      await page.locator('.primary-nav button').filter({ hasText: label }).click()
      if (width === 390) await page.waitForTimeout(250)
    }
    if (width === 1440) {
      await page.getByText('Live 模式需要配置您自己的模型 API。Demo 模式无需配置。', { exact: true }).waitFor()
      await page.getByRole('button', { name: /启动多 Agent 分析/ }).click()
      await page.getByText('5 / 5').waitFor({ timeout: 10000 })
      await navigate('总览')
      const before = postedRuns
      await page.getByRole('button', { name: 'Live', exact: true }).click()
      await page.getByRole('button', { name: /启动多 Agent 分析/ }).click()
      await page.getByRole('heading', { name: '模型配置', exact: true }).waitFor()
      await page.getByText('请先完成模型配置', { exact: true }).waitFor()
      assert.equal(postedRuns, before, 'Unconfigured Live must not submit a task')
    } else {
      await page.getByRole('button', { name: '模型配置', exact: true }).first().click()
      await page.getByRole('heading', { name: '模型配置', exact: true }).waitFor()
    }
    const key = page.getByRole('textbox', { name: 'API Key', exact: true })
    assert.equal(await key.getAttribute('type'), 'password')
    await page.getByRole('textbox', { name: 'API Base URL', exact: true }).fill('https://mock.invalid/v1')
    await page.getByRole('textbox', { name: 'Model Name', exact: true }).fill('offline-ui-model')
    await key.fill(canary)
    await page.getByRole('button', { name: '测试连接', exact: true }).click()
    await page.getByText('模型连接成功。', { exact: true }).waitFor()
    assert.equal(await key.inputValue(), '')
    assert.ok(!(await page.locator('body').innerText()).includes(canary))
    const storage = await page.evaluate(() => ({ local: JSON.stringify(localStorage), session: JSON.stringify(sessionStorage) }))
    assert.ok(!JSON.stringify(storage).includes(canary))
    await page.screenshot({ path: `/tmp/sentinelai-model-config-${width}.png`, fullPage: true })
    await page.reload({ waitUntil: 'networkidle' })
    await navigate('配置')
    assert.equal(await page.getByRole('textbox', { name: 'API Key', exact: true }).inputValue(), '')
    await page.getByRole('textbox', { name: 'Model Name', exact: true }).fill('offline-auth-error')
    await page.getByRole('button', { name: '测试连接', exact: true }).click()
    await page.getByText('API Key错误或无权访问该模型，请检查自己的凭据。', { exact: true }).waitFor()
    await page.getByRole('textbox', { name: 'Model Name', exact: true }).fill('offline-missing-model')
    await page.getByRole('button', { name: '测试连接', exact: true }).click()
    await page.getByText('模型不存在或Base URL路径错误，请核对服务文档。', { exact: true }).waitFor()
    await page.getByRole('textbox', { name: 'Model Name', exact: true }).fill('offline-ui-model')
    await page.getByRole('button', { name: '测试连接', exact: true }).click()
    await page.getByText('模型连接成功。', { exact: true }).waitFor()
    await navigate('总览')
    await page.getByRole('button', { name: 'Live', exact: true }).click()
    await page.getByRole('button', { name: /启动多 Agent 分析/ }).click()
    await page.getByText('5 / 5').waitFor({ timeout: 10000 })
    await page.getByRole('button', { name: /查看完整报告/ }).click()
    await page.getByRole('heading', { name: 'SentinelAI 决策情报报告' }).waitFor()
    assert.match(await page.locator('.report-paper').innerText(), /Live \/ 在线模型分析/)
    assert.ok(!(await page.locator('.report-paper').innerText()).includes(canary))
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    console.log(`${width}px: model configuration, masked/cleared key, success/auth/model-error feedback and five-stage executor regression passed; all models offline fixtures`)
    await page.close()
  }
  assert.deepEqual(errors, [])
} finally {
  await browser.close()
}
