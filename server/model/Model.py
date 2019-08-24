import datetime

from server import db


class Model(db.Model):
    __table_args__ = (db.UniqueConstraint('name_id', 'ver'),
                      db.UniqueConstraint('gid', 'hid'),)
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name_id = db.Column(db.Integer, db.ForeignKey('model_name.id'), nullable=False)
    gid = db.Column(db.Integer, db.ForeignKey('table.id'), nullable=False)
    hid = db.Column(db.Integer, db.ForeignKey('table.id'), nullable=False)
    time = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    ver = db.Column(db.Integer, nullable=False)
    memo = db.Column(db.String(320))
    # name: backref from ModelName

    def get_fate_path(self):
        return 'm%d_v%d' % (self.name_id, self.ver)
