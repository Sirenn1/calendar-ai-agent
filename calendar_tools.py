import json
from google_apis import create_service

client_secret = 'client_secret.json'

def construct_google_calendar_client(client_secret):
    """
    Constructs a Google Calendar API client.

    Parameters:
    - client_secret (str): The path to the client secret JSON file.

    Returns:
    - service: The Google Calendar API service instance.
    """
    API_NAME = 'calendar'
    API_VERSION = 'v3'
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    service = create_service(client_secret, API_NAME, API_VERSION, SCOPES)
    return service

calendar_service = construct_google_calendar_client(client_secret)

def check_calendar_exists(calendar_name):
    """
    Checks if a calendar with the given name already exists.

    Parameters:
    - calendar_name (str): The name of the calendar to check.

    Returns:
    - tuple: (bool, str) - (exists, calendar_id if exists else None)
    """
    calendars = list_calendar_list()
    for calendar in calendars:
        if calendar['name'].lower() == calendar_name.lower():
            return True, calendar['id']
    return False, None

def create_calendar_list(calendar_name):
    """
    Creates a new calendar list if it doesn't already exist.

    Parameters:
    - calendar_name (str): The name of the new calendar list.

    Returns:
    - dict: A dictionary containing the ID of the calendar list (either existing or new).
    """
    exists, calendar_id = check_calendar_exists(calendar_name)
    if exists:
        return {'id': calendar_id}
        
    calendar_list = {
        'summary': calendar_name
    }
    created_calendar_list = calendar_service.calendars().insert(body=calendar_list).execute()
    return created_calendar_list

def list_calendar_list(max_capacity=200):
    """
    Lists calendar lists until the total number of items reaches max_capacity.

    Parameters:
    - max_capacity (int or str, optional): The maximum number of calendar lists to retrieve. Defaults to 200.
      If a string is provided, it will be converted to an integer.

    Returns:
    - list: A list of dictionaries containing cleaned calendar list information with 'id', 'name', and 'description'.
    """
    if isinstance(max_capacity, str):
        max_capacity = int(max_capacity)

    all_calendars = []
    next_page_token = None
    capacity_tracker = 0

    while True:
        calendar_list = calendar_service.calendarList().list(
            maxResults=min(200, max_capacity - capacity_tracker),
            pageToken=next_page_token
        ).execute()
        calendars = calendar_list.get('items', [])
        capacity_tracker += len(calendars)
        
        # Clean and add calendars
        for calendar in calendars:
            all_calendars.append({
                'id': calendar['id'],
                'name': calendar['summary'],
                'description': calendar.get('description', '')
            })
            
        if capacity_tracker >= max_capacity:
            break
        next_page_token = calendar_list.get('nextPageToken')
        if not next_page_token:
            break
            
    return all_calendars

def list_calendar_events(calendar_id, max_capacity=20):
    """
    Lists events from a specified calendar until the total number of events reaches max_capacity.

    Parameters:
    - calendar_id (str): The ID of the calendar from which to list events.
    - max_capacity (int or str, optional): The maximum number of events to retrieve. Default is 20.
      If a string is provided, it will be converted to an integer.

    Returns:
    - list: A list of events from the specified calendar.
    """
    if isinstance(max_capacity, str):
        max_capacity = int(max_capacity)

    all_events = []
    next_page_token = None
    capacity_tracker = 0
    while True:
        events_list = calendar_service.events().list(
            calendarId=calendar_id,
            maxResults=min(250, max_capacity - capacity_tracker),
            pageToken=next_page_token
        ).execute()
        events = events_list.get('items', [])
        # Print event details for debugging
        for event in events:
            print(f"Found event: {event.get('summary')} on {event.get('start', {}).get('date')} (ID: {event.get('id')})")
        all_events.extend(events)
        capacity_tracker += len(events)
        if capacity_tracker >= max_capacity:
            break
        next_page_token = events_list.get('nextPageToken')
        if not next_page_token:
            break 
    return all_events


def insert_calendar_event(calendar_id, **kwargs):
    """
    Inserts an event into the specified calendar.

    Parameters:
    - calendar_id: The ID of the calendar where the event will be inserted.
    - **kwargs: Additional keyword arguments representing the event details.
    Returns:
    - The created event.
    """    
    # Handle both string JSON and dict input
    if isinstance(kwargs.get('kwargs'), str):
        try:
            request_body = json.loads(kwargs['kwargs'])
        except json.JSONDecodeError:
            # If JSON parsing fails, assume it's a direct event creation request
            request_body = kwargs['kwargs']
    else:
        request_body = kwargs['kwargs']
    
    # If no time is specified, create an all-day event
    if 'start' not in request_body or ('dateTime' not in request_body.get('start', {}) and 'date' not in request_body.get('start', {})):
        # Get the date from the event summary or use today's date
        import datetime
        import re
        
        # Try to extract date from summary
        date_match = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?([A-Za-z]+)(?:\s+(\d{4}))?', request_body['summary'])
        if date_match:
            day = int(date_match.group(1))
            month = date_match.group(2)
            # If year is specified in the summary, use it; otherwise use 2025 for exam events
            year = int(date_match.group(3)) if date_match.group(3) else 2025
            try:
                date_str = f"{year}-{datetime.datetime.strptime(month, '%B').month:02d}-{day:02d}"
                request_body['start'] = {'date': date_str}
                request_body['end'] = {'date': date_str}
                print(f"Creating event on {date_str}")  # Debug print to confirm the date
            except ValueError:
                # If date parsing fails, use today's date in 2025
                today = datetime.datetime.now().replace(year=2025).strftime('%Y-%m-%d')
                request_body['start'] = {'date': today}
                request_body['end'] = {'date': today}
                print(f"Using fallback date: {today}")  # Debug print for fallback
        else:
            # If no date found in summary, use today's date but in 2025
            today = datetime.datetime.now().replace(year=2025).strftime('%Y-%m-%d')
            request_body['start'] = {'date': today}
            request_body['end'] = {'date': today}
            print(f"No date found in summary, using: {today}")  # Debug print for no date case
    else:
        # If dateTime is present but no timeZone, default to Asia/Jakarta (UTC+7)
        if 'dateTime' in request_body['start'] and 'timeZone' not in request_body['start']:
            request_body['start']['timeZone'] = 'Asia/Jakarta'
        if 'dateTime' in request_body.get('end', {}) and 'timeZone' not in request_body['end']:
            request_body['end']['timeZone'] = 'Asia/Jakarta'

    event = calendar_service.events().insert(
        calendarId=calendar_id,
        body=request_body
    ).execute()
    return event

