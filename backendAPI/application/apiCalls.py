import time
import os
from sqlalchemy import desc
from datetime import datetime, timedelta
from application import app, db
from flask import Flask, request, jsonify, send_file
import csv
import pytz

app.app_context().push()
from application.databaseModel import StoreInit, StoreStatus, MenuHours
app.config['REPORT_FOLDER'] = '/report'

def csvToDatabase():
    with open('Data/bq-results-20230125-202210-1674678181880.csv', 'r') as timezoneFile:
        storeTimezone = csv.DictReader(timezoneFile)
        for row in storeTimezone:
            storeInitCommit = StoreInit(storeID = row['store_id'], timezone = row.get('timezone_str', 'America/Chicago'))
            db.session.add(storeInitCommit)
        db.session.commit()

    with open('Data/store status.csv', 'r') as storeStatusFile:
        storeStatusContents = csv.DictReader(storeStatusFile)
        for row in storeStatusContents:
            timestampUTCRemove = row['timestamp_utc'].replace(' UTC', '')
            try:
                timestampUTC = datetime.strptime(timestampUTCRemove, '%Y-%m-%d %H:%M:%S.%f')
            except ValueError:
                timestampUTC = datetime.strptime(timestampUTCRemove, '%Y-%m-%d %H:%M:%S')
            storeStatusCommit = StoreStatus(storeID = row['store_id'], storeStatus = row['status'], UTCTime = timestampUTC)
            db.session.add(storeStatusCommit)
        db.session.commit()

    with open('Data/Menu hours.csv', 'r') as MenuHoursFile:
        MenuHoursContents = csv.DictReader(MenuHoursFile)
        for row in MenuHoursContents:
            MenuHoursCommmit = MenuHours(storeID = row['store_id'], day = int(row['day']), startTimeLocal = row.get('start_time_local', '00:00:00'), endTimeLocal = row.get('end_time_local', '23:59:59'))
            db.session.add(MenuHoursCommmit)
        db.session.commit()




