from calendar_tools import list_calendar_list, list_calendar_events, delete_calendar_event, insert_calendar_event

calendars = list_calendar_list()
exam_calendar_id = None
for calendar in calendars:
    if calendar['name'] == 'Exam Week':
        exam_calendar_id = calendar['id']
        break

if exam_calendar_id:
    print("\nFound Exam Week calendar")
    
    print("\nListing existing events:")
    events = list_calendar_events(exam_calendar_id)
    for event in events:
        print(f"Deleting event: {event.get('summary')} on {event.get('start', {}).get('date')}")
        delete_calendar_event(exam_calendar_id, event['id'])
    
    print("\nCreating new events for 2025:")
    
    software_exam = {
        'summary': 'Software Engineering Exam',
        'description': 'Final examination for Software Engineering course',
        'start': {'date': '2025-06-09'},
        'end': {'date': '2025-06-09'}
    }
    
    biology_exam = {
        'summary': 'Computational Biology Exam',
        'description': 'Final examination for Computational Biology course',
        'start': {'date': '2025-06-10'},
        'end': {'date': '2025-06-10'}
    }
    
    print("Adding Software Engineering Exam...")
    insert_calendar_event(exam_calendar_id, kwargs=software_exam)
    print("Adding Computational Biology Exam...")
    insert_calendar_event(exam_calendar_id, kwargs=biology_exam)
    print("\nDone! All events have been recreated for 2025.")
else:
    print("Could not find the Exam Week calendar")
