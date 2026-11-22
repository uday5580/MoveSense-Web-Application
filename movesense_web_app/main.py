"""Python-defined MoveSense web UI and HTTP API."""

from __future__ import annotations

import asyncio
import csv
import io
import math
import os
from datetime import datetime
from functools import partial
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from nicegui import app, ui

from backend import (
    MotionSample,
    SensorError,
    clear_sessions,
    get_profile,
    list_sessions,
    tracker,
    update_profile,
)


ROOT = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
ui.colors(primary="#a4e635")
ui.add_head_html(
    '<meta name="theme-color" content="#090914">'
    '<script src="/static/sensor_bridge.js"></script>'
    """
    <style>
      :root { --ms-bg:#090914; --ms-panel:#151523; --ms-panel2:#1d1d2c;
        --ms-line:#2b2a3c; --ms-text:#f4f3fa; --ms-muted:#a3a2b5;
        --ms-lime:#a4e635; --ms-purple:#bd69f4; --ms-blue:#4d9dff; }
      body, .nicegui-content { background:var(--ms-bg); color:var(--ms-text); }
      body { background-image:radial-gradient(ellipse at 86% 60%,#26331b55 0,transparent 34%),
        radial-gradient(ellipse at 70% 0%,#25203b55 0,transparent 34%); }
      .nicegui-content { min-height:100vh; }
      .ms-main { max-width:1600px; margin:auto; }
      .ms-panel { background:linear-gradient(145deg,#171725f5,#12121ff5)!important;
        border:1px solid #ffffff0c!important; border-radius:15px!important;
        color:var(--ms-text); box-shadow:0 12px 36px #00000025; }
      .ms-muted { color:var(--ms-muted); }
      .ms-eyebrow { color:var(--ms-lime); font-size:10px; font-weight:700; letter-spacing:1.6px; }
      .ms-title { font-size:25px; font-weight:600; letter-spacing:-.6px; }
      .ms-heading { font-size:14px; font-weight:600; }
      .ms-subtitle { color:var(--ms-muted); font-size:12px; }
      .ms-stats { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:13px; }
      .ms-dashboard { display:grid; grid-template-columns:minmax(0,1.8fr) minmax(250px,.8fr); gap:13px; }
      .ms-monitor { display:grid; grid-template-columns:minmax(0,1.65fr) minmax(260px,.8fr); gap:13px; }
      .ms-gyro { grid-column:1/-1; }
      .ms-activity { border-radius:11px; background:#1b1b2a; padding:11px; }
      .ms-metric { background:#20202f; border:1px solid #ffffff08; border-radius:9px; padding:8px; }
      .ms-metric-label { font-size:9px; color:var(--ms-muted); }
      .ms-filter-active { color:var(--ms-lime)!important; background:#20202f!important; }
      .ms-topbar { display:grid; grid-template-columns:minmax(170px,1fr) auto minmax(220px,1fr);
        align-items:center; gap:14px; }
      .ms-brand { min-width:0; }
      .ms-brand-name { color:var(--ms-text); font-size:17px; font-weight:700; letter-spacing:-.3px; }
      .ms-topnav { flex-wrap:nowrap; justify-content:center; }
      .ms-top-actions { min-width:0; justify-content:flex-end; }
      .ms-search { width:160px; }
      .ms-nav { color:#b3b1c2; }
      .ms-nav-active { color:var(--ms-lime)!important; background:#1b1b2b!important; }
      .q-btn.ms-nav, .q-btn.ms-top-link { color:#b3b1c2!important; text-transform:none!important; }
      .q-btn.ms-top-link { flex:0 0 auto; }
      .q-btn.ms-nav-active { color:var(--ms-lime)!important; background:#1b1b2b!important; }
      .q-btn.ms-nav:hover, .q-btn.ms-top-link:hover { color:var(--ms-lime)!important; }
      .ms-badge { border:1px solid #333246; color:#d5d3df; border-radius:20px; padding:5px 10px; font-size:10px; }
      .q-field__control { background:#171725!important; border-radius:12px!important; }
      .q-field__native, .q-field__label { color:var(--ms-text)!important; }
      .q-table, .q-table__container { background:var(--ms-panel)!important; color:var(--ms-text)!important; }
      .q-table th { color:var(--ms-muted)!important; }
      @media(max-width:950px) {
        .ms-stats { grid-template-columns:repeat(2,minmax(0,1fr)); }
        .ms-dashboard,.ms-monitor { grid-template-columns:1fr; }
        .ms-gyro { grid-column:auto; }
      }
      @media(max-width:1100px) {
        .ms-topbar { grid-template-columns:minmax(140px,1fr) auto; }
        .ms-brand { grid-column:1; grid-row:1; }
        .ms-topnav { grid-column:1/-1; grid-row:2; justify-content:flex-start; overflow-x:auto; }
        .ms-top-actions { grid-column:2; grid-row:1; }
      }
      @media(max-width:600px) {
        .ms-title { font-size:21px; }
        .ms-stats { gap:8px; }
        .ms-sidebar { display:none!important; }
        .ms-topbar { grid-template-columns:1fr; gap:9px; }
        .ms-brand,.ms-top-actions,.ms-topnav { grid-column:1; }
        .ms-brand { grid-row:1; }
        .ms-top-actions { grid-row:2; justify-content:space-between; }
        .ms-topnav { grid-row:3; width:100%; flex-wrap:wrap; overflow:visible; }
        .ms-search { width:min(220px,65vw); }
        .ms-dashboard { grid-template-columns:minmax(0,1fr); }
        .ms-activity { align-items:flex-start; flex-wrap:wrap; }
      }
    </style>
    """
)


