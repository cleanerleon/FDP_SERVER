from server import db


class CVResult(db.Model):
    __table_args__ = (db.UniqueConstraint('hid', 'gid'),)
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    hid = db.Column(db.Integer, db.ForeignKey('table.id'), nullable=False)
    gid = db.Column(db.Integer, db.ForeignKey('table.id'), nullable=False)
    score = db.Column(db.Float)
    score_gap = db.Column(db.Float)
    host_table = db.relationship("Table", foreign_keys=[hid])
    guest_table = db.relationship("Table", foreign_keys=[gid])
