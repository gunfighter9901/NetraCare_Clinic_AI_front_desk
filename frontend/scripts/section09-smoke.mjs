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

const frontendUrl = process.env.FRONTEND_URL ?? 'http://127.0.0.1:5173'

const patients = {
  anjali: ['9000000007', 'Anjali Desai'],
  kabir: ['9000000008', 'Kabir Singh'],
  asha: ['9000000001', 'Asha Verma'],
  neha: ['9000000011', 'Neha Joshi'],
  arjun: ['9000000012', 'Arjun Reddy'],
  zoya: ['9000000021', 'Zoya Khan'],
  aditya: ['9000000020', 'Aditya Bose'],
  imran: ['9000000004', 'Imran Sheikh'],
  mary: ['9000000009', 'Mary Thomas'],
  ravi: ['9000000010', 'Ravi Kumar'],
}

async function logout(page) {
  const button = page.getByRole('button', { name: 'Log out' })
  try {
    await button.waitFor({ timeout: 5000 })
  } catch {
    return
  }
  await button.click()
  await page.getByRole('tab', { name: 'Patient' }).waitFor({ timeout: 15000 })
}

async function loginPatient(page, [mobile, name]) {
  await page.getByRole('tab', { name: 'Patient' }).click()
  await page.getByPlaceholder('9000000001').fill(mobile)
  await page.getByPlaceholder('Asha Verma').fill(name)
  await page.getByRole('button', { name: 'Sign in as Patient' }).click()
  await page.getByRole('heading', { name: 'Your appointments' }).waitFor()
}

async function loginStaff(page) {
  await page.getByRole('tab', { name: 'Staff' }).click()
  await page.getByPlaceholder('Front Desk').fill('Front Desk')
  await page.getByRole('button', { name: 'Sign in as Staff' }).click()
  await page.getByRole('heading', { name: 'Clinic appointments' }).waitFor()
}

async function preparePatientBooking(page, doctorId, speciality, visitType, appointmentDate) {
  await page.waitForFunction(
    () => {
      const doctorSelect = [...document.querySelectorAll('select')].find((select) =>
        select.closest('label')?.textContent.includes('Doctor'),
      )
      return doctorSelect !== undefined && doctorSelect.options.length > 0
    },
    undefined,
    { timeout: 20000 },
  )
  await page.getByLabel('Date').fill(appointmentDate)
  await page.getByLabel('Doctor').selectOption(doctorId)
  await page.getByLabel('Speciality').selectOption(speciality)
  await page.getByLabel('Visit type').selectOption(visitType)
}

async function patientBooks(page, patient, doctorId, speciality, visitType, appointmentDate, time) {
  if (await page.getByRole('button', { name: 'Log out' }).count() > 0) {
    await logout(page)
  }
  await loginPatient(page, patient)
  await preparePatientBooking(page, doctorId, speciality, visitType, appointmentDate)
  await page.getByLabel('Direct time (optional)').fill(time)
  await fillBookingReason(page);
  await page.getByRole('button', { name: 'Book appointment' }).click()
}

async function expectPatientRefusal(page, message) {
  await page.getByRole('alert').filter({ hasText: message }).waitFor()
  await logout(page)
}

async function expectPatientBooking(page) {
  const success = await page
    .getByRole('status')
    .filter({ hasText: /Booked appointment A\d+\./ })
    .textContent({ timeout: 90000 })
  const appointmentId = /A\d+/.exec(success)?.[0]
  if (!appointmentId) throw new Error('Section 09 smoke could not read an appointment ID')
  const row = page.locator(`tr[data-appointment-id="${appointmentId}"]`)
  await row.getByText('booked').waitFor()
  return { appointmentId, row }
}

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await browser.newPage()
const pageErrors = []
page.on('pageerror', (error) => pageErrors.push(error.message))

const results = []

