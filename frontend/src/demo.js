// Demo & testing student accounts seeded by backend/store/seed.py.
export const DEMO_PASSWORD = 'punca-demo-2026'
export const DEMO_STUDENT = { email: 'student@punca.demo', password: DEMO_PASSWORD }

export const DEMO_ACCOUNTS = [
  {
    name: 'Demo Student',
    email: 'student@punca.demo',
    studentId: 'TP068421',
    label: 'Fresh Student (Empty Passport)',
    hint: 'Clean slate for live demo walkthroughs',
  },
  {
    name: 'Aisyah Rahman',
    email: 'aisyah.student@demo.punca.edu',
    studentId: 'TP071204',
    label: 'Aisyah · Mid-Journey',
    hint: '5 completed stamps, 1 re-entry, Chain Rule gap',
  },
  {
    name: 'Hafiz Tan',
    email: 'hafiz.student@demo.punca.edu',
    studentId: 'TP072819',
    label: 'Hafiz · Circle Partner',
    hint: 'Shares Chain Rule gap & Tue 14:00 slot with Aisyah',
  },
  {
    name: 'Priya Nair',
    email: 'priya.student@demo.punca.edu',
    studentId: 'TP065110',
    label: 'Priya · Advanced Passport',
    hint: '12 completed stamps + 2 needing re-entry across modules',
  },
  {
    name: 'QA Tester',
    email: 'qa.tester@demo.punca.edu',
    studentId: 'TP079900',
    label: 'QA Tester · Onboarding',
    hint: 'Opens directly on Passport Setup screen',
  },
]
