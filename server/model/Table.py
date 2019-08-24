import os
import datetime

from server import db, app


class Table(db.Model):
    __table_args__ = (db.UniqueConstraint('name_id', 'ver'), )
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name_id = db.Column(db.Integer, db.ForeignKey('table_name.id'), nullable=False)
    ver = db.Column(db.Integer, nullable=False, default=1)
    time = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    id_col = db.Column(db.String(10), default='id')
    y_col = db.Column(db.String(10))
    y_col_id = db.Column(db.Integer, default=-1)
    memo = db.Column(db.String(320), default='')
    price0 = db.Column(db.Numeric(10, 2), default=.01)
    price1 = db.Column(db.Numeric(10, 2), default=.01)
    price2 = db.Column(db.Numeric(10, 2), default=.01)
    score = db.Column(db.Float)
    # name backref from TableName

    def get_fate_path(self):
        return 't%d_v%d' % (self.name_id, self.ver)

    def get_local_path(self):
        path = 'u%d_t%d_v%d' % (self.name.uid, self.name_id, self.ver)
        return os.path.join(app.config['UPLOAD_FOLDER'], path)
