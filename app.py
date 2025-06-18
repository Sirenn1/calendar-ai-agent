from openai import OpenAI
from dotenv import load_dotenv
import streamlit as st
from swarm import Swarm
from agents import main_agent
from datetime import datetime, timedelta
import pytz
from calendar_tools import (
    list_calendar_list, 
    list_calendar_events, 
    insert_calendar_event, 
    create_calendar_list,
    delete_calendar_event
)
from streamlit_calendar import calendar
import pandas as pd
import json
import os

load_dotenv()

client = OpenAI()
swarm_client = Swarm()

if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'selected_calendar' not in st.session_state:
    st.session_state.selected_calendar = None
if 'current_view' not in st.session_state:
    st.session_state.current_view = 'calendar'
if 'show_calendar' not in st.session_state:
    st.session_state.show_calendar = False
if 'calendar_events' not in st.session_state:
    st.session_state.calendar_events = []
if 'search_query' not in st.session_state:
    st.session_state.search_query = ""

os.environ['TZ'] = 'Asia/Jakarta'

st.sidebar.title("Navigation")
view = st.sidebar.radio(
    "Choose a view",
    ["Calendar View", "Add Event", "Chat Assistant", "Statistics", "Export"]
)

st.title("📅 Google Calendar Manager")

EVENT_CATEGORIES = {
    "Meeting": "#4285F4",   
    "Task": "#EA4335",    
    "Event": "#FBBC05",    
    "Reminder": "#34A853", 
    "Personal": "#9C27B0",  
    "Work": "#FF9800",      
    "Study": "#795548",     
    "Other": "#607D8B"    
}

def get_user_timezone():
    try:
        user_tz = os.environ.get('TZ', 'Asia/Jakarta')
        pytz.timezone(user_tz)
        return user_tz
    except:
        return 'Asia/Jakarta'

def get_calendars():
    calendars = list_calendar_list()
    return {cal['name']: cal['id'] for cal in calendars}

def format_event_time(event):
    try:
        user_tz = pytz.timezone(get_user_timezone())
        if 'dateTime' in event['start']:
            start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
            start_time = start_time.astimezone(user_tz)
            date_str = start_time.strftime('%b %d, %Y')
            if 'dateTime' in event['end']:
                end_time = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                end_time = end_time.astimezone(user_tz)
                return f"{date_str} | {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')} {start_time.strftime('%Z')}"
            return f"{date_str} | {start_time.strftime('%I:%M %p')} {start_time.strftime('%Z')}"
        else:
            # For all-day events, get the date from start.date
            if 'date' in event['start']:
                date_obj = datetime.strptime(event['start']['date'], '%Y-%m-%d')
                return f"{date_obj.strftime('%b %d, %Y')} | All Day"
            return "All Day"
    except Exception as e:
        return "Time not available"

calendars = get_calendars()
print("Available calendars:", calendars)  
selected_calendar_name = st.sidebar.selectbox(
    "Select Calendar",
    list(calendars.keys()),
    index=list(calendars.keys()).index("Exam Week") if "Exam Week" in calendars else 0
)
selected_calendar_id = calendars[selected_calendar_name]

user_tz = get_user_timezone()
tz_obj = pytz.timezone(user_tz)
utc_offset = tz_obj.utcoffset(datetime.now()).total_seconds() / 3600  
offset_str = f"UTC{'+' if utc_offset >= 0 else ''}{int(utc_offset)}"
st.sidebar.info(f"Timezone: {user_tz} ({offset_str})")

def format_events_for_calendar(events):
    """Format events for the calendar component"""
    jakarta_tz = pytz.timezone('Asia/Jakarta')
    formatted_events = []
    for event in events:
        start = event.get('start', {})
        end = event.get('end', {})
        
        if 'date' in start:
            start_str = start['date']
            end_str = end.get('date', start['date'])
            all_day = True
        else:
            start_dt = datetime.fromisoformat(start.get('dateTime', '').replace('Z', '+00:00'))
            end_dt = datetime.fromisoformat(end.get('dateTime', start.get('dateTime', '')).replace('Z', '+00:00'))
            start_dt = start_dt.astimezone(jakarta_tz)
            end_dt = end_dt.astimezone(jakarta_tz)
            start_str = start_dt.isoformat()
            end_str = end_dt.isoformat()
            all_day = False
            
        formatted_events.append({
            'id': event['id'],
            'title': event['summary'],
            'start': start_str,
            'end': end_str,
            'allDay': all_day,
            'description': event.get('description', ''),
            'backgroundColor': '#1976D2' if 'exam' in event['summary'].lower() else '#43A047'
        })
    
    return formatted_events

