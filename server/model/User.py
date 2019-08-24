from server import db
from server.model.ModelName import ModelName
from server.model.TableName import TableName

class User(db.Model):
    id = db.Column(db.Integer, autoincrement=True, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    pw_hash = db.Column(db.String(80), nullable=False)
    balance = db.Column(db.Numeric(10, 2), default=0)

    table_names = db.relationship('TableName',  backref=db.backref('user', lazy=True))
    model_names = db.relationship('ModelName',  backref=db.backref('user', lazy=True))
