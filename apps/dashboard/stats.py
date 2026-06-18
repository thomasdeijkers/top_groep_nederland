import os
import shutil
import ctypes
import ctypes.wintypes
import time
from datetime import datetime

from psycopg2 import sql

from shared.db.connection import get_connection
from apps.dashboard.otys_usage import OTYS_LOW_REMAINING_THRESHOLD, get_otys_usage_summary


STAT_DEFINITIONS = [
    {
        "key": "new_documents",
        "label": "Nieuwe documenten",
        "tables": ("documents", "documenten"),
        "status_columns": ("status", "document_status"),
        "status_values": ("nieuw", "new"),
    },
    {
        "key": "employees",
        "label": "Medewerkers",
        "tables": ("employees", "medewerkers"),
    },
    {
        "key": "timesheets",
        "label": "Urenstaten",
        "tables": ("timesheets", "urenstaten"),
    },
]

REVIEW_TABLES = ("documents", "documenten")
REVIEW_STATUS_COLUMNS = ("status", "review_status")
REVIEW_STATUS_VALUES = ("te_controleren", "pending_review", "needs_review")


def get_health():
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
        return {"status": "ok", "database": "connected"}
    except Exception as exc:
        return {"status": "error", "database": "unavailable", "detail": str(exc)}


def get_dashboard_stats():
    try:
        with get_connection() as conn:
            cards = [_build_count_card(conn, definition) for definition in STAT_DEFINITIONS]
            cards.append(_build_review_card(conn))
        return {
            "database": {"status": "connected"},
            "cards": cards,
        }
    except Exception as exc:
        return {
            "database": {"status": "unavailable", "detail": str(exc)},
            "cards": [_empty_card(definition) for definition in STAT_DEFINITIONS]
            + [{"key": "to_review", "label": "Te controleren", "value": 0}],
        }


def get_empty_dashboard_stats():
    return {
        "database": {"status": "not loaded"},
        "cards": [_empty_card(definition) for definition in STAT_DEFINITIONS]
        + [{"key": "to_review", "label": "Te controleren", "value": 0}],
    }


def get_database_status():
    return _database_status()


def get_server_overview():
    database = _database_status()
    cpu = _cpu_usage()
    memory = _memory_usage()
    database_size = _database_size_usage(database)
    scheduled_jobs = _placeholder_scheduled_jobs()
    otys_tiles = _otys_usage_tiles()

    system_tiles = [
        {
            "label": "Database connectie",
            "value": "OK" if database["status"] == "connected" else "Offline",
            "meta": database["meta"],
            "level": 100 if database["status"] == "connected" else 0,
            "tone": "good" if database["status"] == "connected" else "danger",
        },
        {
            "label": "Server belasting",
            "value": cpu["value"],
            "meta": cpu["meta"],
            "level": cpu["level"],
            "tone": cpu["tone"],
        },
        {
            "label": "Geheugen",
            "value": memory["value"],
            "meta": memory["meta"],
            "level": memory["level"],
            "tone": memory["tone"],
        },
        {
            "label": "Database gebruik",
            "value": database_size["value"],
            "meta": database_size["meta"],
            "level": database_size["level"],
            "tone": database_size["tone"],
        },
    ]

    scheduler_tiles = [
        {
            "label": "Cronjobs",
            "value": f"{len(scheduled_jobs)} klaar",
            "meta": "0 fout",
            "level": 100,
            "tone": "good",
        },
        {
            "label": "Laatste succes",
            "value": "-",
            "meta": "nog geen run",
            "level": 0,
            "tone": "neutral",
        },
        {
            "label": "Laatste fout",
            "value": "-",
            "meta": "geen fout bekend",
            "level": 0,
            "tone": "good",
        },
        {
            "label": "Volgende run",
            "value": "-",
            "meta": "scheduler placeholder",
            "level": 0,
            "tone": "neutral",
        },
    ]

    return {
        "database": database,
        "server_system_tiles": system_tiles,
        "server_scheduler_tiles": scheduler_tiles,
        "server_otys_tiles": otys_tiles,
        "server_metrics": system_tiles,
        "scheduled_jobs": scheduled_jobs,
    }