try {
  await page.goto(frontendUrl)

  await patientBooks(page, patients.neha, 'D1', 'General', 'new', '2026-11-30', '16:20')
  const first = await expectPatientBooking(page)
  results.push(['Book a new consultation with a free doctor in OPD', 'Booked, 20 minutes'])
  await logout(page)

  await patientBooks(page, patients.kabir, 'D1', 'General', 'new', '2026-11-30', '16:20')
  await expectPatientRefusal(page, 'Dr. Anand Rao already has an appointment overlapping that time')
  results.push(['Book the same doctor and time for another patient', 'Refused: slot taken'])

  await loginPatient(page, patients.neha)
  await first.row.getByRole('button', { name: 'Cancel' }).click()
  await page
    .getByRole('status')
    .filter({ hasText: `Cancelled appointment ${first.appointmentId}.` })
    .waitFor()
  await first.row.getByText('cancelled').waitFor()
  await logout(page)

  await patientBooks(page, patients.kabir, 'D1', 'Cataract', 'new', '2026-12-03', '09:00')
  await expectPatientRefusal(page, 'Dr. Anand Rao is in surgery during this session')
  results.push(['Book Dr. Rao on a Thursday morning', 'Refused: surgery session'])

  await patientBooks(page, patients.kabir, 'D2', 'Glaucoma', 'new', '2026-12-03', '10:00')
  await expectPatientRefusal(page, 'Dr. Meera Iyer is not at the clinic on Thursdays')
  results.push(['Book Dr. Iyer on any Thursday', 'Refused: doctor not at the clinic'])

  await patientBooks(page, patients.kabir, 'D1', 'General', 'new', '2026-11-30', '13:30')
  await expectPatientRefusal(page, 'Appointments must start between 9 AM and 1 PM or 2 PM and 6 PM')

  await patientBooks(page, patients.kabir, 'D1', 'General', 'new', '2026-11-29', '10:00')
  await expectPatientRefusal(page, 'The clinic is closed on Sundays')

  await patientBooks(page, patients.kabir, 'D1', 'General', 'new', '2026-12-25', '10:00')
  await expectPatientRefusal(page, 'The clinic is closed on 2026-12-25 for Christmas')
  results.push(['Book at 1:30 PM, on a Sunday, or on a listed holiday', 'Refused: clinic closed or outside session'])

  await patientBooks(page, patients.kabir, 'D1', 'General', 'new', '2026-11-30', '12:50')
  await expectPatientRefusal(page, 'The appointment would end after the clinic session')
  results.push(['Book a new consultation at 12:50 PM', 'Refused: would end after 1 PM'])

  await patientBooks(page, patients.kabir, 'D1', 'General', 'new', '2026-12-28', '10:00')
  await expectPatientRefusal(page, 'Appointments can only be booked up to 30 days ahead')

  await patientBooks(page, patients.kabir, 'D1', 'General', 'new', '2026-11-26', '10:00')
  await expectPatientRefusal(page, 'Appointment cannot be booked in the past')
  results.push(['Book more than 30 days ahead, or in the past', 'Refused: outside the booking window'])

  await loginStaff(page)
  const staffForm = page.locator('.booking-form')
  await staffForm.getByLabel('Date').fill('2026-12-01')
  await staffForm.getByLabel('Doctor').selectOption('D4')
  await staffForm.getByLabel('Speciality').selectOption('Glaucoma')
  await staffForm.getByLabel('Direct time (optional)').fill('10:00')
  await fillBookingReason(staffForm);
  await staffForm.getByRole('button', { name: 'Book appointment' }).click()
  await page
    .getByRole('alert')
    .filter({ hasText: 'Dr. Fatima Khan does not cover Glaucoma' })
    .waitFor()
  results.push(['Book Dr. Khan for Glaucoma', 'Refused: doctor does not cover it'])
  await logout(page)

  await patientBooks(page, patients.asha, 'D1', 'Cataract', 'new', '2026-11-30', '16:00')
  await expectPatientBooking(page)
  await logout(page)

  await patientBooks(page, patients.asha, 'D1', 'Cataract', 'new', '2026-11-30', '16:30')
  await expectPatientRefusal(page, 'Patient already has an active Cataract appointment')
  results.push(['Book a second Cataract appointment for a patient who has one', 'Refused: one active booking per speciality'])
  await logout(page)

  await patientBooks(page, patients.zoya, 'D1', 'General', 'follow_up', '2026-11-30', '16:30')
  await expectPatientRefusal(page, 'A follow-up requires a completed visit in this speciality')

  await patientBooks(page, patients.aditya, 'D2', 'Cataract', 'follow_up', '2026-11-30', '10:00')
  await expectPatientRefusal(page, 'Follow-up must be with Dr. Anand Rao, who completed the last Cataract visit')
  results.push(['Book a follow-up for a patient never seen, or with a different doctor', 'Refused: follow-up rule'])

  await patientBooks(page, patients.arjun, 'D1', 'Cataract', 'new', '2026-11-27', '11:00')
  const late = await expectPatientBooking(page)
  await late.row.getByRole('button', { name: 'Cancel' }).click()
  await page.getByRole('status').filter({ hasText: /sent to staff|waiting for staff|approval/i }).first().waitFor({ timeout: 15000 }).catch(async () => { await page.getByText(/sent to staff|waiting for staff|approval/i).first().waitFor() })
  await late.row.getByText('booked').waitFor()
  results.push(['Patient cancels an appointment starting in under 2 hours', 'To Staff: waiting for approval'])
  await logout(page)

  await loginStaff(page)
  await page.locator('.filter-card').getByLabel('Date').fill('2026-11-27')
  await page.locator('.filter-card').getByLabel('Doctor').selectOption('D1')
  const staffLateRow = page.locator(`tr[data-appointment-id="${late.appointmentId}"]`)
  await staffLateRow.getByText('booked').waitFor()
  await staffLateRow.getByRole('button', { name: 'Cancel' }).click()
  await page
    .getByRole('status')
    .filter({ hasText: `Cancelled appointment ${late.appointmentId}.` })
    .waitFor()
  await staffLateRow.getByText('cancelled').waitFor()
  results.push(['Staff cancels the same late appointment', 'Cancelled'])
  await logout(page)

  await patientBooks(page, patients.mary, 'D1', 'General', 'new', '2026-11-30', '14:00')
  const release = await expectPatientBooking(page)
  await release.row.getByRole('button', { name: 'Cancel' }).click()
  await page
    .getByRole('status')
    .filter({ hasText: `Cancelled appointment ${release.appointmentId}.` })
    .waitFor()
  await release.row.getByText('cancelled').waitFor()
  await logout(page)

  await patientBooks(page, patients.ravi, 'D1', 'General', 'new', '2026-11-30', '14:00')
  const releasedBooking = await expectPatientBooking(page)
  results.push(['Cancel a booking, then book that slot as someone else', 'Booked: the slot is free again'])
  await releasedBooking.row.getByRole('button', { name: 'Cancel' }).click()
  await page
    .getByRole('status')
    .filter({ hasText: `Cancelled appointment ${releasedBooking.appointmentId}.` })
    .waitFor()
  await releasedBooking.row.getByText('cancelled').waitFor()
  await logout(page)

  if (pageErrors.length > 0) {
    throw new Error(`Browser page errors: ${pageErrors.join(', ')}`)
  }
  if (results.length !== 13) {
    throw new Error(`Expected 13 section 09 checks, recorded ${results.length}`)
  }
  console.log('section 09 browser smoke: 13/13 passed')
  console.log(
    JSON.stringify(
      {
        clinicNow: '2026-11-27T10:00:00',
        weekdayDate: '2026-12-03',
        opdDate: '2026-11-30',
        sundayDate: '2026-11-29',
        holidayDate: '2026-12-25',
        pastDate: '2026-11-26',
        beyond30Date: '2026-12-28',
      },
      null,
      2,
    ),
  )
} catch (error) {
  console.error(await page.locator('body').innerText().catch(() => ''))
  throw error
} finally {
  await browser.close()
}