def show_calendar_view():
    """Display the calendar component"""
    events = list_calendar_events(selected_calendar_id)
    formatted_events = format_events_for_calendar(events)
    
    calendar_options = {
        "headerToolbar": {
            "left": "today prev,next",
            "center": "title",
            "right": "dayGridMonth,timeGridWeek,timeGridDay"
        },
        "initialView": "dayGridMonth",
        "selectable": True,
        "editable": False,
        "navLinks": True,
        "dayMaxEvents": True,
        "events": formatted_events,
    }
    
    state = calendar(events=formatted_events, options=calendar_options, key="calendar")
    
    if state.get("eventClick"):
        event_id = state["eventClick"]["event"]["id"]
        event = next((e for e in events if e['id'] == event_id), None)
        if event:
            st.sidebar.subheader("Event Details")
            st.sidebar.write(f"**{event['summary']}**")
            st.sidebar.write(event.get('description', 'No description'))
            if st.sidebar.button("Delete Event"):
                delete_calendar_event(selected_calendar_id, event_id)
                st.rerun()

def process_message_with_agent(user_message):
    """Process chat messages using the Swarm AI agent."""
    history = []
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            history.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            history.append({"role": "assistant", "content": msg["content"]})
    history.append({"role": "user", "content": user_message})
    response = swarm_client.run(agent=main_agent, messages=history)
    ai_message = None
    for msg in response.messages[::-1]:
        if msg.get("role") == "assistant":
            ai_message = msg.get("content")
            break
    return ai_message or "(No response from agent)"

def get_event_statistics(events):
    """Calculate statistics about events"""
    stats = {
        "total_events": len(events),
        "by_category": {},
        "upcoming_events": 0,
        "all_day_events": 0,
        "events_by_day": {},
        "busiest_day": None,
        "busiest_day_count": 0,
        "events_by_time": {
            "morning": 0, 
            "afternoon": 0,   
            "evening": 0,     
            "night": 0    
        }
    }
    
    current_time = datetime.now(pytz.timezone('Asia/Jakarta'))
    
    for event in events:
        category = event.get('summary', 'Other').split()[0]
        if category in EVENT_CATEGORIES:
            stats['by_category'][category] = stats['by_category'].get(category, 0) + 1
        else:
            stats['by_category']['Other'] = stats['by_category'].get('Other', 0) + 1
        
        start = event.get('start', {})
        if 'dateTime' in start:
            event_time = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
            event_time = event_time.astimezone(pytz.timezone('Asia/Jakarta'))
            
            hour = event_time.hour
            if 6 <= hour < 12:
                stats['events_by_time']['morning'] += 1
            elif 12 <= hour < 18:
                stats['events_by_time']['afternoon'] += 1
            elif 18 <= hour < 24:
                stats['events_by_time']['evening'] += 1
            else:
                stats['events_by_time']['night'] += 1
            
            if event_time > current_time:
                stats['upcoming_events'] += 1
        elif 'date' in start:
            event_date = datetime.strptime(start['date'], '%Y-%m-%d').date()
            if event_date >= current_time.date():
                stats['upcoming_events'] += 1
                stats['all_day_events'] += 1
        
        if 'date' in start:
            date = start['date']
        elif 'dateTime' in start:
            date = start['dateTime'].split('T')[0]
        else:
            continue
            
        stats['events_by_day'][date] = stats['events_by_day'].get(date, 0) + 1
        
        if stats['events_by_day'][date] > stats['busiest_day_count']:
            stats['busiest_day'] = date
            stats['busiest_day_count'] = stats['events_by_day'][date]
    
    return stats

