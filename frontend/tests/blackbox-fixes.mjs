import assert from 'node:assert/strict'
import { chromium } from 'playwright'

const baseURL = process.env.SENTINEL_TEST_URL || 'http://127.0.0.1:15175'
const browser = await chromium.launch({ headless: true })
const errors = []
const csv = 'supplier,region,on_time_rate,defect_rate,lead_time_days,monthly_spend_usd\nUI New Supplier,Europe,96,1,12,12345\n'

try {
  for (const width of [1440, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 950 } })
    page.on('pageerror', error => errors.push(error.message))
    await page.route('https://api.deepseek.com/**', () => { throw new Error('Unexpected real model request') })
    await page.goto(baseURL, { waitUntil: 'networkidle' })
    const navigate = async label => {
      if (width === 390) await page.getByRole('button', { name: '打开导航' }).click()
      await page.locator('.primary-nav button').filter({ hasText: label }).click()
      if (width === 390) {
        await page.waitForFunction(() => !document.querySelector('.sidebar').classList.contains('sidebar-open'))
        await page.waitForTimeout(250)
      }
    }
    await page.locator('input[type="file"]').setInputFiles({ name: `ui-new-${width}.csv`, mimeType: 'text/csv', buffer: Buffer.from(csv) })
    await page.locator('.files-list .file-row').filter({ hasText: `ui-new-${width}.csv` }).waitFor()
    await page.getByText('已选资料待分析 · 尚无当前指标', { exact: true }).waitFor()
    assert.equal(await page.locator('.supplier-row').count(), 0, 'Old Demo metrics must disappear before new analysis')
    for (const file of ['suppliers.csv', 'brief.txt']) {
      const row = page.locator('.file-row').filter({ hasText: file })
      if ((await row.getAttribute('class')).includes('file-selected')) await row.click()
    }
    await page.locator('#decision-question').fill('离线 UI 测试：请分析新供应商资料并保留风险审查。')
    await page.getByRole('button', { name: 'Live', exact: true }).click()
    await page.getByRole('button', { name: /启动多 Agent 分析/ }).click()
    await page.locator('.pipeline-node').filter({ hasText: 'Research Agent' }).getByText('失败', { exact: true }).waitFor({ timeout: 10000 })
    for (const name of ['Analyst Agent', 'Risk Reviewer Agent', 'Action Agent']) {
      const node = page.locator('.pipeline-node').filter({ hasText: name })
      await node.getByText('已阻断', { exact: true }).waitFor()
      assert.match(await node.innerText(), /等待 Research Agent 完成/)
      assert.doesNotMatch(await node.innerText(), /排队中/)
    }
    await page.locator('.pipeline-node').filter({ hasText: 'Analyst Agent' }).click()
    await page.getByText('当前阶段未执行', { exact: true }).waitFor()
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: `/tmp/sentinelai-fix-workflow-${width}.png`, fullPage: true })
    await navigate('决策报告')
    await page.getByRole('heading', { name: '分析未完成，报告未生成' }).waitFor()
    const failure = await page.locator('.failure-report').innerText()
    assert.match(failure, /失败阶段\s+Research Agent/)
    assert.match(failure, /MODEL_TIMEOUT/)
    assert.match(failure, /已完成阶段\s+Planner Agent/)
    assert.match(failure, /未执行阶段\s+Analyst Agent、Risk Reviewer Agent、Action Agent/)
    assert.match(failure, /90 秒/)
    assert.doesNotMatch(failure, /先运行一次决策分析/)
    assert.equal(await page.getByRole('link', { name: /下载 Markdown/ }).count(), 0)
    await page.screenshot({ path: `/tmp/sentinelai-fix-report-${width}.png`, fullPage: true })
    await page.getByRole('button', { name: '查看失败工作流' }).click()
    await page.locator('.agent-detail h2').filter({ hasText: 'Research Agent' }).waitFor()
    await navigate('总览')
    await page.getByText('UI New Supplier', { exact: true }).waitFor()
    assert.match(await page.locator('.metric-source-state').innerText(), /当前任务.*failed/)
    assert.match(await page.locator('.section-caption').first().innerText(), new RegExp(`ui-new-${width}.csv`))
    await page.locator('input[type="file"]').setInputFiles({ name: `changed-${width}.txt`, mimeType: 'text/plain', buffer: Buffer.from('New evidence, not yet analyzed.') })
    await page.locator('.file-row').filter({ hasText: `changed-${width}.txt` }).waitFor()
    await page.getByText('已选资料待分析 · 尚无当前指标', { exact: true }).waitFor()
    assert.equal(await page.locator('.supplier-row').count(), 0)
    await navigate('运行历史')
    await page.locator('.recent-run-row').first().click()
    await navigate('总览')
    await page.getByText('UI New Supplier', { exact: true }).waitFor()
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), 'No page overflow')
    console.log(`${width}px: new-source reset, current task data, failed/blocked workflow, failed-report navigation passed (offline simulated Live)`)
    await page.close()
  }
  assert.deepEqual(errors, [])
} finally {
  await browser.close()
}