@app.get("/api/sensor/status")
def sensor_status() -> dict[str, Any]:
    return tracker.snapshot()


@app.post("/api/sensor/start")
def sensor_start() -> dict[str, bool]:
    try:
        tracker.start("phone")
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return {"ok": True}


@app.post("/api/sensor/sample")
def sensor_sample(sample: MotionSample) -> dict[str, Any]:
    return tracker.process(sample)


@app.post("/api/sensor/error")
def sensor_error(error: SensorError) -> dict[str, bool]:
    tracker.set_error(error.message)
    return {"ok": True}


@app.post("/api/sensor/stop")
def sensor_stop() -> dict[str, Any]:
    return {"ok": True, "session": tracker.stop()}


def format_time(seconds: int) -> str:
    return f"{seconds // 60:02}:{seconds % 60:02}"


def all_metrics() -> dict[str, Any]:
    sessions = list_sessions()
    live = tracker.snapshot()
    profile = get_profile()
    steps = sum(int(session["steps"]) for session in sessions)
    seconds = sum(int(session["seconds"]) for session in sessions)
    distance = sum(float(session["distance"]) for session in sessions)
    count = len(sessions)
    if live["active"]:
        steps += int(live["steps"])
        seconds += int(live["seconds"])
        distance += int(live["steps"]) * float(profile["step_length_cm"]) / 100000
        count += 1
    pace_seconds = round(seconds / distance) if distance >= 0.01 else 0
    return {
        "activities": count,
        "steps": steps,
        "seconds": seconds,
        "distance": distance,
        "pace": f"{pace_seconds // 60}:{pace_seconds % 60:02} min/km" if pace_seconds else "—",
    }


def line_chart_options(
    samples: list[dict[str, Any]],
    axes: tuple[tuple[str, str], ...],
) -> dict[str, Any]:
    colors = ["#a4e635", "#ef6c6c", "#4d9dff"]
    return {
        "backgroundColor": "transparent",
        "animation": False,
        "tooltip": {"trigger": "axis"},
        "legend": {
            "top": 0,
            "right": 4,
            "textStyle": {"color": "#a3a2b5", "fontSize": 10},
        },
        "grid": {"left": 44, "right": 18, "top": 35, "bottom": 28},
        "xAxis": {
            "type": "category",
            "data": [sample["time"] for sample in samples],
            "axisLabel": {"color": "#a3a2b5", "hideOverlap": True, "fontSize": 9},
            "axisLine": {"lineStyle": {"color": "#383748"}},
            "splitLine": {"show": False},
        },
        "yAxis": {
            "type": "value",
            "axisLabel": {"color": "#a3a2b5", "fontSize": 9},
            "splitLine": {"lineStyle": {"color": "#292838"}},
        },
        "series": [
            {
                "name": label,
                "type": "line",
                "showSymbol": False,
                "smooth": 0.15,
                "lineStyle": {"width": 1.5, "color": colors[index]},
                "data": [sample[key] for sample in samples],
            }
            for index, (label, key) in enumerate(axes)
        ],
    }


