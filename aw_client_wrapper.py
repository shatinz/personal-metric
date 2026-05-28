from aw_client import ActivityWatchClient
from datetime import datetime, timedelta, timezone
import socket

def get_aw_client(start_date, end_date):
    """
    Fetch data from local ActivityWatch instance.
    start_date, end_date: datetime objects (timezone aware preferred)
    """
    client = ActivityWatchClient("personal-metric-aggregator", testing=False)
    
    # 1. Identify Buckets
    buckets = client.get_buckets()
    
    # We need:
    # - AFK bucket for computer (usually aw-watcher-afk_<hostname>)
    # - Window bucket for computer (usually aw-watcher-window_<hostname>)
    # - Android bucket (if exists) via sync? Usually aw-watcher-android...
    
    hostname = socket.gethostname()
    afk_bucket_id = f"aw-watcher-afk_{hostname}"
    window_bucket_id = f"aw-watcher-window_{hostname}"
    
    # Check if they exist
    if afk_bucket_id not in buckets:
        print(f"Warning: Bucket {afk_bucket_id} not found.")
        afk_bucket_id = None
        
    if window_bucket_id not in buckets:
        print(f"Warning: Bucket {window_bucket_id} not found.")
        window_bucket_id = None
        
    # Android bucket search
    # android_bucket_ids = [b for b in buckets if "android" in b and "aw-watcher" in b]
    
    return client, afk_bucket_id, window_bucket_id, []

def calculate_daily_active_time(client, bucket_id, start_dt, end_dt):
    """
    Query a bucket for events in range.
    Return total duration in seconds (filtering 'not-afk' for afk buckets).
    """
    if not bucket_id:
        return 0.0
        
    events = client.get_events(bucket_id, start=start_dt, end=end_dt)
    
    total_seconds = 0.0
    for event in events:
        if "status" in event.data:
            if event.data["status"] == "not-afk":
                total_seconds += event.duration.total_seconds()
        else:
            total_seconds += event.duration.total_seconds()
            
    return total_seconds

def get_top_apps(client, window_bucket_id, start_dt, end_dt, limit=5):
    """
    Get top applications used.
    """
    if not window_bucket_id:
        return {}
        
    events = client.get_events(window_bucket_id, start=start_dt, end=end_dt)
    
    app_usage = {}
    for event in events:
        app = event.data.get("app", "unknown")
        duration = event.duration.total_seconds()
        app_usage[app] = app_usage.get(app, 0) + duration
        
    # Sort and limit
    sorted_apps = sorted(app_usage.items(), key=lambda x: x[1], reverse=True)[:limit]
    return dict(sorted_apps)

if __name__ == "__main__":
    # Test run
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=1)
    
    c, afk, win, android = get_aw_client(start, now)
    print(f"Buckets: AFK={afk}, Win={win}")
    
    laptop_time = calculate_daily_active_time(c, afk, start, now)
    print(f"Laptop Active Time (24h): {laptop_time/3600:.2f} hours")
    
    apps = get_top_apps(c, win, start, now)
    print("Top Apps:", apps)
