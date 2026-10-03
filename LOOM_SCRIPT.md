# TruckTrack Loom Walkthrough

Target length: 3–5 minutes.

## 0:00–0:35 Product framing

- Show the empty state and planning rail.
- Explain that the assessment asks for three locations, current cycle usage, a mapped route, legal stops, and filled daily logs.
- Note that departure time is optional-but-prefilled and log metadata is kept out of the primary flow.

## 0:35–1:25 Complete a trip

- Enter a route that requires more than one driving day.
- Set cycle usage high enough to make the remaining-cycle indicator meaningful.
- Click “Plan compliant trip.”
- Point out the HGV route, numbered current/pickup/drop-off markers, and rest/fuel markers.
- Expand the turn-by-turn route book and show that maneuvers are grouped into current-to-pickup and pickup-to-drop-off legs.

## 1:25–2:15 Explain the schedule

- Walk across the route summary, compliance band, and ELD duty strip.
- Show pickup and drop-off as on-duty/not-driving.
- Show how a qualifying service stop resets the eight-hour driving-break clock.
- Point to a 10-hour sleeper period and, if present, a conservative 34-hour cycle restart.

## 2:15–2:55 Show the logs

- Scroll to the generated daily sheets.
- Explain that events crossing midnight are split by the terminal timezone and every page totals 24 hours.
- Demonstrate one PNG download, the ZIP download, and print/save PDF.

## 2:55–4:10 Code tour

- Open `backend/planner/scheduler.py`: explain the boundary-driven loop and why compliance lives on the server.
- Open `backend/planner/logs.py`: show the calendar-day projection and 24-hour invariant.
- Open `backend/planner/route_client.py`: show the provider adapter and normalized route model.
- Open `frontend/src/components/DutyStrip.tsx` and `LogSheet.tsx`: show how the same schedule model drives both visualizations.

## 4:10–4:40 Verification and tradeoffs

- Show the backend and frontend test results.
- Explain the deliberate aggregate-cycle limitation: without prior eight-day records, the planner uses a 34-hour restart instead of pretending to know rolling recapture.
- Close on the deployed URL, GitHub repository, and the disclaimer that this is not a certified ELD.