def breakdown_options() -> dict[str, Any]:
    sessions = list_sessions()
    walking = sum(session["activity"] == "Walking" for session in sessions)
    running = sum(session["activity"] == "Running" for session in sessions)
    other = len(sessions) - walking - running
    chart_data = (
        [
            {"name": "Walking", "value": walking},
            {"name": "Running", "value": running},
            {"name": "Other", "value": other},
        ]
        if sessions
        else [{"name": "No sessions", "value": 1, "itemStyle": {"color": "#292838"}}]
    )
    return {
        "backgroundColor": "transparent",
        "color": ["#a4e635", "#bd69f4", "#4d9dff"],
        "tooltip": {"trigger": "item"},
        "legend": {
            "bottom": 0,
            "show": bool(sessions),
            "textStyle": {"color": "#a3a2b5", "fontSize": 10},
        },
        "series": [
            {
                "type": "pie",
                "radius": ["56%", "76%"],
                "center": ["50%", "44%"],
                "label": {"show": False},
                "data": chart_data,
            }
        ],
        "graphic": [
            {
                "type": "text",
                "left": "center",
                "top": "38%",
                "style": {
                    "text": f"{len(sessions)}\nTotal",
                    "textAlign": "center",
                    "fill": "#f4f3fa",
                    "fontSize": 16,
                    "fontWeight": 600,
                    "lineHeight": 22,
                },
            }
        ],
    }


page_content: Any = None
page_title: Any = None
current_page = {"name": "dashboard"}
search_term = {"value": ""}
activity_filter = {"value": "all"}
page_refs: dict[str, Any] = {}
nav_controls: list[tuple[Any, str]] = []
filter_controls: list[tuple[Any, str]] = []


