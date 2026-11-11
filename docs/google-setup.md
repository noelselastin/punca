# Turning on Google sign-in

Punca can write to a student's own Google Calendar and Google Docs. That needs one value from Google
Cloud: an **OAuth client ID**. Until it is set, Punca still works, with these stand-ins:

| Feature | Without the client ID | With the client ID |
| --- | --- | --- |
| Add to Google Calendar | Opens Google Calendar with the session filled in | Session is created in your calendar, with a Meet room |
| Save notes to Google Docs | Notes are kept in Punca | A real Google Doc is created in your Google account |

Punca's study task list stays inside Punca; it is not sent to Google Tasks.

## One-time setup (about 10 minutes)

1. Open <https://console.cloud.google.com/> and create a project (any name, for example "Punca").
2. **APIs & Services → Library**: enable **Google Calendar API** and **Google Drive API**. Punca uses
   the Drive API only to create its Google Docs, in a "Punca Study Materials" folder.
3. **APIs & Services → OAuth consent screen**: choose **External**, fill in the app name and your email,
   and leave the app in **Testing**. Under **Test users**, add the Gmail address of every person who
   will try Punca (up to 100). People who are not on that list cannot connect.
4. **APIs & Services → Credentials → Create credentials → OAuth client ID**:
   - Application type: **Web application**
   - **Authorised JavaScript origins**: add every address Punca is opened from, for example
     `http://localhost:8000`, `http://127.0.0.1:8000`, `http://localhost:5173`, and the public link.
   - No redirect URI is needed.
5. Copy the **Client ID** (it ends in `.apps.googleusercontent.com`) into the `.env` file at the repo root:

   ```
   GOOGLE_OAUTH_CLIENT_ID=1234567890-abc123.apps.googleusercontent.com
   ```

6. Restart the Punca server. The Google Workspace page now shows **Connect Google account**.

## Things to know

- **One client ID serves every student.** It identifies the Punca app, not a person or a computer.
  Each student signs in with their own Google account, and Punca writes only to that account.
- **The public link changes.** A free Cloudflare quick tunnel gets a new address on every restart, and
  Google only allows sign-in from addresses listed in step 4. Add the new address each time, or demo
  from `http://localhost:8000`.
- **"Google hasn't verified this app".** Testers see this warning once because the app is in Testing.
  They choose **Advanced → Go to Punca**. Removing the warning needs Google's verification review.
- **What Punca asks for.** Calendar events, and access to files Punca itself creates (its Google Docs).
  It cannot see any other file in the student's Drive. The list is `SCOPES` in `backend/google_live.py`.
- **Tokens are not stored.** The Google access token lives in the server's memory for about an hour
  and is never written to the store or the log. After that the student reconnects with one click.
- **Sign-up email.** Punca pre-selects the personal Gmail given at sign-up when the Google window opens.

## Testing without the client ID

Testers can connect one account for an hour without any Google Cloud setup:

1. Open <https://developers.google.com/oauthplayground/>.
2. In step 1, paste these scopes into "Input your own scopes" and authorise with your Google account:
   `https://www.googleapis.com/auth/drive.file https://www.googleapis.com/auth/calendar.events openid email profile`
3. In step 2, press **Exchange authorization code for tokens** and copy the **Access token**.
4. In Punca: **Google Workspace → Customize & Access → Temporary Google access token**, paste, save.
