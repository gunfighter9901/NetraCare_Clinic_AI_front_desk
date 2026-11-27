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

async function login(page, role, fill) {
  await page.getByRole('tab', { name: role }).click()
  await fill()
  await page.getByRole('button', { name: `Sign in as ${role}` }).click()
}

async function logout(page) {
  await page.getByRole('button', { name: 'Log out' }).click()
  await page.getByRole('tab', { name: 'Patient' }).waitFor()
}

async function patientBookingFlow(page) {
  await page.getByRole('heading', { name: 'Your appointments' }).waitFor()
  const slotSelect = page.getByLabel('Free time')
  await slotSelect.waitFor()
  await page.getByLabel('Date').fill('2026-11-30')
  await waitForDoctors(page);
  await page.getByLabel('Doctor').selectOption('D3')
  await page.getByLabel('Speciality').selectOption('Retina')
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
  const startTime = await slotSelect.inputValue()
  if (!startTime) throw new Error('Patient smoke found no free slot')

  await fillBookingReason(page);
  await page.getByRole('button', { name: 'Book appointment' }).click()
  const success = await page.getByRole('status').filter({ hasText: /Booked appointment A\d+\./ }).textContent()
  const appointmentId = /A\d+/.exec(success)?.[0]
  if (!appointmentId) throw new Error('Patient smoke could not read the booked appointment ID')
  const appointmentRow = page.locator(`tr[data-appointment-id="${appointmentId}"]`)
  await appointmentRow.getByText('booked').waitFor()
  await page.waitForFunction(
    (value) => {
      const selects = [...document.querySelectorAll('select')]
      const slotSelect = selects.find((select) => [...select.options].some((option) => option.value === value))
      return slotSelect === undefined || slotSelect.value !== value
    },
    startTime,
    { timeout: 10_000 },
  )

  await logout(page)
  await login(page, 'Patient', async () => {
    await page.getByPlaceholder('9000000001').fill('9000000002')
    await page.getByPlaceholder('Asha Verma').fill('Rohan Gupta')
  })
  await page.getByRole('heading', { name: 'Your appointments' }).waitFor()
  if ((await page.locator(`tr[data-appointment-id="${appointmentId}"]`).count()) !== 0) {
    throw new Error('Another patient can see Asha’s appointment')
  }
  if ((await page.getByText('Asha Verma').count()) !== 0) {
    throw new Error('Another patient can see Asha’s name')
  }

  await logout(page)
  await login(page, 'Patient', async () => {
    await page.getByPlaceholder('9000000001').fill('9000000001')
    await page.getByPlaceholder('Asha Verma').fill('Asha Verma')
  })
  await appointmentRow.getByRole('button', { name: 'Cancel' }).click()
  await page
    .getByRole('status')
    .filter({ hasText: `Cancelled appointment ${appointmentId}.` })
    .waitFor()
  await appointmentRow.getByText('cancelled').waitFor()
}