def delete_calendar_event(calendar_id, event_id):
    """
    Deletes an event from a calendar.

    Parameters:
    - calendar_id: The ID of the calendar containing the event
    - event_id: The ID of the event to delete
    """
    try:
        calendar_service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        print(f"Successfully deleted event {event_id}")
        return True
    except Exception as e:
        print(f"Error deleting event: {e}")
        return False

def list_calendars():
    calendars = calendar_service.calendarList().list().execute()
    for cal in calendars['items']:
        print(f"Calendar Name: {cal['summary']}, ID: {cal['id']}")
list_calendars()

def update_calendar_event(calendar_id, event_id, **kwargs):
    """
    Updates an existing calendar event.

    Parameters:
    - calendar_id: The ID of the calendar containing the event
    - event_id: The ID of the event to update
    - **kwargs: The updated event details
    """
    try:
        event = calendar_service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        # Update the event with new details
        for key, value in kwargs['kwargs'].items():
            event[key] = value
        updated_event = calendar_service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event
        ).execute()
        print(f"Successfully updated event {event_id}")
        return updated_event
    except Exception as e:
        print(f"Error updating event: {e}")
        return None

def get_calendar_busy_times(calendar_id, time_min, time_max):
    """
    Gets the busy time slots for a calendar within a specified time range

    Parameters:
    - calendar_id: The ID of the calendar to check
    - time_min: Start time in RFC3339 format
    - time_max: End time in RFC3339 format

    Returns:
    - list: List of busy time periods
    """
    try:
        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": calendar_id}]
        }
        response = calendar_service.freebusy().query(body=body).execute()
        busy_times = response['calendars'][calendar_id]['busy']
        return busy_times
    except Exception as e:
        print(f"Error getting busy times: {e}")
        return []

def create_recurring_event(calendar_id, **kwargs):
    """
    Creates a recurring event in the specified calendar.

    Parameters:
    - calendar_id: The ID of the calendar where the event will be created
    - **kwargs: Event details including recurrence rules
    
    Example recurrence rule:
    'recurrence': ['RRULE:FREQ=WEEKLY;COUNT=10']  # Repeats weekly for 10 weeks
    """
    try:
        event = calendar_service.events().insert(
            calendarId=calendar_id,
            body=kwargs['kwargs']
        ).execute()
        print(f"Created recurring event: {event.get('summary')}")
        return event
    except Exception as e:
        print(f"Error creating recurring event: {e}")
        return None

def suggest_study_slots(calendar_id, exam_date, hours_needed, days_before=7):
    """
    Suggests study time slots before an exam.

    Parameters:
    - calendar_id: The ID of the calendar to check
    - exam_date: The date of the exam in RFC3339 format
    - hours_needed: Total hours of study time needed
    - days_before: How many days before the exam to start studying

    Returns:
    - list: Suggested study time slots
    """
    from datetime import datetime, timedelta
    
    exam_dt = datetime.fromisoformat(exam_date.replace('Z', '+00:00'))
    start_dt = exam_dt - timedelta(days=days_before)
    
    # Get busy times
    busy_times = get_calendar_busy_times(
        calendar_id,
        start_dt.isoformat() + 'Z',
        exam_date
    )
    
    # Find free slots (simplified algorithm)
    suggested_slots = []
    current_dt = start_dt
    hours_scheduled = 0
    
    while current_dt < exam_dt and hours_scheduled < hours_needed:
        # Skip if current time is in a busy slot
        is_busy = any(
            current_dt.isoformat() + 'Z' >= slot['start'] and 
            current_dt.isoformat() + 'Z' < slot['end'] 
            for slot in busy_times
        )
        
        if not is_busy and current_dt.hour >= 9 and current_dt.hour <= 17:
            suggested_slots.append({
                'start': current_dt.isoformat() + 'Z',
                'end': (current_dt + timedelta(hours=2)).isoformat() + 'Z'
            })
            hours_scheduled += 2
        
        current_dt += timedelta(hours=1)
    
    return suggested_slots