def export_calendar_to_csv(events):
    """Export calendar events to CSV format"""
    import csv
    from io import StringIO
    
    output = StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Title', 'Start Date', 'End Date', 'Category', 'Description', 'Location'])
    
    for event in events:
        start = event.get('start', {})
        end = event.get('end', {})
        
        start_str = start.get('dateTime', start.get('date', ''))
        end_str = end.get('dateTime', end.get('date', ''))
        
        writer.writerow([
            event.get('summary', 'Untitled'),
            start_str,
            end_str,
            event.get('category', 'Other'),
            event.get('description', ''),
            event.get('location', '')
        ])
    
    return output.getvalue()

if view == "Calendar View":
    st.header("📅 Calendar View")
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.now(pytz.timezone(user_tz)).date())
    with col2:
        end_date = st.date_input("End Date", start_date + timedelta(days=7))
    
    events = list_calendar_events(selected_calendar_id)
    
    filtered_events = []
    for event in events:
        try:
            if 'dateTime' in event['start']:
                event_date = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                event_date = event_date.astimezone(pytz.timezone(user_tz))
                if start_date <= event_date.date() <= end_date:
                    filtered_events.append(event)
            else:
                event_date = datetime.fromisoformat(event['start']['date']).date()
                if start_date <= event_date <= end_date:
                    filtered_events.append(event)
        except Exception as e:
            continue
    
    if filtered_events:
        for event in filtered_events:
            with st.expander(f"{event.get('summary', 'Untitled Event')} - {format_event_time(event)}"):
                st.write(f"Description: {event.get('description', 'No description')}")
                st.write(f"Category: {event.get('category', 'Other')}")
                if st.button(f"Delete {event.get('summary', 'Untitled Event')}", key=event['id']):
                    delete_calendar_event(selected_calendar_id, event['id'])
                    st.success("Event deleted! Please refresh the page.")
    else:
        st.info("No events found in the selected date range.")

elif view == "Add Event":
    st.header("➕ Add New Event")
    
    with st.form("event_form"):
        event_name = st.text_input("Event Name")
        event_description = st.text_area("Description")
        
        default_category = "Other"
        if event_name:
            event_name_lower = event_name.lower()
            if any(word in event_name_lower for word in ["meeting", "call", "discussion"]):
                default_category = "Meeting"
            elif any(word in event_name_lower for word in ["task", "todo", "assignment"]):
                default_category = "Task"
            elif any(word in event_name_lower for word in ["party", "celebration", "gathering"]):
                default_category = "Event"
            elif any(word in event_name_lower for word in ["reminder", "deadline", "due"]):
                default_category = "Reminder"
            elif any(word in event_name_lower for word in ["personal", "family", "hobby"]):
                default_category = "Personal"
            elif any(word in event_name_lower for word in ["work", "project", "business"]):
                default_category = "Work"
            elif any(word in event_name_lower for word in ["study", "exam", "class"]):
                default_category = "Study"
        
        event_category = st.selectbox(
            "Category (Optional)",
            list(EVENT_CATEGORIES.keys()),
            index=list(EVENT_CATEGORIES.keys()).index(default_category)
        )
        
        col1, col2 = st.columns(2)
        with col1:
            current_time = datetime.now(pytz.timezone(user_tz))
            event_date = st.date_input("Date", current_time.date())
        with col2:
            is_all_day = st.checkbox("All Day Event", value=True)
        
        if not is_all_day:
            event_time = st.time_input("Time", current_time.time())
        
        location = st.text_input("Location (Optional)")
        reminder = st.selectbox(
            "Set Reminder",
            ["None", "10 minutes before", "30 minutes before", "1 hour before", "1 day before"]
        )
        
        if st.form_submit_button("Add Event"):
            event_details = {
                'summary': event_name,
                'description': event_description,
                'location': location if location else None,
                'category': event_category
            }
            
            if is_all_day:
                event_details['start'] = {'date': event_date.strftime('%Y-%m-%d')}
                event_details['end'] = {'date': event_date.strftime('%Y-%m-%d')}
            else:
                dt = datetime.combine(event_date, event_time)
                dt = pytz.timezone(user_tz).localize(dt)
                dt_str = dt.isoformat()
                event_details['start'] = {
                    'dateTime': dt_str,
                    'timeZone': user_tz
                }
                event_details['end'] = {
                    'dateTime': (dt + timedelta(hours=1)).isoformat(),
                    'timeZone': user_tz
                }
            
            if reminder != "None":
                event_details['reminders'] = {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': {
                            "10 minutes before": 10,
                            "30 minutes before": 30,
                            "1 hour before": 60,
                            "1 day before": 1440
                        }[reminder]}
                    ]
                }
            
            try:
                insert_calendar_event(selected_calendar_id, kwargs=event_details)
                st.success("Event added successfully!")
                st.rerun()
            except Exception as e:
                st.error(f"Error adding event: {str(e)}")