async function staffWorkflowFlow(page) {
  await page.getByRole('heading', { name: 'Clinic appointments' }).waitFor()
  const form = page.locator('.booking-form')
  await form.waitFor()

  await page.locator('.filter-card').getByLabel('Date').fill('2026-11-27')
  await waitForDoctors(page);
  await page.locator('.filter-card').getByLabel('Doctor').selectOption('D1')
  await form.getByLabel('Date').fill('2026-11-27')

  await waitForDoctors(page);
  await form.getByLabel('Doctor').selectOption('D4')
  await form.getByLabel('Speciality').selectOption('Glaucoma')
  await form.waitFor()
  await page.waitForFunction(
    () => {
      const slotSelect = [...document.querySelectorAll('.booking-form select')].find((select) =>
        select.closest('label')?.textContent.includes('Free time'),
      )
      return slotSelect !== undefined && slotSelect.options.length > 0
    },
    undefined,
    { timeout: 10_000 },
  )
  await fillBookingReason(form);
  await form.getByRole('button', { name: 'Book appointment' }).click()
  await page
    .getByRole('alert')
    .filter({ hasText: 'Dr. Fatima Khan does not cover Glaucoma' })
    .waitFor()

  await waitForDoctors(page);
  await form.getByLabel('Doctor').selectOption('D1')
  await form.getByLabel('Speciality').selectOption('General')
  await form.getByRole('combobox', { name: /^Patient/ }).selectOption('P02')
  await page.waitForFunction(
    () => {
      const slotSelect = [...document.querySelectorAll('.booking-form select')].find((select) =>
        select.closest('label')?.textContent.includes('Free time'),
      )
      return slotSelect !== undefined && slotSelect.options.length > 0
    },
    undefined,
    { timeout: 10_000 },
  )
  const existingSlot = await form.getByLabel('Free time').locator('option').first().getAttribute('value')
  if (!existingSlot) throw new Error('Staff smoke found no existing-patient slot')
  await form.getByLabel('Free time').selectOption(existingSlot)
  await fillBookingReason(form);
  await form.getByRole('button', { name: 'Book appointment' }).click()
  const existingSuccess = await page
    .getByRole('status')
    .filter({ hasText: /Booked appointment A\d+ for Rohan Gupta\./ })
    .textContent()
  const existingId = /A\d+/.exec(existingSuccess)?.[0]
  if (!existingId) throw new Error('Staff smoke could not read the existing-patient appointment ID')

  await form.getByText('Walk-in').click()
  const walkInMobile = `9${String(Date.now()).slice(-9)}`
  await form.getByLabel('Walk-in name').fill('Smoke Walk In')
  await form.getByLabel('Walk-in mobile').fill(walkInMobile)
  await form.waitFor()
  await page.waitForFunction(
    () => {
      const slotSelect = [...document.querySelectorAll('.booking-form select')].find((select) =>
        select.closest('label')?.textContent.includes('Free time'),
      )
      return slotSelect !== undefined && slotSelect.options.length > 0
    },
    undefined,
    { timeout: 10_000 },
  )
  const walkInSlot = await form.getByLabel('Free time').locator('option').first().getAttribute('value')
  if (!walkInSlot) throw new Error('Staff smoke found no walk-in slot')
  await form.getByLabel('Free time').selectOption(walkInSlot)
  await fillBookingReason(form);
  await form.getByRole('button', { name: 'Book appointment' }).click()
  const walkInSuccess = await page
    .getByRole('status')
    .filter({ hasText: /Booked appointment A\d+ for Smoke Walk In\./ })
    .textContent()
  const walkInId = /A\d+/.exec(walkInSuccess)?.[0]
  if (!walkInId) throw new Error('Staff smoke could not read the walk-in appointment ID')

  const existingRow = page.locator(`tr[data-appointment-id="${existingId}"]`)
  const walkInRow = page.locator(`tr[data-appointment-id="${walkInId}"]`)
  await existingRow.getByText('booked').waitFor()
  await walkInRow.getByText('booked').waitFor()
  await existingRow.getByRole('button', { name: 'Cancel' }).click()
  await page
    .getByRole('status')
    .filter({ hasText: `Cancelled appointment ${existingId}.` })
    .waitFor()
  await existingRow.getByText('cancelled').waitFor()
  await walkInRow.getByRole('button', { name: 'Cancel' }).click()
  await page
    .getByRole('status')
    .filter({ hasText: `Cancelled appointment ${walkInId}.` })
    .waitFor()
  await walkInRow.getByText('cancelled').waitFor()
}

