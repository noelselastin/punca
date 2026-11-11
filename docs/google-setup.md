# Google Workspace in Punca

Punca connects to Google with plain links. It never signs in to Google itself, so there is no Google
Cloud setup, no consent screen and no list of test users. Each link opens in a new tab, in whichever
Google account the student is signed in to in that browser.

| Feature | What happens |
| --- | --- |
| Google Calendar | Punca saves the session, then opens Google Calendar with the title, time, notes, peer emails and Meet room filled in. The student presses **Save** there. |
| Google Docs | Punca keeps the note, copies it to the clipboard and opens a new Google Doc. The student pastes it in (Ctrl+V). |
| Study tasks | Punca keeps its own study to-do list (Google Workspace → Study tasks), and **Add route to my study tasks** on a diagnosis result adds each step of the rebuild route to it. These tasks stay in Punca: Google Tasks has no link that adds a task, so **Open Google Tasks** opens tasks.google.com for the student to add them there. |
| Google Meet | **Start Google Meet** opens meet.google.com/new. Pasting the room link pins it to the study circle for every member. |

Sign-up asks for the student's personal email (any provider). It is the sign-in address and the contact
email shown to study partners who are allowed to see it.

## Live mode (not used)

An earlier build could also write straight into a student's Google account through Google sign-in
(`backend/google_live.py`, switched on by `GOOGLE_OAUTH_CLIENT_ID`). The web app no longer offers it,
so leave `GOOGLE_OAUTH_CLIENT_ID` unset.
