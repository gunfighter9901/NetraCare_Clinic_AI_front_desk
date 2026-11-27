import { chromium } from 'playwright'


async function fillBookingReason(scope) {
  const reason = scope.getByLabel(/reason for your visit|Reason for visit/i);
  try {
    await reason.fill('Routine eye test and new glasses');
  } catch {
    // Field may not be visible in this context.
  }
}

async function fillDoctorNote(scope) {
  const note = scope.getByLabel(/Doctor note for completion/i);
  try {
    await note.fill('Smoke test note: vision stable, review as needed.');
  } catch {
    // Field may not be visible in this context.
  }
}


async function waitForDoctors(scope) {
  await scope.waitForFunction(
    () => {
      const doctorSelect = [...document.querySelectorAll('select')].find((select) =>
        select.closest('label')?.textContent.includes('Doctor'),
      )
      return doctorSelect !== undefined && doctorSelect.options.length > 0
    },
    undefined,
    { timeout: 20000 },
  )
}

const frontendUrl = process.env.FRONTEND_URL ?? 'http://127.0.0.1:5173'

async function loginPatient(page, mobile, name) {
  await page.getByRole('tab', { name: 'Patient' }).click()
  await page.getByPlaceholder('9000000001').fill(mobile)
  await page.getByPlaceholder('Asha Verma').fill(name)
  await page.getByRole('button', { name: 'Sign in as Patient' }).click()
  await page.getByRole('heading', { name: 'Your appointments' }).waitFor()
}

async function prepareBooking(
  page,
  doctorId,
  speciality,
  appointmentDate,
  visitType = 'new',
  requireSlots = true,
) {
  await page.getByLabel('Date').fill(appointmentDate)
  await waitForDoctors(page);
  await page.getByLabel('Doctor').selectOption(doctorId)
  await page.getByLabel('Speciality').selectOption(speciality)
  await page.getByLabel('Visit type').selectOption(visitType)
  if (!requireSlots) return
  await page.waitForFunction(
    () => {
      const slotSelect = [...document.querySelectorAll('select')].find((select) =>
        select.closest('label')?.textContent.includes('Free time'),
      )
      return slotSelect !== undefined && slotSelect.options.length > 0
    },
    undefined,
    { timeout: 10_000 },
  )
}

async function waitForNoSlotMessage(page, message) {
  await page.getByText(message).waitFor()
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const pageErrors = []

try {
  const page = await browser.newPage()
  page.on('pageerror', (error) => pageErrors.push(error.message))
  await page.goto(frontendUrl)
  await loginPatient(page, '9000000004', 'Imran Sheikh')

  await prepareBooking(page, 'D2', 'Glaucoma', '2026-12-01', 'new', false)
  await waitForNoSlotMessage(page, 'Dr. Meera Iyer is in surgery during this session')

  await prepareBooking(page, 'D2', 'Glaucoma', '2026-12-03', 'new', false)
  await waitForNoSlotMessage(page, 'Dr. Meera Iyer is not at the clinic on Thursdays')

  await prepareBooking(page, 'D1', 'General', '2026-12-25', 'new', false)
  await waitForNoSlotMessage(page, 'The clinic is closed on 2026-12-25 for Christmas')

  await prepareBooking(page, 'D1', 'General', '2026-11-30')
  await fillBookingReason(page);
  await page.getByRole('button', { name: 'Book appointment' }).click()
  await page.getByRole('status').filter({ hasText: /Booked appointment A\d+\./ }).waitFor()
  await page.waitForFunction(
    () => {
      const slotSelect = [...document.querySelectorAll('select')].find((select) =>
        select.closest('label')?.textContent.includes('Free time'),
      )
      return slotSelect !== undefined && slotSelect.options.length > 0
    },
    undefined,
    { timeout: 10_000 },
  )
  await fillBookingReason(page);
  await page.getByRole('button', { name: 'Book appointment' }).click()
  await page
    .getByRole('alert')
    .filter({ hasText: 'Patient already has an active General appointment' })
    .waitFor()

  await prepareBooking(page, 'D1', 'Cataract', '2026-11-27')
  await page.waitForFunction(
    () => {
      const slotSelect = [...document.querySelectorAll('select')].find((select) =>
        select.closest('label')?.textContent.includes('Free time'),
      )
      return slotSelect !== undefined && [...slotSelect.options].some((option) => option.value === '10:20:00')
    },
    undefined,
    { timeout: 10_000 },
  )
  await page.getByLabel('Free time').selectOption('10:20:00')
  await fillBookingReason(page);
  await page.getByRole('button', { name: 'Book appointment' }).click()
  const lateSuccess = await page
    .getByRole('status')
    .filter({ hasText: /Booked appointment A\d+\./ })
    .textContent()
  const lateAppointmentId = /A\d+/.exec(lateSuccess)?.[0]
  if (!lateAppointmentId) throw new Error('Rule-message smoke could not read the late appointment ID')
  const lateRow = page.locator(`tr[data-appointment-id="${lateAppointmentId}"]`)
  await lateRow.getByText('booked').waitFor()
  await lateRow.getByRole('button', { name: 'Cancel' }).click()
  await page.getByRole('status').filter({ hasText: /sent to staff|waiting for staff|approval/i }).first().waitFor({ timeout: 15000 }).catch(async () => { await page.getByText(/sent to staff|waiting for staff|approval/i).first().waitFor() })
  await lateRow.getByText('booked').waitFor()

  const contextA = await browser.newContext()
  const contextB = await browser.newContext()
  const doublePageA = await contextA.newPage()
  const doublePageB = await contextB.newPage()
  doublePageA.on('pageerror', (error) => pageErrors.push(error.message))
  doublePageB.on('pageerror', (error) => pageErrors.push(error.message))

  await doublePageA.goto(frontendUrl)
  await loginPatient(doublePageA, '9000000005', 'Priya Menon')
  await prepareBooking(doublePageA, 'D1', 'General', '2026-11-30')

  await doublePageB.goto(frontendUrl)
  await loginPatient(doublePageB, '9000000006', 'Suresh Patil')
  await prepareBooking(doublePageB, 'D1', 'General', '2026-11-30')

  const staleSlot = await doublePageA.getByLabel('Free time').locator('option').first().getAttribute('value')
  await doublePageB.getByLabel('Free time').selectOption(staleSlot)
  await doublePageA.getByLabel('Free time').selectOption(staleSlot)

  await fillBookingReason(doublePageA);
  await doublePageA.getByRole('button', { name: 'Book appointment' }).click()
  await doublePageA.getByRole('status').filter({ hasText: /Booked appointment A\d+\./ }).waitFor()
  await fillBookingReason(doublePageB);
  await doublePageB.getByRole('button', { name: 'Book appointment' }).click()
  await doublePageB
    .getByRole('alert')
    .filter({ hasText: 'Dr. Anand Rao already has an appointment overlapping that time' })
    .waitFor()

  await contextA.close()
  await contextB.close()

  if (pageErrors.length > 0) {
    throw new Error(`Browser page errors: ${pageErrors.join(', ')}`)
  }
  console.log('rule-message smoke: passed')
} catch (error) {
  console.error(error)
  throw error
} finally {
  await browser.close()
}
