"""Attendance service"""
from db import get_db

def mark_attendance(assignment_id, is_present):
    db = get_db()
    db.execute('UPDATE assignments SET is_present=? WHERE id=?', (1 if is_present else 0, assignment_id))
    db.commit()

def get_attendance_summary(activity_id):
    db = get_db()
    total   = db.execute('SELECT COUNT(*) FROM assignments WHERE activity_id=?', (activity_id,)).fetchone()[0]
    present = db.execute('SELECT COUNT(*) FROM assignments WHERE activity_id=? AND is_present=1', (activity_id,)).fetchone()[0]
    return {'total': total, 'present': present, 'absent': total - present}
