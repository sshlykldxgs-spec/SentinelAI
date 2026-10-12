import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const baseURL = process.env.SENTINEL_TEST_URL || 'http://127.0.0.1:15177'
const browser = await chromium.launch({ headless: true })
const names = ['Planner Agent', 'Research Agent', 'Analyst Agent', 'Risk Reviewer Agent', 'Action Agent']
const firstFailure = { code: 'MODEL_TIMEOUT', message: '离线模拟首次请求超时。', retryable: true }
const errors = []

function fixture(state) {
  const agent = { id: 'action', name: names[4], role: '行动建议与人工审批', status: state,
    attempts: 2, retry_attempt: 1, max_retries: 1, first_failure: firstFailure, model: 'offline-ui-fixture',
    output: state === 'completed' ? '离线模拟建议，未执行外部操作。' : '',
    attempt_history: [{ attempt: 1, status: 'failed', elapsed_seconds: 1, error: firstFailure },
      { attempt: 2, status: state === 'retrying' ? 'running' : state, elapsed_seconds: state === 'retrying' ? null : 1,
        error: state === 'failed' ? firstFailure : null }], tools: [] }
  return { id: 'ui-recovery', mode: 'live', model: 'offline-ui-fixture', question: '离线模拟恢复状态', document_ids: ['d1'],
    created_at: '2026-10-12T00:00:00Z', status: state === 'retrying' ? 'running' : state === 'failed' ? 'failed' : 'completed',
    report: null, error_details: state === 'failed' ? firstFailure : null,
    agents: names.map((name, index) => index === 4 ? agent : { id: ['planner', 'research', 'analyst', 'risk'][index], name,
      role: '离线状态测试', status: 'completed', output: 'Offline fixture', tools: [] }),
    events: [{ event_id: 1, type: 'agent.retrying', stage: 'action', timestamp: '2026-10-12T00:00:01Z', payload: { retry_attempt: 1 } }],
    budget: { reserved_tokens: 0, observed_tokens: null, limit: null } }
}

try {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 950 } })
    page.on('pageerror', error => errors.push(error.message))
    let state = 'retrying'
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname
      const run = fixture(state)
      if (path.endsWith('/events')) {
        await route.fulfill({ contentType: 'text/event-stream', body: `id: 1\ndata: ${JSON.stringify({ event: run.events[0], run })}\n\n` })
      } else if (path === '/api/bootstrap') {
        await route.fulfill({ json: { documents: [{ id: 'd1', name: 'offline.txt', type: 'txt', size: 20 }], runs: [run],
          demo_document_ids: ['d1'], default_question: run.question, approvals: [], metrics: null, live_available: false, model_config: {} } })
      } else if (path === '/api/health') {
        await route.fulfill({ json: { status: 'ok' } })
      } else {
        throw new Error(`Unexpected API request in offline UI test: ${path}`)
      }
    })
    const openAction = async () => {
      if (width === 390) await page.getByRole('button', { name: '打开导航' }).click()
      await page.locator('.primary-nav button').filter({ hasText: 'Agent 工作流' }).click()
      if (width === 390) await page.waitForTimeout(250)
      await page.locator('.pipeline-node').filter({ hasText: 'Action Agent' }).click()
    }
    await page.goto(baseURL, { waitUntil: 'networkidle' })
    await openAction()
    await page.locator('.agent-detail').getByText('恢复重试 (1/1)', { exact: true }).waitFor()
    assert.match(await page.locator('.recovery-history').innerText(), /首次失败.*MODEL_TIMEOUT/s)
    await page.screenshot({ path: `/tmp/sentinelai-stability-retrying-${width}.png`, fullPage: true })
    for (state of ['completed', 'failed']) {
      await page.reload({ waitUntil: 'networkidle' })
      await openAction()
      await page.locator('.agent-detail .status-pill').filter({ hasText: state === 'completed' ? '已完成' : '失败' }).waitFor()
      assert.match(await page.locator('.recovery-history').innerText(), /首次失败.*MODEL_TIMEOUT/s)
      assert.match(await page.locator('.recovery-history').innerText(), /恢复请求：1 \/ 1/)
    }
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
    console.log(`${width}px: retrying (1/1), terminal completed/failed and first-failure history passed; all API responses mocked`)
    await page.close()
  }
  assert.deepEqual(errors, [])
} finally {
  await browser.close()
}
