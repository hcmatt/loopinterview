from application import db

#By having this StoreInit I can use the storeID as a primary key
#If i were to combine the start time and end time, there would be multiple of the same storeID lines in the database
class StoreInit(db.Model):
    storeID = db.Column(db.Integer, primary_key = True)
    timezone = db.Column(db.String(64), default = 'America/Chicago')
    storeStatusBackref = db.relationship('StoreStatus', backref='store_init')
    MenuHoursBackRef = db.relationship('MenuHours', backref='store_init')

class StoreStatus(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    storeID = db.Column(db.Integer, db.ForeignKey('store_init.storeID'))
    storeStatus = db.Column(db.String(16))
    UTCTime = db.Column(db.DateTime)

class MenuHours(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    storeID = db.Column(db.Integer, db.ForeignKey('store_init.storeID'))
    day = db.Column(db.Integer)
    startTimeLocal = db.Column(db.String(16))
    endTimeLocal = db.Column(db.String(16))

