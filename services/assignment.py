"""Assignment service"""
from db import get_db

def assign_volunteer(volunteer_id, activity_id, role):
    db = get_db()
    existing = db.execute(
        'SELECT id FROM assignments WHERE volunteer_id=? AND activity_id=?',
        (volunteer_id, activity_id)
    ).fetchone()
    if not existing:
        db.execute('INSERT INTO assignments (volunteer_id, activity_id, role) VALUES (?,?,?)',
                   (volunteer_id, activity_id, role))
        db.commit()
        return True
    return False
