from flask import Flask, render_template, request
import pymysql

app = Flask(__name__)

#homepage
@app.route('/')
def index():

    #connect to database
    db = pymysql.connect(
        host="localhost",
        user="pi",
        password="",
        database="IOT_LOCKBOX"
    )

    cursor = db.cursor()

    #get latest sensor data
    cursor.execute("""
        SELECT light, temperature, humidity
        FROM sensor_data
        ORDER BY id DESC
        LIMIT 1
    """)
    sensor = cursor.fetchone()

    #get latest access state
    cursor.execute("""
        SELECT action
        FROM access_log
        ORDER BY id DESC
        LIMIT 1
    """)
    state = cursor.fetchone()

    #get latest alarm
    # get latest alarm
    cursor.execute("""
        SELECT alarm_type, timestamp
        FROM alarms
        ORDER BY id DESC
        LIMIT 1
    """)
    row = cursor.fetchone()

    active_alarm = None

    if row:
        alarm_type, ts = row

        cursor.execute("""
            SELECT TIMESTAMPDIFF(SECOND, %s, NOW())
        """, (ts,))
        seconds_old = cursor.fetchone()[0]

        if seconds_old <= 10:
            active_alarm = alarm_type

    #calculate and get temperature statistics
    cursor.execute("""
    SELECT
        AVG(temperature),
        MIN(temperature),
        MAX(temperature)
    FROM sensor_data
    """)
    tempStats = cursor.fetchone()
    
    cursor.execute("""
        SELECT alarm_type, timestamp
        FROM alarms
        ORDER BY id DESC
        LIMIT 3
    """)
    alarms = cursor.fetchall()

  

    db.close()

    return render_template(
        'index.html',
        sensor=sensor,
        state=state,
        alarms=alarms,
        tempStats=tempStats,
        active_alarm=active_alarm
    )

#data page
@app.route('/data')
def data():
    db = pymysql.connect(
    host="localhost",
    user="pi",
    password="",
    database="IOT_LOCKBOX"
    )

    cursor = db.cursor()

    cursor.execute("SELECT * FROM sensor_data ORDER BY id DESC")
    sensor_data = cursor.fetchall()

    cursor.execute("SELECT * FROM alarms ORDER BY id DESC")
    alarms = cursor.fetchall()

    cursor.execute("SELECT * FROM access_log ORDER BY id DESC")
    access_logs = cursor.fetchall()

    db.close()

    return render_template(
    "data.html",
    sensor_data=sensor_data,
    alarms=alarms,
    access_logs=access_logs
    )

#controls page
@app.route('/controls', methods=['GET', 'POST'])
def control():
    db = pymysql.connect(
        host="localhost",
        user="pi",
        password="",
        database="IOT_LOCKBOX"
    )
    cursor = db.cursor()

    if request.method == 'POST':
        action = request.form.get("action")

        if action:
            cursor.execute(
                "INSERT INTO commands (command) VALUES (%s)",
                (action,)
            )
            db.commit()

    db.close()

    return render_template("controls.html")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)