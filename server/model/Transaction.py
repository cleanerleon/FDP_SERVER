import datetime

from server import db


class Transaction(db.Model):
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    time = db.Column(db.DateTime, nullable=False, default=datetime.datetime.utcnow)
    gid = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    hid = db.Column(db.Integer, db.ForeignKey('user.id'))
    type = db.Column(db.Integer, nullable=False)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
