import serial
import pymysql
import time

device = '/dev/cu.usbmodem101'
arduino = serial.Serial(device, 9600)


#arm delay system
arm_delay_active = False #delay period
arm_delay_start = 0.0 
Armed = True 

#send command to arduino function
def send_cmd(cmd: str):
    arduino.write(f"{cmd}\n".encode())
    print(f"[→ Arduino] {cmd}")



dbconn = None 
try:
    #database connection setup
    dbconn = pymysql.connect(
        host = "localhost",
        user = "pi",
        password = "",
        database = "IOT_LOCKBOX"
    )
    print("Connected to database.") #verifies connection

    cursor = dbconn.cursor() 

    #Thresholds table
    cursor = dbconn.cursor()

    cursor.execute("""CREATE TABLE IF NOT EXISTS thresholds (
        param VARCHAR(30) PRIMARY KEY, value FLOAT NOT NULL
    )""")
    dbconn.commit()

    cursor.execute("SELECT COUNT(*) FROM thresholds")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO thresholds (param, value) VALUES (%s,%s)",
            [("TEMP_MIN",15.0),("TEMP_MAX",30.0),("HUM_MIN",40.0),("HUM_MAX",70.0),("LDR_MAX",25.0)]
        )
        dbconn.commit()

    last_threshold_fetch = 0
    

    #track alarm states to detect changes
    prevLdr = 0
    prevTemp = 0
    prevHum = 0
    prevState = ""

    #track active alarms
    ldrAlarm = 0
    wrongPwdAlarm = 0

    #make sure data logged once
    ldrLogged = False
    tempLogged = False
    humLogged = False
    wrongPwdLogged = False

    #store sensor data every 30 seconds
    last_sensor_insert = 0
    SENSOR_INTERVAL = 30


    while True:
        if time.time() - last_threshold_fetch >= 10:
            cursor.execute("SELECT param, value FROM thresholds")
            t = {row[0]: row[1] for row in cursor.fetchall()}
            TEMP_MIN = t.get("TEMP_MIN", 15.0)
            TEMP_MAX = t.get("TEMP_MAX", 30.0)
            HUM_MIN = t.get("HUM_MIN",  40.0)
            HUM_MAX = t.get("HUM_MAX",  70.0)
            LDR_MAX = t.get("LDR_MAX",  15.0)
            last_threshold_fetch = time.time()
            

        #delay alarm enabling by 2 secs
        if arm_delay_active and time.time() - arm_delay_start > 2.0:
            arm_delay_active = False
        
        arduino = serial.Serial(device, 9600, timeout=1)
        
        #read arduino data
        data = arduino.readline().decode('utf-8').strip()
        if not data:
            continue
        
        print("Received:", data)

        #extract commands from ardiuno
        if data.startswith("CMD,"):
            cmd = data.split(",")[1]

            if cmd == "MUTE":
                print("Buzzer muted by button — alarm states preserved")

            elif cmd == "WRONG_PASSWORD":
                wrongPwdAlarm = 1 #trigger wrong pasword alarm 

                if not wrongPwdLogged: 
                    cursor.execute("INSERT INTO alarms (alarm_type) VALUES ('WRONG-PASSWORD')") #log wrong password attemp into db
                    dbconn.commit()
                    wrongPwdLogged = True
                    print("Wrong password alarm logged")
                send_cmd("ALARM_LDR") #tells arduino to trigger alarm

            continue

        #ensure correct sensor data format
        values = data.split(",")
        if len(values) != 4:
            continue

        light = float(values[0])
        temp = float(values[1])
        hum = float(values[2])
        state = values[3].strip()

        cursor.execute("SELECT id, command FROM commands WHERE executed=0")
        commands = cursor.fetchall()

        for cmd_id, command in commands:
            print("Web command:", command)

            if command == "LOCK":
                send_cmd("LOCK")

            elif command == "UNLOCK":
                send_cmd("UNLOCK")

            elif command == "MUTE":
                send_cmd("MUTE")

            # mark as executed
            cursor.execute(
                "UPDATE commands SET executed=1 WHERE id=%s",
                (cmd_id,)
            )
            dbconn.commit()

        # alarm logic 
        #if system armed & not in delay & light too high, trigger alarm
        if Armed and not arm_delay_active and light > LDR_MAX:
            ldrAlarm = 1

        #temp alarm if out of range
        tempAlarm = 1 if (temp < TEMP_MIN or temp > TEMP_MAX) else 0

        #humidity alarm if out of range
        humAlarm  = 1 if (hum  < HUM_MIN  or hum  > HUM_MAX)  else 0

        #detect changes in state
        if state == "1" and prevState != "1": #unlocked 
            Armed = False 
            arm_delay_active = False
            ldrAlarm = 0 #reset ldr alarm
            wrongPwdAlarm = 0 #reset wromg pwd alarm
            ldrLogged = False
            wrongPwdLogged = False
            send_cmd("CLEAR_LDR")

            #enable dht11 alarms again
            if tempAlarm:send_cmd("ALARM_TEMP")
            if humAlarm: send_cmd("ALARM_HUM")
        

            #log unlock 
            cursor.execute("""
                INSERT INTO access_log (action, method)
                VALUES ('UNLOCK', 'KEYPAD')
            """)
            dbconn.commit()
            print("Unlock logged")

        elif state == "0" and prevState != "0": #locked, starts armed system
            Armed = True
            arm_delay_active = True #delay 2 secs
            arm_delay_start = time.time()

            #log locked
            cursor.execute("""
                INSERT INTO access_log (action, method)
                VALUES ('LOCK', 'KEYPAD')
            """)
            dbconn.commit()
            print("Lock logged")

        # send alarm commands to Arduino 
        if ldrAlarm and not prevLdr: send_cmd("ALARM_LDR")
        if tempAlarm and not prevTemp: send_cmd ("ALARM_TEMP")
        if humAlarm and not prevHum: send_cmd("ALARM_HUM")

        if not tempAlarm and prevTemp: send_cmd("CLEAR_TEMP")
        if not humAlarm  and prevHum:  send_cmd("CLEAR_HUM")

        #log alarm events 

        #ldr alarm
        if ldrAlarm == 1 and not ldrLogged:
            cursor.execute("INSERT INTO alarms (alarm_type) VALUES ('UNAUTHORISED-ACCESS')")
            dbconn.commit()
            ldrLogged = True
            print("LDR alarm logged")

        #temp alarm
        if tempAlarm == 1 and not tempLogged:
            cursor.execute("INSERT INTO alarms (alarm_type) VALUES ('TEMPERATURE')")
            dbconn.commit()
            tempLogged = True
            print("Temp alarm logged")

        #humidity alarm
        if humAlarm == 1 and not humLogged: 
            cursor.execute("INSERT INTO alarms (alarm_type) VALUES ('HUMIDITY')")
            dbconn.commit()
            humLogged = True
            print("Hum alarm logged")

        if tempAlarm == 0: tempLogged = False
        if humAlarm  == 0: humLogged  = False

        #store sensor data periodically 
        now = time.time()
        if now - last_sensor_insert >= SENSOR_INTERVAL:
            cursor.execute("""
                INSERT INTO sensor_data (light, temperature, humidity)
                VALUES (%s, %s, %s)
            """, (light, temp, hum))
            dbconn.commit()
            last_sensor_insert = now
            print("Sensor data inserted.")

        #update previous states
        prevLdr = ldrAlarm
        prevTemp = tempAlarm
        prevHum = humAlarm
        prevState = state

        time.sleep(0.1)

except pymysql.MySQLError as e:
    print(f"Database error: {e}")
finally:
    if dbconn:
        cursor.close()
        dbconn.close()