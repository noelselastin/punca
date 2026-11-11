# Punca Windows runtime

The `Punca-Runtime` Windows task starts at this user's sign-in and runs independently of an AI app or terminal. It runs with normal user permissions, allows operation on battery, has no execution time limit, and restarts after failure. It does not disable sleep or change power settings.

The supervisor checks services every 15 seconds. It restarts stopped processes, restarts a stalled application after three failed health checks, and gives Cloudflare several minutes to reconnect before replacing a lost tunnel. Exact command-line matching allows safe adoption of already-running Punca processes. Only matching or child processes owned by the supervisor are stopped.

- Local preview: http://localhost:5173 (current uncommitted source, copied preview data, offline AI mode, live Google configuration).
- Public app on port 8000: isolated last-published release `52ca23b`, original store, existing production frontend bundle. Google OAuth remains off here until the pending new version and a stable origin are approved.
- Current links and service status: http://localhost:8766
- Always redirects to the latest available temporary public link: http://localhost:8766/public (works only on this laptop).
- Runtime configuration, service logs and status: `logs/hosting/` (Git-ignored; configuration has no credentials). The isolated release `.env` is also ignored.

Use **Punca links**, **Punca local preview**, or **Punca public site** from the Windows Start menu. These start the task if needed. No desktop shortcuts are created.

## Operating limits

The laptop must be on, awake, signed in, and connected to the internet to serve the site. A Cloudflare Quick Tunnel has no uptime guarantee; its hostname changes when recreated. Existing shared URLs cannot be restored after Cloudflare removes them. New public OAuth origins must be registered separately. Always-on hosting and a stable hostname are needed for reliable public availability independent of this laptop.

## Maintenance

Run `Start-ScheduledTask -TaskName Punca-Runtime` to start the supervisor. Its configuration is `logs/hosting/supervisor-config.json`. Before intentional maintenance, stop the task and the specifically identified Punca child processes; stopping the task alone may leave already-running services alive. To disable startup without deleting anything, use `Disable-ScheduledTask -TaskName Punca-Runtime`.

Dependencies: the user's existing Python 3.13 with `psutil`, the project's virtual environment, Node/Vite, and the existing Cloudflare executable. The supervisor creates no hosted resources, changes no repository branch, and never commits or pushes.
