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

load_dotenv()

client = OpenAI()

# Initialize session state
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

# Sidebar for navigation
st.sidebar.title("Navigation")
view = st.sidebar.radio(
    "Choose a view",
    ["Calendar View", "Add Event", "Chat Assistant"]
)

# Header
st.title("Exam Calendar Manager")

def get_calendars():
    calendars = list_calendar_list()
    return {cal['name']: cal['id'] for cal in calendars}

def format_event_time(event):
    start = event.get('start', {})
    if 'date' in start:  # All-day event
        return f"All day on {start['date']}"
    elif 'dateTime' in start:  # Timed event
        dt = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M")
    return "Time not specified"

# Calendar selection in sidebar
calendars = get_calendars()
selected_calendar_name = st.sidebar.selectbox(
    "Select Calendar",
    list(calendars.keys()),
    index=list(calendars.keys()).index("Exam Week") if "Exam Week" in calendars else 0
)
selected_calendar_id = calendars[selected_calendar_name]

def format_events_for_calendar(events):
    """Format events for the calendar component"""
    formatted_events = []
    for event in events:
        start = event.get('start', {})
        end = event.get('end', {})
        
        # Handle all-day events
        if 'date' in start:
            start_str = start['date']
            end_str = end.get('date', start['date'])
            all_day = True
        else:
            start_str = start.get('dateTime', '')
            end_str = end.get('dateTime', start_str)
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
    # Get events
    events = list_calendar_events(selected_calendar_id)
    formatted_events = format_events_for_calendar(events)
    
    # Calendar options
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
    
    # Create calendar
    state = calendar(events=formatted_events, options=calendar_options, key="calendar")
    
    # Handle calendar interactions
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

def process_message(message):
    """Process chat messages and handle calendar-related commands"""
    message_lower = message.lower()
    
    if "show calendar" in message_lower:
        st.session_state.show_calendar = True
        return "Here's your calendar view! You can interact with events and use different views."
    
    elif "hide calendar" in message_lower:
        st.session_state.show_calendar = False
        return "I've hidden the calendar view. Let me know if you need anything else!"
    
    elif "list events" in message_lower:
        events = list_calendar_events(selected_calendar_id)
        if not events:
            return "You don't have any upcoming events."
        
        response = "Here are your upcoming events:\n\n"
        for event in events:
            start = event.get('start', {})
            if 'date' in start:
                date_str = start['date']
            else:
                date_str = start.get('dateTime', 'No date specified')
            response += f"- {event['summary']} on {date_str}\n"
        return response
    
    else:
        return "I'm here to help you manage your calendar! You can:\n- Say 'show calendar' to see your calendar\n- Say 'hide calendar' to hide it\n- Say 'list events' to see upcoming events\n- Ask me to create or delete events"

if view == "Calendar View":
    st.header("📅 Calendar View")
    
    # Date range selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", datetime.now())
    with col2:
        end_date = st.date_input("End Date", datetime.now() + timedelta(days=30))
    
    # Display events
    events = list_calendar_events(selected_calendar_id)
    if events:
        st.subheader("Upcoming Events")
        for event in events:
            with st.expander(f"{event['summary']} - {format_event_time(event)}"):
                st.write(f"Description: {event.get('description', 'No description')}")
                if st.button(f"Delete {event['summary']}", key=event['id']):
                    delete_calendar_event(selected_calendar_id, event['id'])
                    st.success("Event deleted! Please refresh the page.")

elif view == "Add Event":
    st.header("➕ Add New Event")
    
    # Event form
    with st.form("event_form"):
        event_name = st.text_input("Event Name")
        event_description = st.text_area("Description")
        
        col1, col2 = st.columns(2)
        with col1:
            event_date = st.date_input("Date", datetime.now())
        with col2:
            is_all_day = st.checkbox("All Day Event", value=True)
        
        if not is_all_day:
            event_time = st.time_input("Time", datetime.now().time())
        
        # Additional features
        location = st.text_input("Location (Optional)")
        reminder = st.selectbox(
            "Set Reminder",
            ["None", "10 minutes before", "30 minutes before", "1 hour before", "1 day before"]
        )
        
        if st.form_submit_button("Add Event"):
            event_details = {
                'summary': event_name,
                'description': event_description,
                'location': location if location else None
            }
            
            if is_all_day:
                event_details['start'] = {'date': event_date.strftime('%Y-%m-%d')}
                event_details['end'] = {'date': event_date.strftime('%Y-%m-%d')}
            else:
                dt = datetime.combine(event_date, event_time)
                dt_str = dt.strftime('%Y-%m-%dT%H:%M:%S')
                event_details['start'] = {
                    'dateTime': dt_str,
                    'timeZone': 'Asia/Jakarta'
                }
                event_details['end'] = {
                    'dateTime': (dt + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S'),
                    'timeZone': 'Asia/Jakarta'
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
            except Exception as e:
                st.error(f"Error adding event: {str(e)}")

else:  # Chat Assistant
    st.header("💬 Chat Assistant")
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
        
        # Show calendar if requested
        if message["role"] == "assistant" and st.session_state.show_calendar:
            show_calendar_view()

    # Accept user input
    if prompt := st.chat_input("How can I help you with your calendar?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Process message and add assistant response
        response = process_message(prompt)
        with st.chat_message("assistant"):
            st.markdown(response)
            if st.session_state.show_calendar:
                show_calendar_view()
        st.session_state.messages.append({"role": "assistant", "content": response})

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("### Tips")
st.sidebar.markdown("""
- Use the Calendar View to see all your events
- Add new events with specific times and reminders
- Chat with the assistant for natural language support
""")