elif view == "Chat Assistant":
    st.header("💬 Chat Assistant")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    if prompt := st.chat_input("Ask me about your calendar..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            response = process_message_with_agent(prompt)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

elif view == "Statistics":
    st.header("📊 Calendar Statistics")
    events = list_calendar_events(selected_calendar_id)
    stats = get_event_statistics(events)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Events", stats["total_events"])
        st.metric("Upcoming Events", stats["upcoming_events"])
    with col2:
        st.metric("All Day Events", stats["all_day_events"])
        if stats["busiest_day"]:
            st.metric("Busiest Day", f"{stats['busiest_day']} ({stats['busiest_day_count']} events)")
    
    st.subheader("Events by Category")
    if stats['by_category']:
        category_data = pd.DataFrame({
            'Category': list(stats['by_category'].keys()),
            'Count': list(stats['by_category'].values())
        })
        st.bar_chart(category_data.set_index('Category'))
    else:
        st.info("No events categorized yet.")
    
    st.subheader("Events by Time of Day")
    time_data = pd.DataFrame({
        'Time of Day': list(stats['events_by_time'].keys()),
        'Count': list(stats['events_by_time'].values())
    })
    st.bar_chart(time_data.set_index('Time of Day'))
    
    st.subheader("Events by Day")
    if stats['events_by_day']:
        day_data = pd.DataFrame({
            'Date': list(stats['events_by_day'].keys()),
            'Count': list(stats['events_by_day'].values())
        })
        day_data['Date'] = pd.to_datetime(day_data['Date'])
        day_data = day_data.sort_values('Date')
        st.line_chart(day_data.set_index('Date'))
    else:
        st.info("No events scheduled yet.")

elif view == "Export":
    st.header("📤 Export Calendar")
    events = list_calendar_events(selected_calendar_id)
    
    if events:
        export_format = st.radio(
            "Select Export Format",
            ["CSV", "JSON"],
            horizontal=True
        )
        
        if export_format == "CSV":
            csv_data = export_calendar_to_csv(events)
            st.download_button(
                label="Download Calendar as CSV",
                data=csv_data,
                file_name="calendar_export.csv",
                mime="text/csv"
            )
        else:   
            formatted_events = []
            for event in events:
                formatted_event = {
                    'title': event.get('summary', ''),
                    'description': event.get('description', ''),
                    'location': event.get('location', ''),
                    'start': event.get('start', {}),
                    'end': event.get('end', {}),
                    'category': event.get('summary', 'Other').split()[0] if event.get('summary') else 'Other'
                }
                formatted_events.append(formatted_event)
            
            json_data = json.dumps(formatted_events, indent=2)
            st.download_button(
                label="Download Calendar as JSON",
                data=json_data,
                file_name="calendar_export.json",
                mime="application/json"
            )
            
            with st.expander("Preview JSON Data"):
                st.json(formatted_events)
    else:
        st.info("No events to export.")

st.sidebar.markdown("---")
st.sidebar.markdown("### Tips")
st.sidebar.markdown("""
- Use the Calendar View to see all your events
- Add new events with specific times and reminders
- Use categories to organize your events
- Export your calendar for backup
- Check statistics to track your schedule
- Chat with the assistant for natural language support
""")