def _placeholder_scheduled_jobs():
    return [
        {
            "job": "Mail ophalen",
            "category": "Tickets",
            "schedule": "Placeholder",
            "status": "Nog niet actief",
            "last_run": "-",
            "next_run": "-",
        },
        {
            "job": "Urenstaten controleren",
            "category": "Urenverwerking",
            "schedule": "Placeholder",
            "status": "Nog niet actief",
            "last_run": "-",
            "next_run": "-",
        },
        {
            "job": "OTYS synchronisatie",
            "category": "Import",
            "schedule": "Placeholder",
            "status": "Nog niet actief",
            "last_run": "-",
            "next_run": "-",
        },
        {
            "job": "Database onderhoud",
            "category": "Systeem",
            "schedule": "Placeholder",
            "status": "Nog niet actief",
            "last_run": "-",
            "next_run": "-",
        },
    ]


def _otys_usage_tiles():
    usage = get_otys_usage_summary()
    minute_calls = usage.get("minute_calls", 0)
    hour_calls = usage.get("hour_calls", 0)
    day_calls = usage.get("day_calls", 0)
    official_limit = usage.get("limit_per_minute", 350)
    safe_limit = usage.get("safe_limit_per_minute", 330)
    safe_remaining = usage.get("safe_remaining_minute", max(safe_limit - minute_calls, 0))
    latest_remaining = usage.get("latest_remaining")
    min_remaining = usage.get("min_remaining_hour")
    blocked = usage.get("day_blocked", 0)
    last_error = usage.get("latest_error") or usage.get("last_error") or "geen fout bekend"
    latest_status = usage.get("latest_status")
    timeframe = usage.get("latest_timeframe")

    remaining_label = "-" if latest_remaining is None else str(latest_remaining)
    remaining_meta = "nog geen OTYS-call gelogd"
    if latest_remaining is not None:
        remaining_meta = f"laatste venster, reset over {timeframe}s" if timeframe is not None else "laatst bekende OTYS-header"

    if latest_remaining is None:
        remaining_tone = "neutral"
        remaining_level = 0
    elif latest_remaining <= OTYS_LOW_REMAINING_THRESHOLD:
        remaining_tone = "warning"
        remaining_level = 15
    else:
        remaining_tone = "good"
        remaining_level = min((latest_remaining / official_limit) * 100, 100)

    return [
        {
            "label": "OTYS calls minuut",
            "value": f"{minute_calls}/{official_limit}",
            "meta": f"veilige marge: {safe_remaining} over, {hour_calls} in 1 uur",
            "level": min((minute_calls / official_limit) * 100, 100),
            "tone": "warning" if minute_calls >= safe_limit else "good",
        },
        {
            "label": "OTYS veilige ruimte",
            "value": str(safe_remaining),
            "meta": f"throttle actief vanaf {safe_limit}/min",
            "level": min((safe_remaining / safe_limit) * 100, 100) if safe_limit else 0,
            "tone": "warning" if safe_remaining <= OTYS_LOW_REMAINING_THRESHOLD else "good",
        },
        {
            "label": "OTYS resterend",
            "value": remaining_label,
            "meta": remaining_meta,
            "level": remaining_level,
            "tone": remaining_tone,
        },
        {
            "label": "OTYS blokkades",
            "value": str(blocked),
            "meta": f"laatste 24 uur, {day_calls} calls",
            "level": 100 if blocked else 0,
            "tone": "danger" if blocked else "good",
        },
        {
            "label": "OTYS laatste status",
            "value": str(latest_status or "-"),
            "meta": last_error[:90],
            "level": 100 if latest_status and int(latest_status) < 400 else 0,
            "tone": "good" if latest_status and int(latest_status) < 400 else "neutral",
        },
        {
            "label": "OTYS laagste rest",
            "value": "-" if min_remaining is None else str(min_remaining),
            "meta": "laagste gemeten restant dit uur",
            "level": 0 if min_remaining is None else min((min_remaining / official_limit) * 100, 100),
            "tone": "warning" if min_remaining is not None and min_remaining <= OTYS_LOW_REMAINING_THRESHOLD else "good",
        },
    ]


def _build_count_card(conn, definition):
    table_name = _first_existing_table(conn, definition["tables"])
    if table_name is None:
        return _empty_card(definition)

    if "status_columns" in definition:
        for column_name in definition["status_columns"]:
            if _column_exists(conn, table_name, column_name):
                return {
                    "key": definition["key"],
                    "label": definition["label"],
                    "value": _count_status_rows(
                        conn,
                        table_name,
                        column_name,
                        definition["status_values"],
                    ),
                }

    return {
        "key": definition["key"],
        "label": definition["label"],
        "value": _count_rows(conn, table_name),
    }


