from server import db


class ModelName(db.Model):
    __table_args__ = (db.UniqueConstraint('name', 'uid'),
                      db.UniqueConstraint('hid', 'gid'))
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    uid = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    hid = db.Column(db.Integer, db.ForeignKey('table_name.id'), nullable=False)
    gid = db.Column(db.Integer, db.ForeignKey('table_name.id'), nullable=False)
    models = db.relationship('Model', backref='name', lazy=True)
