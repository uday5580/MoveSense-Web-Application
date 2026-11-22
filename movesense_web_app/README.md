# MoveSense

MoveSense is a local activity-monitoring prototype with a Python-defined web UI,
a Python HTTP/data backend, and a small browser-side motion-sensor bridge.

## Stack

- **NiceGUI** renders the dashboard and application pages from Python.
- **FastAPI** endpoints (provided by NiceGUI) receive validated motion samples.
- **SQLite** persists session history and profile settings in `data/movesense.sqlite3`.
- `static/sensor_bridge.js` is only used to read the browser DeviceMotion API and
  send sensor samples to the Python backend. The application UI is not served
  from `index.html`.

## Run on Windows

Install Python 3.10 or newer and make sure it is available in PowerShell. Then:

```powershell
cd "C:\Users\kiran\Downloads\MoveSense_Web_Application\movesense_web_app"
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

Open `http://localhost:8000`. If PowerShell still says Python was not found,
install Python and enable **Add Python to PATH**, then reopen the terminal.
If port 8000 is already in use, run `$env:MOVESENSE_PORT = 8001` before
`python main.py`, then open `http://localhost:8001`.

## Features

- Activity dashboard with totals, recent sessions, search, filters, and activity breakdown
- Live accelerometer and gyroscope charts from supported phone browsers
- Demo sensor sessions for desktop browsers and testing
- Rule-based activity classification and approximate step counting
- Session history, CSV export, local analytics, profile and step-length settings
- SQLite persistence; sessions are not uploaded to a cloud service

The server binds to loopback by default. For phone sensor access, deploy it
behind HTTPS; do not expose this unauthenticated prototype directly to a
network. Browser permission and sensor support vary by device. Sensor-derived
steps, distance, pace, and activity labels are estimates, not medical
measurements.

## Deploy to Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/uday5580/MoveSense-Web-Application)

The included `render.yaml` deploys the application over HTTPS, which is required
for reliable smartphone motion-sensor access.

1. Push this project to GitHub.
2. In Render, choose **New > Blueprint** and select the repository.
3. Render will create the `movesense-web` service on the free web-service tier.
4. Open the Render HTTPS URL and test the dashboard with the demo mode first.

The deployed service is intentionally public and unauthenticated. Do not store
private or sensitive movement data on this deployment. The free tier does not
provide durable SQLite storage; saved sessions may reset when Render redeploys
or restarts the service.

## Tests

```powershell
python -m unittest discover -s tests
```