def _build_review_card(conn):
    table_name = _first_existing_table(conn, REVIEW_TABLES)
    if table_name is None:
        return {"key": "to_review", "label": "Te controleren", "value": 0}

    for column_name in REVIEW_STATUS_COLUMNS:
        if _column_exists(conn, table_name, column_name):
            return {
                "key": "to_review",
                "label": "Te controleren",
                "value": _count_status_rows(
                    conn,
                    table_name,
                    column_name,
                    REVIEW_STATUS_VALUES,
                ),
            }

    return {"key": "to_review", "label": "Te controleren", "value": 0}


def _empty_card(definition):
    return {"key": definition["key"], "label": definition["label"], "value": 0}


def _first_existing_table(conn, table_names):
    for table_name in table_names:
        if _table_exists(conn, table_name):
            return table_name
    return None


def _table_exists(conn, table_name):
    with conn.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s);", (f"public.{table_name}",))
        return cursor.fetchone()[0] is not None


def _column_exists(conn, table_name, column_name):
    with conn.cursor() as cursor:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = %s
              AND column_name = %s;
            """,
            (table_name, column_name),
        )
        return cursor.fetchone() is not None


def _count_rows(conn, table_name):
    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL("SELECT COUNT(*) FROM {};").format(sql.Identifier(table_name))
        )
        return cursor.fetchone()[0]


def _count_status_rows(conn, table_name, column_name, status_values):
    with conn.cursor() as cursor:
        cursor.execute(
            sql.SQL("SELECT COUNT(*) FROM {} WHERE {} = ANY(%s);").format(
                sql.Identifier(table_name),
                sql.Identifier(column_name),
            ),
            (list(status_values),),
        )
        return cursor.fetchone()[0]


def _database_status():
    started = datetime.now()
    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        current_database(),
                        current_user,
                        COALESCE(inet_server_addr()::text, %s),
                        COALESCE(inet_server_port()::text, %s),
                        now();
                    """,
                    (os.getenv("DB_HOST", "database"), os.getenv("DB_PORT", "")),
                )
                database_name, database_user, host, port, database_time = cursor.fetchone()
        latency_ms = int((datetime.now() - started).total_seconds() * 1000)
        host_label = f"{host}:{port}" if port else host
        return {
            "status": "connected",
            "label": "connected",
            "detail": f"{database_name} als {database_user}",
            "meta": f"{host_label} - {latency_ms} ms",
            "latency_ms": latency_ms,
            "database_time": database_time,
        }
    except Exception as exc:
        return {
            "status": "unavailable",
            "label": "unavailable",
            "detail": str(exc),
            "meta": "Geen verbinding met database",
            "latency_ms": None,
            "database_time": None,
        }


def _server_usage():
    metrics = []
    load = _cpu_usage()
    metrics.append(
        {
            "label": "Server belasting",
            "value": load["value"],
            "meta": load["meta"],
            "level": load["level"],
            "tone": load["tone"],
        }
    )

    memory = _memory_usage()
    metrics.append(
        {
            "label": "Geheugen",
            "value": memory["value"],
            "meta": memory["meta"],
            "level": memory["level"],
            "tone": memory["tone"],
        }
    )

    disk = shutil.disk_usage(os.getenv("SERVER_USAGE_PATH", os.getcwd()))
    disk_percent = round((disk.used / disk.total) * 100, 1) if disk.total else 0
    metrics.append(
        {
            "label": "Server opslag",
            "value": f"{disk_percent}%",
            "meta": f"{_format_bytes(disk.used)} / {_format_bytes(disk.total)}",
            "level": disk_percent,
            "tone": _usage_tone(disk_percent),
        }
    )
    return metrics


