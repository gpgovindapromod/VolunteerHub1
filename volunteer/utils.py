"""Volunteer utility helpers"""

def get_volunteer_stats(db, vol_id):
    return {
        'applied':  db.execute('SELECT COUNT(*) FROM applications WHERE volunteer_id=?', (vol_id,)).fetchone()[0],
        'approved': db.execute("SELECT COUNT(*) FROM applications WHERE volunteer_id=? AND status='approved'", (vol_id,)).fetchone()[0],
        'rejected': db.execute("SELECT COUNT(*) FROM applications WHERE volunteer_id=? AND status='rejected'", (vol_id,)).fetchone()[0],
    }
