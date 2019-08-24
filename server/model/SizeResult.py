from server import db


class SizeResult(db.Model):
    __table_args__ = (db.UniqueConstraint('hid', 'gid'),)
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    hid = db.Column(db.Integer, db.ForeignKey('table.id'), nullable=False)
    gid = db.Column(db.Integer, db.ForeignKey('table.id'), nullable=False)
    size = db.Column(db.Integer)
    host_table = db.relationship("Table", foreign_keys=[hid])
    guest_table = db.relationship("Table", foreign_keys=[gid])