async function doctorCompletionFlow(page) {
  await login(page, 'Patient', async () => {
    await page.getByPlaceholder('9000000001').fill('9000000020')
    await page.getByPlaceholder('Asha Verma').fill('Aditya Bose')
  })
  await page.getByRole('heading', { name: 'Your appointments' }).waitFor()
  await page.getByLabel('Date').fill('2026-11-30')
  await waitForDoctors(page);
  await page.getByLabel('Doctor').selectOption('D1')
  await page.getByLabel('Speciality').selectOption('Cataract')
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
  const consultationSlot = await page.getByLabel('Free time').locator('option').first().getAttribute('value')
  await page.getByLabel('Free time').selectOption(consultationSlot)
  await fillBookingReason(page);
  await page.getByRole('button', { name: 'Book appointment' }).click()
  const consultationSuccess = await page
    .getByRole('status')
    .filter({ hasText: /Booked appointment A\d+\./ })
    .textContent()
  const consultationId = /A\d+/.exec(consultationSuccess)?.[0]
  if (!consultationId) throw new Error('Doctor smoke could not read the consultation ID')
  await page.locator(`tr[data-appointment-id="${consultationId}"]`).getByText('booked').waitFor()
  await logout(page)

  await login(page, 'Doctor', async () => {
    await page.locator('select').selectOption({ index: 0 })
  })
  await page.getByRole('heading', { name: 'Your schedule' }).waitFor()
  await page.getByLabel('Date').fill('2026-11-30')
  const consultationRow = page.locator(`tr[data-appointment-id="${consultationId}"]`)
  await consultationRow.getByText('booked').waitFor()
  await fillDoctorNote(consultationRow);
  await fillDoctorNote(page);
  await consultationRow.getByRole('button', { name: 'Complete' }).click()
  await page
    .getByRole('status')
    .filter({ hasText: `Completed visit ${consultationId}.` })
    .waitFor()
  await consultationRow.getByText('completed').waitFor()
  await logout(page)

  await login(page, 'Patient', async () => {
    await page.getByPlaceholder('9000000001').fill('9000000020')
    await page.getByPlaceholder('Asha Verma').fill('Aditya Bose')
  })
  await page.getByRole('heading', { name: 'Your appointments' }).waitFor()
  await page.getByLabel('Date').fill('2026-11-30')
  await waitForDoctors(page);
  await page.getByLabel('Doctor').selectOption('D2')
  await page.getByLabel('Speciality').selectOption('Cataract')
  await page.getByLabel('Visit type').selectOption('follow_up')
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
  const wrongDoctorSlot = await page.getByLabel('Free time').locator('option').first().getAttribute('value')
  await page.getByLabel('Free time').selectOption(wrongDoctorSlot)
  await fillBookingReason(page);
  await page.getByRole('button', { name: 'Book appointment' }).click()
  await page
    .getByRole('alert')
    .filter({ hasText: 'Follow-up must be with Dr. Anand Rao' })
    .waitFor()

  await waitForDoctors(page);
  await page.getByLabel('Doctor').selectOption('D1')
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
  const followUpSlot = await page.getByLabel('Free time').locator('option').first().getAttribute('value')
  await page.getByLabel('Free time').selectOption(followUpSlot)
  await fillBookingReason(page);
  await page.getByRole('button', { name: 'Book appointment' }).click()
  const followUpSuccess = await page
    .getByRole('status')
    .filter({ hasText: /Booked appointment A\d+\./ })
    .textContent()
  const followUpId = /A\d+/.exec(followUpSuccess)?.[0]
  if (!followUpId) throw new Error('Doctor smoke could not read the follow-up ID')
  const followUpRow = page.locator(`tr[data-appointment-id="${followUpId}"]`)
  await followUpRow.getByText('booked').waitFor()
  await followUpRow.getByRole('button', { name: 'Cancel' }).click()
  await page
    .getByRole('status')
    .filter({ hasText: `Cancelled appointment ${followUpId}.` })
    .waitFor()
  await followUpRow.getByText('cancelled').waitFor()
  await logout(page)
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage()
const pageErrors = []
page.on('pageerror', (error) => pageErrors.push(error.message))

try {
  await page.goto(frontendUrl)
  await page.getByRole('heading', { name: 'NetraCare' }).waitFor()
  await page.getByRole('tab', { name: 'Patient' }).waitFor()
  await page.getByPlaceholder('9000000001').waitFor()

  await login(page, 'Staff', async () => {
    await page.getByPlaceholder('Front Desk').fill('Front Desk')
  })
  await page.getByRole('heading', { name: 'Clinic appointments' }).waitFor()
  await staffWorkflowFlow(page)
  await logout(page)

  await doctorCompletionFlow(page)

  await login(page, 'Patient', async () => {
    await page.getByPlaceholder('9000000001').fill('9000000001')
    await page.getByPlaceholder('Asha Verma').fill('Asha Verma')
  })
  await page.getByRole('heading', { name: 'Your appointments' }).waitFor()
  await patientBookingFlow(page)
  await logout(page)

  if (pageErrors.length > 0) {
    throw new Error(`Browser page errors: ${pageErrors.join(', ')}`)
  }
  console.log('browser smoke: passed')
} catch (error) {
  console.error(await page.locator('body').innerText())
  throw error
} finally {
  await browser.close()
}
