"""
CityOS City Intelligence & Analytics Engine
--------------------------------------------
Provides municipal intelligence computations, spatial hotspot clustering,
resolution time analytics, deterministic smart insights, and heatmap data.
Operates completely offline without external AI APIs.
"""

import math
from datetime import datetime
import database

# Supported municipal categories
CATEGORIES = [
    "Road",
    "Water",
    "Waste",
    "Electricity",
    "Traffic",
    "Public Safety",
    "Other",
]

# Priority weights for heatmap intensity
PRIORITY_WEIGHTS = {
    "HIGH": 1.0,
    "MEDIUM": 0.6,
    "LOW": 0.3,
}


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculates the great-circle distance between two points on the Earth
    in kilometers using the Haversine formula.
    """
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return float("inf")

    # Earth radius in kilometers
    r = 6371.0

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def _apply_filters_to_query(base_query, params, filters):
    """Helper to apply category, priority, status, and date filters to SQL query."""
    if not filters:
        return base_query, params

    cat = filters.get("category", "All")
    prio = filters.get("priority", "All")
    status = filters.get("status", "All")
    days = filters.get("days", "All")

    if cat and cat != "All":
        base_query += " AND category = ?"
        params.append(cat)

    if prio and prio != "All":
        base_query += " AND UPPER(priority) = ?"
        params.append(prio.upper())

    if status and status != "All":
        if status == "Submitted":
            base_query += " AND status = 'Reported'"
        else:
            base_query += " AND status = ?"
            params.append(status)

    if days and str(days).isdigit() and int(days) > 0:
        # Filter for recent days
        base_query += " AND datetime(created_at) >= datetime('now', '-' || ? || ' days')"
        params.append(int(days))

    return base_query, params


def compute_city_statistics(db, filters=None):
    """
    Computes system-wide municipal KPIs:
    - Total Reports
    - Open/Pending Reports (Reported + Under Review)
    - In Progress Reports
    - Resolved Reports
    - Rejected Reports
    - High-Priority Reports
    - Reports with valid Geographic Coordinates
    """
    query = "SELECT * FROM reports WHERE 1=1"
    params = []
    query, params = _apply_filters_to_query(query, params, filters)

    rows = db.execute(query, params).fetchall()

    total = len(rows)
    reported = 0
    under_review = 0
    in_progress = 0
    resolved = 0
    rejected = 0
    high_priority = 0
    with_location = 0

    for r in rows:
        st = r["status"]
        if st == "Reported":
            reported += 1
        elif st == "Under Review":
            under_review += 1
        elif st == "In Progress":
            in_progress += 1
        elif st == "Resolved":
            resolved += 1
        elif st == "Rejected":
            rejected += 1

        prio = (r["priority"] or "").upper()
        if prio == "HIGH":
            high_priority += 1

        if r["latitude"] is not None and r["longitude"] is not None:
            with_location += 1

    open_reports = reported + under_review

    return {
        "total": total,
        "open": open_reports,
        "reported": reported,
        "under_review": under_review,
        "in_progress": in_progress,
        "resolved": resolved,
        "rejected": rejected,
        "high_priority": high_priority,
        "with_location": with_location,
        "resolution_rate": round((resolved / total * 100), 1) if total > 0 else 0.0,
    }


def compute_category_analytics(db, filters=None):
    """
    Computes count distribution by complaint category.
    Returns: {"labels": [...], "data": [...], "breakdown": [{"category": ..., "count": ..., "percentage": ...}]}
    """
    query = "SELECT category, COUNT(*) as count FROM reports WHERE 1=1"
    params = []
    query, params = _apply_filters_to_query(query, params, filters)
    query += " GROUP BY category ORDER BY count DESC"

    rows = db.execute(query, params).fetchall()
    counts = {r["category"]: r["count"] for r in rows}

    total = sum(counts.values()) if counts else 0
    breakdown = []
    labels = []
    data = []

    # Format for supported categories first, then any extra categories
    all_cats = list(dict.fromkeys(CATEGORIES + list(counts.keys())))

    for cat in all_cats:
        c = counts.get(cat, 0)
        pct = round((c / total * 100), 1) if total > 0 else 0.0
        labels.append(cat)
        data.append(c)
        breakdown.append({
            "category": cat,
            "count": c,
            "percentage": pct,
        })

    return {
        "labels": labels,
        "data": data,
        "breakdown": breakdown,
        "total": total,
    }


def compute_priority_analytics(db, filters=None):
    """
    Computes count distribution across HIGH, MEDIUM, LOW priorities.
    """
    query = "SELECT UPPER(COALESCE(priority, 'MEDIUM')) as prio, COUNT(*) as count FROM reports WHERE 1=1"
    params = []
    query, params = _apply_filters_to_query(query, params, filters)
    query += " GROUP BY UPPER(COALESCE(priority, 'MEDIUM'))"

    rows = db.execute(query, params).fetchall()
    counts = {r["prio"]: r["count"] for r in rows}

    high = counts.get("HIGH", 0)
    medium = counts.get("MEDIUM", 0)
    low = counts.get("LOW", 0)
    total = high + medium + low

    return {
        "labels": ["High", "Medium", "Low"],
        "data": [high, medium, low],
        "high": high,
        "medium": medium,
        "low": low,
        "total": total,
    }


def compute_status_analytics(db, filters=None):
    """
    Computes count distribution across operational lifecycle statuses.
    """
    query = "SELECT status, COUNT(*) as count FROM reports WHERE 1=1"
    params = []
    query, params = _apply_filters_to_query(query, params, filters)
    query += " GROUP BY status"

    rows = db.execute(query, params).fetchall()
    counts = {r["status"]: r["count"] for r in rows}

    reported = counts.get("Reported", 0)
    under_review = counts.get("Under Review", 0)
    in_progress = counts.get("In Progress", 0)
    resolved = counts.get("Resolved", 0)
    rejected = counts.get("Rejected", 0)

    return {
        "labels": ["Submitted", "Under Review", "In Progress", "Resolved", "Rejected"],
        "data": [reported, under_review, in_progress, resolved, rejected],
        "reported": reported,
        "under_review": under_review,
        "in_progress": in_progress,
        "resolved": resolved,
        "rejected": rejected,
        "total": sum(counts.values()),
    }


def detect_problem_hotspots(db, filters=None, distance_threshold_km=0.5):
    """
    Groups geo-located reports within distance_threshold_km (~500m) into clusters.
    Returns ranked problem hotspots with metrics.
    """
    query = """
        SELECT id, category, title, description, location, location_description,
               latitude, longitude, status, issue_type, priority, created_at
        FROM reports
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """
    params = []
    query, params = _apply_filters_to_query(query, params, filters)
    query += " ORDER BY datetime(created_at) DESC"

    rows = db.execute(query, params).fetchall()
    reports = [dict(r) for r in rows]

    if not reports:
        return []

    clusters = []
    visited = set()

    for i, rep in enumerate(reports):
        if rep["id"] in visited:
            continue

        cluster = [rep]
        visited.add(rep["id"])

        for j in range(i + 1, len(reports)):
            other = reports[j]
            if other["id"] in visited:
                continue

            dist = haversine_distance(
                rep["latitude"], rep["longitude"],
                other["latitude"], other["longitude"]
            )
            if dist <= distance_threshold_km:
                cluster.append(other)
                visited.add(other["id"])

        # Determine hotspot attributes
        if len(cluster) >= 1:
            avg_lat = sum(r["latitude"] for r in cluster) / len(cluster)
            avg_lon = sum(r["longitude"] for r in cluster) / len(cluster)

            cats = [r["category"] for r in cluster]
            top_category = max(set(cats), key=cats.count)

            issue_types = [r["issue_type"] or "General Issue" for r in cluster]
            top_issue = max(set(issue_types), key=issue_types.count)

            prios = [(r["priority"] or "MEDIUM").upper() for r in cluster]
            highest_priority = "HIGH" if "HIGH" in prios else ("MEDIUM" if "MEDIUM" in prios else "LOW")

            # Status breakdown
            st_counts = {}
            for r in cluster:
                st_counts[r["status"]] = st_counts.get(r["status"], 0) + 1
            st_summary = ", ".join(f"{c} {s}" for s, c in st_counts.items())

            # Best location name
            loc_name = cluster[0]["location"]
            if cluster[0]["location_description"]:
                loc_name += f" ({cluster[0]['location_description']})"

            clusters.append({
                "id": f"HS-{len(clusters) + 1:03d}",
                "count": len(cluster),
                "center_lat": round(avg_lat, 6),
                "center_lon": round(avg_lon, 6),
                "location_name": loc_name,
                "top_category": top_category,
                "top_issue_type": top_issue,
                "highest_priority": highest_priority,
                "status_summary": st_summary,
                "report_ids": [r["id"] for r in cluster],
                "is_multi": len(cluster) >= 2,
            })

    # Sort hotspots by volume of complaints descending
    clusters.sort(key=lambda x: (x["count"], x["highest_priority"] == "HIGH"), reverse=True)
    return clusters


def get_top_problem_areas(db, limit=5):
    """
    Ranks top problem areas by report concentration.
    """
    hotspots = detect_problem_hotspots(db)
    top_areas = []

    for idx, hs in enumerate(hotspots[:limit], start=1):
        top_areas.append({
            "rank": idx,
            "area_name": hs["location_name"],
            "count": hs["count"],
            "category": hs["top_category"],
            "issue_type": hs["top_issue_type"],
            "priority": hs["highest_priority"],
            "lat": hs["center_lat"],
            "lon": hs["center_lon"],
        })

    return top_areas


def compute_resolution_analytics(db):
    """
    Calculates municipal resolution metrics:
    - Total resolved vs unresolved reports
    - Average turnaround time (hours & days)
    - Average resolution time per category
    """
    total_row = db.execute("SELECT COUNT(*) as count FROM reports").fetchone()
    total = total_row["count"] if total_row else 0

    resolved_rows = db.execute(
        """
        SELECT id, category, created_at, updated_at
        FROM reports
        WHERE status = 'Resolved'
        """
    ).fetchall()

    resolved_count = len(resolved_rows)
    unresolved_count = total - resolved_count

    durations_hours = []
    category_durations = {}

    for r in resolved_rows:
        try:
            created = datetime.fromisoformat(r["created_at"])
            updated = datetime.fromisoformat(r["updated_at"])
            hours = (updated - created).total_seconds() / 3600.0
            # Floor to minimum 0.05 hours for immediate test updates
            hours = max(hours, 0.05)
            durations_hours.append(hours)

            cat = r["category"]
            if cat not in category_durations:
                category_durations[cat] = []
            category_durations[cat].append(hours)
        except Exception:
            continue

    avg_hours = sum(durations_hours) / len(durations_hours) if durations_hours else 0.0
    avg_days = avg_hours / 24.0

    category_avg = {}
    for cat, times in category_durations.items():
        category_avg[cat] = {
            "avg_hours": round(sum(times) / len(times), 1),
            "avg_days": round((sum(times) / len(times)) / 24.0, 1),
            "resolved_count": len(times),
        }

    return {
        "total_reports": total,
        "resolved_reports": resolved_count,
        "unresolved_reports": unresolved_count,
        "avg_resolution_hours": round(avg_hours, 1),
        "avg_resolution_days": round(avg_days, 1),
        "formatted_avg_time": f"{round(avg_hours, 1)} hrs" if avg_hours < 48 else f"{round(avg_days, 1)} days",
        "category_performance": category_avg,
    }


def generate_smart_insights(db, stats=None, hotspots=None, cat_analytics=None):
    """
    Generates rule-based, deterministic, explainable Smart City Insights
    from current report distributions and geographic concentration.
    No external AI APIs.
    """
    if stats is None:
        stats = compute_city_statistics(db)
    if hotspots is None:
        hotspots = detect_problem_hotspots(db)
    if cat_analytics is None:
        cat_analytics = compute_category_analytics(db)

    insights = []

    # 1. Category Dominance Insight
    if cat_analytics and cat_analytics["breakdown"]:
        top_cat = max(cat_analytics["breakdown"], key=lambda x: x["count"])
        if top_cat["count"] > 0:
            insights.append({
                "type": "category",
                "badge": "Dominant Sector",
                "badge_class": "badge-priority-medium",
                "icon": "📊",
                "title": f"{top_cat['category']} represents the highest volume of citizen complaints",
                "message": f"{top_cat['category']} issues comprise {top_cat['percentage']}% ({top_cat['count']} reports) of total municipal filings. Recommended to allocate additional triage personnel.",
            })

    # 2. High-Priority Cluster Alert
    multi_hotspots = [h for h in hotspots if h["count"] >= 2]
    high_prio_hotspots = [h for h in multi_hotspots if h["highest_priority"] == "HIGH"]

    if high_prio_hotspots:
        top_hp = high_prio_hotspots[0]
        insights.append({
            "type": "hazard",
            "badge": "Priority Hotspot Alert",
            "badge_class": "badge-priority-high",
            "icon": "⚠️",
            "title": f"High-priority cluster concentrated near {top_hp['location_name']}",
            "message": f"Detected {top_hp['count']} complaints in close proximity with critical priority. Primary issue: {top_hp['top_issue_type']} ({top_hp['top_category']}). Immediate field inspection advised.",
        })
    elif stats["high_priority"] > 0:
        insights.append({
            "type": "hazard",
            "badge": "Urgent Triage",
            "badge_class": "badge-priority-high",
            "icon": "🚨",
            "title": f"{stats['high_priority']} High-Priority incidents require immediate municipal review",
            "message": "Urgent complaints flagged with safety/hazard keywords are pending dispatch. Review the priority queue in the administration console.",
        })

    # 3. Resolution Efficiency Insight
    res_analytics = compute_resolution_analytics(db)
    if res_analytics["resolved_reports"] > 0:
        rate = stats.get("resolution_rate", 0)
        insights.append({
            "type": "efficiency",
            "badge": "Operational Performance",
            "badge_class": "badge-priority-low",
            "icon": "⏱️",
            "title": f"Municipal resolution turnaround averages {res_analytics['formatted_avg_time']}",
            "message": f"{res_analytics['resolved_reports']} reports resolved ({rate}% overall completion). Operations are maintaining steady resolution velocity.",
        })

    # 4. Spatial Density Insight
    if len(multi_hotspots) >= 2:
        insights.append({
            "type": "hotspot",
            "badge": "Geospatial Clustering",
            "badge_class": "badge-priority-medium",
            "icon": "🗺️",
            "title": f"{len(multi_hotspots)} distinct problem hotspots identified across the city",
            "message": "Concentrated complaint zones detected. Consult the City Problem Heatmap for spatial triage.",
        })

    # Fallback if no specific insight matched
    if not insights:
        insights.append({
            "type": "general",
            "badge": "City Health",
            "badge_class": "badge-priority-low",
            "icon": "✨",
            "title": "Municipal complaint volume is normal",
            "message": "All municipal sectors are operating within standard parameters.",
        })

    return insights


def get_heatmap_points(db, filters=None):
    """
    Returns array of coordinates with intensity weights:
    [[lat, lon, intensity], ...]
    """
    query = """
        SELECT latitude, longitude, priority
        FROM reports
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """
    params = []
    query, params = _apply_filters_to_query(query, params, filters)

    rows = db.execute(query, params).fetchall()

    points = []
    for r in rows:
        lat = float(r["latitude"])
        lon = float(r["longitude"])
        prio = (r["priority"] or "MEDIUM").upper()
        weight = PRIORITY_WEIGHTS.get(prio, 0.6)
        points.append([lat, lon, weight])

    return points