def _database_usage(database):
    if database["status"] != "connected":
        return [
            {
                "label": "Database gebruik",
                "value": "-",
                "meta": "Niet beschikbaar zonder verbinding",
                "level": 0,
                "tone": "danger",
            },
            {
                "label": "Database sessies",
                "value": "-",
                "meta": "Niet beschikbaar zonder verbinding",
                "level": 0,
                "tone": "danger",
            },
        ]

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        pg_database_size(current_database()),
                        (
                            SELECT COUNT(*)
                            FROM pg_stat_activity
                            WHERE datname = current_database()
                        ),
                        current_setting('max_connections')::int;
                    """
                )
                database_size, active_sessions, max_connections = cursor.fetchone()
        session_percent = round((active_sessions / max_connections) * 100, 1) if max_connections else 0
        return [
            {
                "label": "Database gebruik",
                "value": _format_bytes(database_size),
                "meta": "huidige databasegrootte",
                "level": min(database_size / (1024 * 1024 * 1024) * 10, 100),
                "tone": "good",
            },
            {
                "label": "Database sessies",
                "value": str(active_sessions),
                "meta": f"van {max_connections} connecties",
                "level": session_percent,
                "tone": _usage_tone(session_percent),
            },
        ]
    except Exception as exc:
        return [
            {
                "label": "Database gebruik",
                "value": "-",
                "meta": str(exc),
                "level": 0,
                "tone": "danger",
            },
        ]


def _database_size_usage(database):
    if database["status"] != "connected":
        return {
            "value": "-",
            "meta": "niet beschikbaar zonder verbinding",
            "level": 0,
            "tone": "danger",
        }

    try:
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT pg_database_size(current_database());")
                database_size = cursor.fetchone()[0]
        return {
            "value": _format_bytes(database_size),
            "meta": "huidige databasegrootte",
            "level": min(database_size / (1024 * 1024 * 1024) * 10, 100),
            "tone": "good",
        }
    except Exception as exc:
        return {
            "value": "-",
            "meta": str(exc),
            "level": 0,
            "tone": "danger",
        }


def _cpu_usage():
    if os.name == "nt":
        return _windows_cpu_usage()

    try:
        one_minute, _, _ = os.getloadavg()
        cpu_count = os.cpu_count() or 1
        percent = round(min((one_minute / cpu_count) * 100, 100), 1)
        return {
            "value": f"{percent}%",
            "meta": f"load {one_minute:.2f} - {cpu_count} cores",
            "level": percent,
            "tone": _usage_tone(percent),
        }
    except (AttributeError, OSError):
        return {
            "value": "-",
            "meta": "Load niet beschikbaar op dit platform",
            "level": 0,
            "tone": "neutral",
        }


def _windows_cpu_usage():
    first = _windows_system_times()
    time.sleep(0.08)
    second = _windows_system_times()
    if not first or not second:
        return {
            "value": "-",
            "meta": "CPU-meting niet beschikbaar",
            "level": 0,
            "tone": "neutral",
        }

    idle_delta = second["idle"] - first["idle"]
    total_delta = second["total"] - first["total"]
    percent = round(max(0, min(100, (1 - idle_delta / total_delta) * 100)), 1) if total_delta else 0
    return {
        "value": f"{percent}%",
        "meta": f"{os.cpu_count() or 1} cores",
        "level": percent,
        "tone": _usage_tone(percent),
    }


def _windows_system_times():
    if os.name != "nt":
        return None

    idle = ctypes.wintypes.FILETIME()
    kernel = ctypes.wintypes.FILETIME()
    user = ctypes.wintypes.FILETIME()
    if not ctypes.windll.kernel32.GetSystemTimes(
        ctypes.byref(idle),
        ctypes.byref(kernel),
        ctypes.byref(user),
    ):
        return None

    idle_value = _filetime_to_int(idle)
    kernel_value = _filetime_to_int(kernel)
    user_value = _filetime_to_int(user)
    return {"idle": idle_value, "total": kernel_value + user_value}


def _filetime_to_int(filetime):
    return (filetime.dwHighDateTime << 32) + filetime.dwLowDateTime


def _memory_usage():
    if os.name == "nt":
        windows_memory = _windows_memory_usage()
        if windows_memory:
            return windows_memory

    meminfo = _read_linux_meminfo()
    if not meminfo:
        return {
            "value": "-",
            "meta": "Geheugenmeting niet beschikbaar",
            "level": 0,
            "tone": "neutral",
        }

    total = meminfo.get("MemTotal", 0)
    available = meminfo.get("MemAvailable", 0)
    used = max(total - available, 0)
    percent = round((used / total) * 100, 1) if total else 0
    return {
        "value": f"{percent}%",
        "meta": f"{_format_bytes(used * 1024)} / {_format_bytes(total * 1024)}",
        "level": percent,
        "tone": _usage_tone(percent),
    }


def _windows_memory_usage():
    if os.name != "nt":
        return None

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None

    used = status.ullTotalPhys - status.ullAvailPhys
    percent = round((used / status.ullTotalPhys) * 100, 1) if status.ullTotalPhys else 0
    return {
        "value": f"{percent}%",
        "meta": f"{_format_bytes(used)} / {_format_bytes(status.ullTotalPhys)}",
        "level": percent,
        "tone": _usage_tone(percent),
    }


def _read_linux_meminfo():
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            rows = {}
            for line in handle:
                key, value = line.split(":", 1)
                rows[key] = int(value.strip().split()[0])
            return rows
    except (FileNotFoundError, OSError, ValueError):
        return {}


def _usage_tone(percent):
    if percent >= 85:
        return "danger"
    if percent >= 70:
        return "warning"
    return "good"


def _format_bytes(value):
    value = float(value or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
