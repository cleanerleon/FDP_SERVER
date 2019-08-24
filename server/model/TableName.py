from server import db


class TableName(db.Model):
    __table_args__ = (db.UniqueConstraint('uid', 'name'), )
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    uid = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    tables = db.relationship('Table', backref='name', lazy=True)