def metric_card(
    title: str,
    value: str,
    footnote: str,
    icon: str,
) -> ui.label:
    with ui.card().classes("ms-panel w-full"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(title).classes("text-xs text-grey-4")
            ui.icon(icon).classes("text-lime-5 text-lg")
        value_label = ui.label(value).classes("text-2xl font-semibold mt-3")
        ui.label(footnote).classes("text-[10px] ms-muted")
    return value_label


def build_recent_rows(container: Any) -> int:
    container.clear()
    sessions = list_sessions()
    query = search_term["value"].strip().lower()
    selected_filter = activity_filter["value"]
    visible = [
        session
        for session in sessions
        if (
            selected_filter == "all"
            or session["activity"] == selected_filter
            or (
                selected_filter == "other"
                and session["activity"] not in {"Walking", "Running"}
            )
        )
        and (
            not query
            or query
            in " ".join(
                str(session[key])
                for key in ("activity", "date", "steps", "distance", "source")
            ).lower()
        )
    ][:5]
    with container:
        if not visible:
            message = (
                "No activities match this filter."
                if sessions
                else "No sessions yet. Start monitoring or try demo data."
            )
            ui.label(message).classes("ms-muted text-center p-8 w-full")
            return 0
        for session in visible:
            stamp = datetime.fromisoformat(session["date"]).astimezone().strftime("%b %d, %Y")
            badge = "footprint" if session["activity"] == "Walking" else "monitor_heart"
            with ui.row().classes("w-full items-center gap-3 ms-activity"):
                ui.icon(badge).classes("text-purple-4 text-xl")
                with ui.column().classes("grow gap-0"):
                    ui.label(session["activity"]).classes("text-sm font-medium")
                    ui.label(f"{stamp} · {format_time(int(session['seconds']))}").classes(
                        "text-[10px] ms-muted"
                    )
                with ui.row().classes("gap-2"):
                    for label, value in (
                        ("Distance", f"{float(session['distance']):.2f} km"),
                        ("Time", format_time(int(session["seconds"]))),
                        ("Steps", f"{int(session['steps']):,}"),
                    ):
                        with ui.column().classes("ms-metric"):
                            ui.label(label).classes("ms-metric-label")
                            ui.label(value).classes("text-[10px]")
    return len(visible)


def render_dashboard() -> None:
    global page_refs, filter_controls
    page_refs = {}
    filter_controls = []
    with ui.row().classes("w-full items-end justify-between mb-4"):
        with ui.column().classes("gap-1"):
            ui.label("YOUR ACTIVITY HISTORY").classes("ms-eyebrow")
            ui.label("Activities").classes("ms-title")
            ui.label("Your movement sessions and sensor-powered mobility insights.").classes(
                "ms-subtitle"
            )
        ui.button(
            "Add activity",
            icon="add",
            on_click=lambda: navigate("monitor"),
        ).props("unelevated").classes("bg-lime-5 text-black rounded-full")

    metrics = all_metrics()
    with ui.element("div").classes("ms-stats mb-4"):
        page_refs["activities"] = metric_card(
            "Total activities",
            str(metrics["activities"]),
            "Saved monitoring sessions",
            "show_chart",
        )
        page_refs["distance"] = metric_card(
            "Total distance",
            f"{metrics['distance']:.2f} km",
            "Estimated from your step length",
            "place",
        )
        page_refs["pace"] = metric_card(
            "Average pace",
            metrics["pace"],
            "Estimated across recorded sessions",
            "speed",
        )
        page_refs["steps"] = metric_card(
            "Estimated steps",
            f"{metrics['steps']:,}",
            "Approximate movement peaks",
            "directions_walk",
        )

    with ui.row().classes("w-full items-center justify-between mb-2"):
        with ui.row().classes("gap-1"):
            for label, value in (
                ("All activities", "all"),
                ("Running", "Running"),
                ("Walking", "Walking"),
                ("Other", "other"),
            ):
                button = ui.button(
                    label,
                    on_click=partial(set_activity_filter, value),
                ).props("flat dense").classes("text-xs")
                if activity_filter["value"] == value:
                    button.classes("ms-filter-active")
                filter_controls.append((button, value))
        ui.label("Latest first").classes("text-xs ms-muted")

    with ui.element("div").classes("ms-dashboard w-full"):
        with ui.card().classes("ms-panel"):
            with ui.row().classes("w-full items-center justify-between mb-2"):
                ui.label("Recent activities").classes("ms-heading")
                page_refs["recent_count"] = ui.label("0 sessions").classes("text-xs ms-muted")
            page_refs["recent_rows"] = ui.column().classes("w-full gap-2")
            count = build_recent_rows(page_refs["recent_rows"])
            page_refs["recent_count"].set_text(f"{count} sessions")
        with ui.card().classes("ms-panel"):
            ui.label("Activity breakdown").classes("ms-heading")
            page_refs["breakdown"] = ui.echart(breakdown_options()).style("height:260px;width:100%")


def render_monitor() -> None:
    global page_refs
    page_refs = {}
    snapshot = tracker.snapshot()
    with ui.row().classes("w-full items-end justify-between mb-4"):
        with ui.column().classes("gap-1"):
            ui.label("DEVICE MOTION").classes("ms-eyebrow")
            ui.label("Live sensor monitoring").classes("ms-title")
            ui.label("Movement signals from your smartphone, visualized in real time.").classes(
                "ms-subtitle"
            )
        page_refs["live_pill"] = ui.label(
            "● SESSION ACTIVE" if snapshot["active"] else "● SESSION STOPPED"
        ).classes("ms-badge")

    with ui.element("div").classes("ms-monitor w-full"):
        with ui.card().classes("ms-panel"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("Accelerometer").classes("ms-heading")
                page_refs["elapsed"] = ui.label(format_time(snapshot["seconds"])).classes(
                    "text-xs ms-muted"
                )
            page_refs["accel_chart"] = ui.echart(
                line_chart_options(
                    snapshot["samples"],
                    (("X-axis", "x"), ("Y-axis", "y"), ("Z-axis", "z")),
                )
            ).style("height:340px;width:100%")
            with ui.row().classes("gap-2 mt-3"):
                ui.button("Start sensor session", icon="play_arrow").props(
                    "unelevated id=movesense-start"
                ).classes("bg-lime-5 text-black rounded-full")
                ui.button("Stop session", icon="stop", on_click=stop_sensor_session).props(
                    "outline"
                ).classes("rounded-full")
                ui.button("Try demo data", icon="science", on_click=start_demo).props(
                    "outline"
                ).classes("rounded-full")
            ui.label(
                "On iPhone/iPad, use Safari and allow motion access. HTTPS or localhost is required "
                "for browser sensor access. Demo data is available on unsupported devices."
            ).classes("ms-badge mt-3")
        with ui.card().classes("ms-panel"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("Device readings").classes("ms-heading")
                ui.label("Live values").classes("text-xs text-lime-5")
            page_refs["sensor_error"] = ui.label(snapshot["last_error"]).classes(
                "text-xs text-red-3 mt-2"
            )
            with ui.column().classes("w-full gap-2 mt-3"):
                ui.label("ACCELERATION · m/s²").classes("ms-eyebrow")
                for axis, key in (("X AXIS", "x"), ("Y AXIS", "y"), ("Z AXIS", "z")):
                    page_refs[f"axis_{key}"] = sensor_value(axis, snapshot["latest"][key])
                ui.label("ROTATION RATE · °/s").classes("ms-eyebrow mt-3")
                for axis, key in (
                    ("ALPHA", "alpha"),
                    ("BETA", "beta"),
                    ("GAMMA", "gamma"),
                ):
                    page_refs[f"axis_{key}"] = sensor_value(axis, snapshot["latest"][key])
            page_refs["activity"] = ui.label(snapshot["activity"]).classes(
                "text-3xl font-semibold mt-5"
            )
            page_refs["confidence"] = ui.label("Waiting for sensor input").classes(
                "text-sm ms-muted"
            )
        with ui.card().classes("ms-panel ms-gyro"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("Gyroscope tracker").classes("ms-heading")
                ui.label("°/s").classes("text-xs ms-muted")
            page_refs["gyro_chart"] = ui.echart(
                line_chart_options(
                    snapshot["samples"],
                    (("Gyro X", "alpha"), ("Gyro Y", "beta"), ("Gyro Z", "gamma")),
                )
            ).style("height:190px;width:100%")


def sensor_value(label: str, value: float) -> ui.label:
    with ui.row().classes("w-full items-center justify-between ms-metric"):
        ui.label(label).classes("ms-metric-label")
        value_label = ui.label(f"{value:.2f}").classes("font-semibold")
    return value_label


def render_recognition() -> None:
    global page_refs
    page_refs = {}
    snapshot = tracker.snapshot()
    ui.label("ACTIVITY CLASSIFICATION").classes("ms-eyebrow")
    ui.label("Activity recognition").classes("ms-title")
    ui.label("Rule-based estimates from the latest motion signals.").classes("ms-subtitle mb-4")
    with ui.element("div").classes("ms-stats"):
        page_refs["activity"] = metric_card(
            "Detected activity", snapshot["activity"], "Current classification", "sensors"
        )
        page_refs["steps"] = metric_card(
            "Step estimate", str(snapshot["steps"]), "During current session", "directions_walk"
        )
        page_refs["intensity"] = metric_card(
            "Signal intensity", "Low", "Based on recent acceleration", "speed"
        )
        page_refs["duration"] = metric_card(
            "Session duration", format_time(snapshot["seconds"]), "Current session", "schedule"
        )
    with ui.card().classes("ms-panel w-full mt-4"):
        ui.label("Recognition logic").classes("ms-heading")
        ui.label(
            "MoveSense smooths accelerometer magnitude and evaluates recent signal variation. "
            "Repeated movement peaks are an approximate step signal. Activity labels are estimated "
            "with a transparent heuristic, not a trained or clinically validated model."
        ).classes("ms-subtitle leading-7 mt-2")
        with ui.row().classes("gap-3 mt-4"):
            page_refs["magnitude"] = metric_card(
                "Smoothed magnitude", f"{snapshot['magnitude']:.2f}", "m/s²", "waves"
            )
            page_refs["peaks"] = metric_card(
                "Peak events", str(snapshot["peaks"]), "Approximate step events", "show_chart"
            )


def render_analytics() -> None:
    all_sessions = list_sessions()
    sessions = list(reversed(all_sessions[:8]))
    profile = get_profile()
    steps = sum(int(session["steps"]) for session in all_sessions)
    seconds = sum(int(session["seconds"]) for session in all_sessions)
    distance = sum(float(session["distance"]) for session in all_sessions)
    walking = sum(session["activity"] == "Walking" for session in all_sessions)
    running = sum(session["activity"] == "Running" for session in all_sessions)
    ui.label("YOUR MOVEMENT PATTERNS").classes("ms-eyebrow")
    ui.label("Mobility analytics").classes("ms-title")
    ui.label("Insights from sessions saved on this device.").classes("ms-subtitle mb-4")
    with ui.element("div").classes("ms-dashboard w-full"):
        with ui.card().classes("ms-panel"):
            ui.label("Steps by session").classes("ms-heading")
            ui.echart(
                {
                    "backgroundColor": "transparent",
                    "tooltip": {"trigger": "axis"},
                    "grid": {"left": 45, "right": 15, "top": 20, "bottom": 40},
                    "xAxis": {
                        "type": "category",
                        "data": [
                            datetime.fromisoformat(session["date"]).astimezone().strftime("%b %d")
                            for session in sessions
                        ],
                        "axisLabel": {"color": "#a3a2b5"},
                    },
                    "yAxis": {
                        "type": "value",
                        "axisLabel": {"color": "#a3a2b5"},
                        "splitLine": {"lineStyle": {"color": "#292838"}},
                    },
                    "series": [
                        {
                            "type": "bar",
                            "name": "Steps",
                            "data": [int(session["steps"]) for session in sessions],
                            "itemStyle": {"color": "#a4e635", "borderRadius": [5, 5, 0, 0]},
                        }
                    ],
                }
            ).style("height:270px;width:100%")
        with ui.card().classes("ms-panel"):
            ui.label("Mobility summary").classes("ms-heading")
            for label, value in (
                ("Total steps", f"{steps:,}"),
                ("Total active time", f"{seconds // 60} min"),
                ("Walking sessions", str(walking)),
                ("Running sessions", str(running)),
                ("Estimated distance", f"{distance:.2f} km"),
                ("Step length", f"{float(profile['step_length_cm']):.0f} cm"),
            ):
                with ui.row().classes("w-full justify-between py-2 border-b border-gray-800"):
                    ui.label(label).classes("text-xs ms-muted")
                    ui.label(value).classes("text-xs")
    ui.label(
        "Distance and activity labels are estimates. Sensor values remain on this device."
    ).classes("ms-badge mt-3")


def render_history() -> None:
    ui.label("YOUR ACTIVITY HISTORY").classes("ms-eyebrow")
    ui.label("Session records").classes("ms-title")
    with ui.row().classes("w-full justify-between items-center my-3"):
        ui.label("Sessions are stored in the local SQLite database.").classes("ms-subtitle")
        ui.button("Export CSV", icon="download", on_click=export_csv).props("outline").classes(
            "rounded-full"
        )
    rows = []
    for session in list_sessions():
        rows.append(
            {
                **session,
                "date": datetime.fromisoformat(session["date"])
                .astimezone()
                .strftime("%b %d, %Y %H:%M"),
                "duration": format_time(int(session["seconds"])),
                "distance": f"{float(session['distance']):.3f} km",
            }
        )
    ui.table(
        columns=[
            {"name": "date", "label": "DATE & TIME", "field": "date", "align": "left"},
            {"name": "activity", "label": "ACTIVITY", "field": "activity", "align": "left"},
            {"name": "duration", "label": "DURATION", "field": "duration", "align": "left"},
            {"name": "steps", "label": "STEPS", "field": "steps", "align": "left"},
            {"name": "distance", "label": "DISTANCE", "field": "distance", "align": "left"},
        ],
        rows=rows,
        row_key="id",
    ).classes("w-full ms-panel")


def render_settings() -> None:
    profile = get_profile()
    ui.label("PREFERENCES").classes("ms-eyebrow")
    ui.label("Profile & settings").classes("ms-title")
    ui.label("Personalize estimates and manage locally stored data.").classes("ms-subtitle mb-4")
    with ui.row().classes("w-full gap-3"):
        with ui.card().classes("ms-panel w-full"):
            ui.label("Personal profile").classes("ms-heading")
            name_input = ui.input("Display name", value=profile["name"]).props(
                "maxlength=30"
            ).classes("w-full")
            step_input = ui.number(
                "Average step length (cm)",
                value=float(profile["step_length_cm"]),
                min=30,
                max=120,
                step=1,
            ).classes("w-full")

            def save_settings() -> None:
                try:
                    update_profile(name_input.value or "User", float(step_input.value or 70))
                except ValueError as error:
                    ui.notify(str(error), type="negative")
                    return
                ui.notify("Preferences saved on this device.", type="positive")
                refresh_visible_data()

            ui.button("Save preferences", icon="save", on_click=save_settings).props(
                "unelevated"
            ).classes("bg-lime-5 text-black rounded-full mt-2")
        with ui.card().classes("ms-panel w-full"):
            ui.label("Data & privacy").classes("ms-heading")
            ui.label(
                "Monitoring sessions and profile preferences are stored in a local SQLite "
                "database. No movement data is uploaded to a cloud service."
            ).classes("ms-subtitle leading-7 mt-2")
            dialog = ui.dialog()
            with dialog, ui.card().classes("ms-panel"):
                ui.label("Delete all saved activity sessions?").classes("text-base")
                with ui.row().classes("w-full justify-end gap-2 mt-3"):
                    ui.button("Cancel", on_click=dialog.close).props("flat")

                    def confirm_clear() -> None:
                        clear_sessions()
                        dialog.close()
                        ui.notify("Saved activity sessions were deleted.", type="positive")
                        refresh_visible_data()

                    ui.button("Delete", on_click=confirm_clear).props("unelevated color=negative")
            ui.button("Clear saved activity data", icon="delete", on_click=dialog.open).props(
                "outline color=negative"
            ).classes("rounded-full mt-4")


def build_page() -> None:
    global page_refs, filter_controls
    page_refs = {}
    filter_controls = []
    page_content.clear()
    with page_content:
        if current_page["name"] == "dashboard":
            render_dashboard()
        elif current_page["name"] == "monitor":
            render_monitor()
        elif current_page["name"] == "recognition":
            render_recognition()
        elif current_page["name"] == "analytics":
            render_analytics()
        elif current_page["name"] == "history":
            render_history()
        else:
            render_settings()


def refresh_visible_data() -> None:
    if current_page["name"] in {"dashboard", "analytics", "history", "settings"}:
        build_page()


def navigate(page: str) -> None:
    current_page["name"] = page
    titles = {
        "dashboard": "Activities",
        "monitor": "Live sensors",
        "recognition": "Activity recognition",
        "analytics": "Analytics",
        "history": "Activity history",
        "settings": "Settings",
    }
    page_title.set_text(titles[page])
    for button, button_page in nav_controls:
        if button_page == page:
            button.classes("ms-nav-active")
        else:
            button.classes(remove="ms-nav-active")
    build_page()


def set_activity_filter(value: str) -> None:
    activity_filter["value"] = value
    for button, filter_value in filter_controls:
        button.style(
            "color:#a4e635;background:#20202f" if filter_value == value else ""
        )
    if page_refs.get("recent_rows") is not None:
        count = build_recent_rows(page_refs["recent_rows"])
        page_refs["recent_count"].set_text(f"{count} sessions")


async def stop_sensor_session() -> None:
    snapshot = tracker.snapshot()
    if not snapshot["active"]:
        ui.notify("No monitoring session is active.", type="warning")
        return
    if snapshot["source"] == "phone":
        await ui.run_javascript(
            "return await window.MoveSenseSensors.stop();",
            timeout=5.0,
        )
    else:
        session = tracker.stop()
        if session is not None:
            ui.notify("Demo session saved.", type="positive")
    refresh_visible_data()


async def start_demo() -> None:
    if tracker.snapshot()["active"]:
        ui.notify("Stop the current session before starting a demo.", type="warning")
        return
    tracker.start("demo")
    for index in range(36):
        if not tracker.snapshot()["active"]:
            break
        acceleration = (
            math.sin(index * 0.8) * 2,
            math.cos(index * 0.6) * 2,
            9.8 + math.sin(index * 0.8) * 3.5,
        )
        sample = MotionSample(
            x=acceleration[0],
            y=acceleration[1],
            z=acceleration[2],
            alpha=math.sin(index * 0.4) * 1.4,
            beta=math.cos(index * 0.5) * 1.1,
            gamma=math.sin(index * 0.7) * 0.9,
        )
        tracker.process(sample)
        await asyncio.sleep(0.16)
    if tracker.snapshot()["active"]:
        session = tracker.stop()
        if session is not None:
            ui.notify("Demo session saved.", type="positive")
        refresh_visible_data()


def export_csv() -> None:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Date", "Activity", "Duration seconds", "Steps", "Distance km", "Source"])
    for session in list_sessions():
        writer.writerow(
            [
                session["date"],
                session["activity"],
                session["seconds"],
                session["steps"],
                session["distance"],
                session["source"],
            ]
        )
    ui.download(output.getvalue(), "movesense-activity-history.csv")


def refresh_dashboard() -> None:
    metrics = all_metrics()
    for key, value in (
        ("activities", str(metrics["activities"])),
        ("steps", f"{metrics['steps']:,}"),
        ("distance", f"{metrics['distance']:.2f} km"),
        ("pace", metrics["pace"]),
    ):
        element = page_refs.get(key)
        if element is not None:
            element.set_text(value)
    recent_rows = page_refs.get("recent_rows")
    if recent_rows is not None:
        count = build_recent_rows(recent_rows)
        count_label = page_refs.get("recent_count")
        if count_label is not None:
            count_label.set_text(f"{count} sessions")
    breakdown = page_refs.get("breakdown")
    if breakdown is not None:
        breakdown.options.update(breakdown_options())
        breakdown.update()


def refresh_monitor() -> None:
    if current_page["name"] not in {"monitor", "recognition"}:
        return
    snapshot = tracker.snapshot()
    refs = page_refs
    live_pill = refs.get("live_pill")
    if live_pill is not None:
        live_pill.set_text(
            "● SESSION ACTIVE" if snapshot["active"] else "● SESSION STOPPED"
        )
    for key in ("accel_chart", "gyro_chart"):
        chart = refs.get(key)
        if chart is None:
            continue
        axes = (
            (("X-axis", "x"), ("Y-axis", "y"), ("Z-axis", "z"))
            if key == "accel_chart"
            else (("Gyro X", "alpha"), ("Gyro Y", "beta"), ("Gyro Z", "gamma"))
        )
        chart.options.update(line_chart_options(snapshot["samples"], axes))
        chart.update()
    elapsed = refs.get("elapsed")
    if elapsed is not None:
        elapsed.set_text(format_time(snapshot["seconds"]))
    for axis in ("x", "y", "z", "alpha", "beta", "gamma"):
        label = refs.get(f"axis_{axis}")
        if label is not None:
            label.set_text(f"{snapshot['latest'][axis]:.2f}")
    activity = refs.get("activity")
    if activity is not None:
        activity.set_text(snapshot["activity"])
    confidence = refs.get("confidence")
    if confidence is not None:
        intensity = "High" if snapshot["magnitude"] > 14 else "Moderate" if snapshot["magnitude"] > 10 else "Low"
        confidence.set_text(
            snapshot["last_error"]
            or f"Movement intensity: {intensity} · heuristic estimate"
        )
    error_label = refs.get("sensor_error")
    if error_label is not None:
        error_label.set_text(snapshot["last_error"])
    for key, value in (
        ("steps", str(snapshot["steps"])),
        ("duration", format_time(snapshot["seconds"])),
        ("magnitude", f"{snapshot['magnitude']:.2f}"),
        ("peaks", str(snapshot["peaks"])),
        ("intensity", "High" if snapshot["magnitude"] > 14 else "Moderate" if snapshot["magnitude"] > 10 else "Low"),
    ):
        label = refs.get(key)
        if label is not None:
            label.set_text(value)


def build_navigation_button(
    label: str,
    page: str,
    icon: str | None = None,
    compact: bool = False,
    accessible_label: str | None = None,
) -> Any:
    button = ui.button(
        label,
        icon=icon,
        on_click=partial(navigate, page),
    ).props("flat")
    button.classes("ms-nav" if not compact else "ms-top-link text-xs")
    if page == current_page["name"]:
        button.classes("ms-nav-active")
    if not compact:
        title = accessible_label or label
        button.props(f'title="{title}" aria-label="{title}"')
    nav_controls.append((button, page))
    return button


with ui.row().classes("w-full min-h-screen no-wrap"):
    with ui.column().classes("ms-sidebar items-center gap-2 p-3 border-r border-gray-900"):
        ui.label("M").classes(
            "grid place-items-center w-10 h-10 rounded-xl bg-lime-5 text-black font-black text-xl mb-4"
        )
        for label, page, icon in (
            ("Overview", "dashboard", "dashboard"),
            ("Live monitoring", "monitor", "show_chart"),
            ("Recognition", "recognition", "sensors"),
            ("Analytics", "analytics", "bar_chart"),
            ("History", "history", "history"),
            ("Settings", "settings", "settings"),
        ):
            build_navigation_button("", page, icon, accessible_label=label)
    with ui.column().classes("ms-main flex-1 min-w-0 p-4 md:p-7"):
        with ui.element("header").classes("ms-topbar w-full mb-5"):
            with ui.column().classes("ms-brand gap-0"):
                ui.label("MOVEMENT INTELLIGENCE").classes("ms-eyebrow")
                ui.label("MoveSense").classes("ms-brand-name")
            with ui.row().classes("ms-topnav items-center gap-1"):
                for label, page in (
                    ("Dashboard", "dashboard"),
                    ("Activities", "history"),
                    ("Live sensors", "monitor"),
                    ("Analytics", "analytics"),
                    ("Settings", "settings"),
                ):
                    build_navigation_button(label, page, compact=True)
            with ui.row().classes("ms-top-actions items-center gap-2"):
                ui.input(
                    placeholder="Search activities",
                    on_change=lambda event: update_search(event.value),
                ).props('dense outlined clearable aria-label="Search activities"').classes("ms-search")
                with ui.row().classes("items-center gap-2 no-wrap"):
                    ui.avatar("U").classes("bg-lime-7 text-black")
                    ui.label(get_profile()["name"]).classes("text-xs")
            page_title = ui.label("Activities").classes("sr-only")
        page_content = ui.column().classes("w-full")
        with page_content:
            render_dashboard()


def update_search(value: str | None) -> None:
    search_term["value"] = value or ""
    rows = page_refs.get("recent_rows")
    if rows is not None:
        count = build_recent_rows(rows)
        count_label = page_refs.get("recent_count")
        if count_label is not None:
            count_label.set_text(f"{count} sessions")


ui.timer(0.5, refresh_monitor)
ui.timer(1.0, refresh_dashboard)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        title="MoveSense | Activity Intelligence",
        host=os.environ.get("MOVESENSE_HOST", "127.0.0.1"),
        port=int(os.environ.get("MOVESENSE_PORT", os.environ.get("PORT", "8000"))),
        reload=False,
        show=False,
    )