def finalGenerator():
    #Keeping track of the values
    dataForCSV = []


    # StoresQuery = StoreInit.query.filter_by()
    # StoreInit.query.filter_by(storeID=store.storeID).all()
    StoresQuery = StoreInit.query.all()

    for specificStores in StoresQuery:
        #we go from descending order as this allows for subtraction of dates and get the last hour and the last day and the last week easier
        StoreStatusQuery = StoreStatus.query.filter_by(storeID = specificStores.storeID).order_by(desc(StoreStatus.UTCTime)).all()

        if len(StoreStatusQuery):
            latestDayPossibleUTC = StoreStatusQuery[0].UTCTime.astimezone(pytz.utc)

        uptime_last_hour = 0
        downtime_last_hour = 0
        uptime_last_day = 0
        downtime_last_day = 0
        uptime_last_week = 0
        downtime_last_week = 0
        lastHourBool = False
        
        #Variables needed for algo
        prevResult = None
        prevActive = 0
        prevEndDatetime = 0
        benefitOfTheDoubt = True

        prevResultWeek = None
        prevActiveWeek = 0
        prevEndDatetimeWeek = 0
        prevStartDatetimeWeek = 0
        benefitOfTheDoubtWeek = True
        dayGap = 1

        #Check if there is a timezone, if there isn't then it is America/Chicago
        for latestTime in StoreStatusQuery:
            if specificStores.timezone is not None:
                timezoneToUse = pytz.timezone(specificStores.timezone)
            else:
                timezoneToUse = pytz.timezone("America/Chicago")

            pytzUTCLatestTime = latestTime.UTCTime.astimezone(pytz.utc)
            pytzUTCLatestTimeConverted = pytzUTCLatestTime.astimezone(timezoneToUse)
            latestDayPossibleUTCConverted = latestDayPossibleUTC.astimezone(timezoneToUse)
            pytzUTCLatestTimeConvertedDay = pytzUTCLatestTimeConverted.weekday()

            #This is the utc converted to the timezone desired then turned into the format of only having the time
            menuHoursFormat = pytzUTCLatestTimeConverted.time()



            #Check if the store has a opening and closing time, if it doesn't then we know it is open 24 hours
            openCloseMenuHours = MenuHours.query.filter_by(storeID = specificStores.storeID, day = pytzUTCLatestTimeConvertedDay).first()
            if openCloseMenuHours is None:
                startTimeLocalDatetimeStart = datetime.strptime("00:00:00", "%H:%M:%S").time()
                startTimeLocalDatetimeEnd = datetime.strptime("23:59:59", "%H:%M:%S").time()
            else:
                startTimeLocalDatetimeStart = datetime.strptime(openCloseMenuHours.startTimeLocal, "%H:%M:%S").time()
                startTimeLocalDatetimeEnd = datetime.strptime(openCloseMenuHours.endTimeLocal, "%H:%M:%S").time()

            
            #These are all variables initialized to be able to subtract from each other
            #These variables include the opening of the store and closing of the store on this particular weekday, and the time of the status
            start_datetime = datetime.combine(datetime.min, startTimeLocalDatetimeStart)
            end_datetime = datetime.combine(datetime.min, startTimeLocalDatetimeEnd)
            menu_datetime = datetime.combine(datetime.min, menuHoursFormat)


            #I check if the formatted time is between the store's opening and closing times and check if this has already been called
            if (startTimeLocalDatetimeStart <= menuHoursFormat <= startTimeLocalDatetimeEnd) and not (lastHourBool):
                time_difference = end_datetime - menu_datetime
                if latestTime.storeStatus == "active":
                    if ((time_difference.total_seconds() / 60) > 60):
                        uptime_last_hour = 60
                    else:
                        uptime_last_hour += (time_difference.total_seconds() / 60)
                    lastHourBool = True
                else:
                    if ((time_difference.total_seconds() / 60) > 60):
                        downtime_last_hour = 60
                    else:
                        downtime_last_hour += (time_difference.total_seconds() / 60)
                    lastHourBool = True


            #This is to check for the day, and this checks if it is in the store opening/closing hours and it is the same day as the last day possible
            if (startTimeLocalDatetimeStart <= menuHoursFormat <= startTimeLocalDatetimeEnd) and (latestDayPossibleUTCConverted.date() == pytzUTCLatestTimeConverted.date()):
                    #This is where things get tricky
                    #we first want to check if the storeStatus is active
                    if latestTime.storeStatus == "active":
                        #If it is we are going to go to benefitOftheDoubt mode
                        #This means that the store was either closed for the whole day or openeded for the whole day, in this case opened
                        if prevResult is None and benefitOfTheDoubt:
                            uptime_last_day = (end_datetime - start_datetime).total_seconds() / 60
                            prevResult, prevActive, prevEndDatetime = menu_datetime, "active", end_datetime
                        #Next if there is another result from the day then you can not base that the store was open or closed for the whole day
                        #We subtract the value of the hours of the store based on the previous activity and then calculate the store closing time - the first input we got
                        #Then we subtract the first input we got - this store status
                        #We then get rid of benefitOfTheDoubt because we know there are numerous activities in this day
                        elif prevResult and benefitOfTheDoubt:
                            if prevActive == "inactive":
                                downtime_last_day = (prevEndDatetime - prevResult).total_seconds() / 60
                                uptime_last_day = (prevResult - menu_datetime).total_seconds() / 60
                                prevResult, prevActive, prevEndDatetime = menu_datetime, "active", end_datetime
                                benefitOfTheDoubt = False
                            else:
                                uptime_last_day = ((prevEndDatetime - prevResult).total_seconds() + (prevResult - menu_datetime).total_seconds()) / 60
                                prevResult, prevActive, prevEndDatetime = menu_datetime, "active", end_datetime
                                benefitOfTheDoubt = False
                        else:
                            #Calcute normally, subtract the last status from this status and count that as active or inactive based on this status
                            uptime_last_day += (prevResult - menu_datetime).total_seconds() / 60
                            prevResult, prevActive, prevEndDatetime = menu_datetime, "active", end_datetime      
                    else:
                        #This is just mirrored but variables altered on the prev activity
                        if prevResult is None and benefitOfTheDoubt:
                            downtime_last_day = (end_datetime - start_datetime).total_seconds() / 60
                            prevResult, prevActive, prevEndDatetime = menu_datetime, "inactive", end_datetime
                        elif prevResult and benefitOfTheDoubt:
                            if prevActive == "active":
                                uptime_last_day = (prevEndDatetime - prevResult).total_seconds() / 60
                                downtime_last_day = (prevResult - menu_datetime).total_seconds() / 60
                                prevResult, prevActive, prevEndDatetime = menu_datetime, "inactive", end_datetime
                                benefitOfTheDoubt = False
                            else:
                                downtime_last_day = ((prevEndDatetime - prevResult).total_seconds() + (prevResult - menu_datetime).total_seconds()) / 60
                                prevResult, prevActive, prevEndDatetime = menu_datetime, "inactive", end_datetime
                                benefitOfTheDoubt = False
                        else:
                            downtime_last_day += (prevResult - menu_datetime).total_seconds() / 60
                            prevResult, prevActive, prevEndDatetime = menu_datetime, "inactive", end_datetime 

            #Check week
            if (startTimeLocalDatetimeStart <= menuHoursFormat <= startTimeLocalDatetimeEnd) and (((latestDayPossibleUTCConverted.date() - pytzUTCLatestTimeConverted.date()).total_seconds() / 86400) <= 7):
                #This restarts the variables as it is a new day and have to include benefitOfTheDoubt
                if ((latestDayPossibleUTC.date() - pytzUTCLatestTimeConverted.date()).total_seconds() / 86400) > dayGap:
                    dayGap += 1
                    prevResultWeek = None
                    prevActiveWeek = None
                    prevStartDatetimeWeek = None
                    prevEndDatetimeWeek = None
                    benefitOfTheDoubtWeek = True
                

                #The code for this is similar to the day code expect we have to += and subtract and not restart the variable as then we would lose progress
                if latestTime.storeStatus == "active":
                    if prevResultWeek is None and benefitOfTheDoubtWeek:
                        uptime_last_week += (end_datetime - start_datetime).total_seconds() / 60
                        prevResultWeek, prevActiveWeek, prevStartDatetimeWeek, prevEndDatetimeWeek = menu_datetime, "active", start_datetime, end_datetime
                    elif prevResultWeek and benefitOfTheDoubtWeek:
                        if prevActiveWeek == "inactive":
                            downtime_last_week = downtime_last_week - ((prevEndDatetimeWeek - prevStartDatetimeWeek).total_seconds() / 60) + ((prevEndDatetimeWeek - prevResultWeek).total_seconds() / 60)
                            uptime_last_week += ((prevResultWeek - menu_datetime).total_seconds() / 60)
                            prevResultWeek, prevActiveWeek, prevStartDatetimeWeek, prevEndDatetimeWeek = menu_datetime, "active", start_datetime, end_datetime
                            benefitOfTheDoubtWeek = False
                        else:
                            uptime_last_week = uptime_last_week - ((prevEndDatetimeWeek - prevStartDatetimeWeek).total_seconds() / 60) + ((prevEndDatetimeWeek - prevResultWeek).total_seconds() / 60) + ((prevResultWeek - menu_datetime).total_seconds() / 60)
                            prevResultWeek, prevActiveWeek, prevStartDatetimeWeek, prevEndDatetimeWeek = menu_datetime, "active", start_datetime, end_datetime
                            benefitOfTheDoubtWeek = False
                    else:
                        uptime_last_week += (prevResultWeek - menu_datetime).total_seconds() / 60
                        prevResultWeek, prevActiveWeek, prevEndDatetimeWeek = menu_datetime, "active", end_datetime      
                else:
                    if prevResultWeek is None and benefitOfTheDoubtWeek:
                        downtime_last_week += (end_datetime - start_datetime).total_seconds() / 60
                        prevResult, prevActive, prevStartDateTimeWeek, prevEndDatetimeWeek = menu_datetime, "inactive", start_datetime, end_datetime
                    elif prevResult and benefitOfTheDoubtWeek:
                        if prevActiveWeek == "active":
                            uptime_last_week = downtime_last_week - ((prevEndDatetimeWeek - prevStartDateTimeWeek).total_seconds() / 60) + ((prevEndDatetimeWeek - prevResultWeek).total_seconds() / 60)
                            downtime_last_week += (prevResultWeek - menu_datetime).total_seconds() / 60
                            prevResultWeek, prevActiveWeek, prevStartDatetimeWeek, prevEndDatetimeWeek = menu_datetime, "active", start_datetime, end_datetime
                            benefitOfTheDoubtWeek = False
                        else:
                            downtime_last_week = downtime_last_week - ((end_datetime - start_datetime).total_seconds() / 60) + ((prevEndDatetimeWeek - prevResultWeek).total_seconds() / 60) + ((prevResultWeek - menu_datetime).total_seconds() / 60)
                            prevResultWeek, prevActiveWeek, prevStartDatetimeWeek, prevEndDatetimeWeek = menu_datetime, "active", start_datetime, end_datetime
                            benefitOfTheDoubtWeek = False
                    else:
                        downtime_last_week += (prevResultWeek - menu_datetime).total_seconds() / 60
                        prevResultWeek, prevActiveWeek, prevEndDatetimeWeek = menu_datetime, "inactive", end_datetime

        print("uptime_last_hour", uptime_last_hour)
        print("uptime_last_week", uptime_last_week / 60)
        print("downtime_last_week", downtime_last_week / 60)

        report_row = {
            'store_id': specificStores.storeID,
            'uptime_last_hour': uptime_last_hour,
            'downtime_last_hour': downtime_last_hour,
            'uptime_last_day': uptime_last_day / 60,
            'downtime_last_day': downtime_last_day / 60,
            'uptime_last_week': uptime_last_week / 60,
            'downtime_last_week': downtime_last_week / 60
        }

        dataForCSV.append(report_row)


    report_id = 1234
    file_path = f'{report_id}.csv'
    final_file_path = "application/" + file_path


    with open(final_file_path, 'w', newline='') as report_file:
        fieldnames = ['store_id', 'uptime_last_hour', 'downtime_last_hour', 'uptime_last_day', 'downtime_last_day', 'uptime_last_week', 'downtime_last_week']
        writer = csv.DictWriter(report_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(dataForCSV)

    print("finished")
    return report_id


@app.route('/trigger_report', methods = ['GET'])
def trigger_report():
    #Can random this
    report_id = 1234
    return {'reportID': report_id}

@app.route('/get_report', methods=['GET'])
def my_endpoint():
    inputValue = request.args.get('input')
    print(inputValue)
    if (inputValue is None):
        return {'status': 'error'}
    # Process the input value as needed
    check_file = os.path.isfile(f'application/{inputValue}.csv')
    if not check_file:
        finalGenerator()
        return jsonify({'status': 'running'})

    return {'status': 'Complete'}
    
    
@app.route('/download_report', methods=['GET'])
def download_report():
    # Code to retrieve the report file path
    report_file_path = '1234.csv'

    return send_file(report_file_path, mimetype='text/csv', as_attachment=True)

