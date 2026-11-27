import { chromium } from 'playwright'

const frontendUrl = process.env.FRONTEND_URL ?? 'http://127.0.0.1:5173'

async function loginPatient(page, mobile, name) {
  await page.getByRole('tab', { name: 'Patient' }).click()
  await page.getByPlaceholder('9000000001').fill(mobile)
  await page.getByPlaceholder('Asha Verma').fill(name)
  await page.getByRole('button', { name: 'Sign in as Patient' }).click()
  await page.getByRole('heading', { name: 'Your appointments' }).waitFor()
}

async function loginStaff(page, contextPage = page) {
  await contextPage.getByRole('tab', { name: 'Staff' }).click()
  await contextPage.getByPlaceholder('Front Desk').fill('Front Desk')
  await contextPage.getByRole('button', { name: 'Sign in as Staff' }).click()
  await contextPage.getByRole('heading', { name: 'Clinic appointments' }).waitFor()
}

async function logout(page) {
  await page.getByRole('button', { name: 'Log out' }).click()
  await page.getByRole('heading', { name: 'NetraCare' }).waitFor({ timeout: 15000 })
  await page.getByRole('tab', { name: 'Patient' }).waitFor({ timeout: 15000 })
}

async function sendChat(page, text) {
  await page.getByLabel('Chat message').fill(text)
  await page.getByRole('button', { name: 'Send' }).click()
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const pageErrors = []

try {
  const page = await browser.newPage()
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await page.goto(frontendUrl)
  await page.getByRole('heading', { name: 'NetraCare' }).waitFor()

  // Patient chat: sourced answer + follow-up
  await loginPatient(page, '9000000001', 'Asha Verma')
  await page.getByLabel('Patient chat', { exact: false }).waitFor({ timeout: 10000 }).catch(() => {})
  const chatPanel = page.locator('.chat-card')
  await chatPanel.waitFor()

  await sendChat(page, 'How much does cataract surgery cost, and do I have to stay overnight?')
  await page.getByText('procedures.md', { exact: false }).first().waitFor({ timeout: 60000 })

  await sendChat(page, 'What should I avoid after it?')
  await page.getByText(/rubbing|swim/i).first().waitFor({ timeout: 60000 })

  // Booking via agent shows a confirmation card; declining changes nothing
  const beforeCount = await page.locator('tr[data-appointment-id]').count()
  await sendChat(page, 'Book a retina follow-up with Dr. Shah on Monday morning, the earliest time. Reason: routine eye test')
  await page.getByRole('button', { name: 'Confirm' }).first().waitFor({ timeout: 120000 })
  await page.getByRole('button', { name: 'No' }).first().click()
  await page.getByText(/what would you like|nothing changed|anything else/i).first().waitFor({ timeout: 60000 }).catch(() => {})
  const afterCount = await page.locator('tr[data-appointment-id]').count()
  if (afterCount !== beforeCount) throw new Error('Chat booking request changed appointments')

  // New chat clears
  await page.getByRole('button', { name: 'New chat' }).click()
  if (await chatPanel.getByText('procedures.md', { exact: false }).count() !== 0) {
    throw new Error('New chat did not clear the conversation')
  }

  // Red-flag emergency in chat
  await sendChat(page, 'A curtain came down over my left eye an hour ago')
  await page.locator('.chat-emergency').filter({ hasText: /urgent attention/i }).waitFor({ timeout: 60000 })

  // Logout/login shows empty chat
  await logout(page)
  await loginPatient(page, '9000000001', 'Asha Verma')
  await page.locator('.chat-card').waitFor()
  if (await page.locator('.chat-emergency').count() !== 0) {
    throw new Error('Chat persisted across logout')
  }
  await logout(page)

  // Staff sees chat-origin urgent case and search debug
  await loginStaff(page)
  await page.getByText('Urgent cases', { exact: false }).waitFor()
  await page.getByText('chat', { exact: true }).first().waitFor({ timeout: 15000 })
  const seenButtons = page.getByRole('button', { name: 'Mark seen' })
  if (await seenButtons.count() > 0) {
    await seenButtons.first().click()
  }
  await page.getByLabel('Debug query').fill('Should I bring my HbA1c report?')
  await page.getByRole('button', { name: 'Inspect retrieval' }).click()
  await page.getByText('Diabetic eye check', { exact: false }).first().waitFor({ timeout: 60000 })
  for (const heading of ['Keyword', 'Vector', 'Hybrid']) {
    await page.getByText(heading, { exact: false }).first().waitFor()
  }

  if (pageErrors.length > 0) {
    throw new Error(`Browser page errors: ${pageErrors.join(', ')}`)
  }
  console.log('chat smoke: passed')
} catch (error) {
  console.error(error)
  throw error
} finally {
  await browser.close()
}
