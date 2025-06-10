import face_recognition
import cv2
import numpy as np
from picamera2 import Picamera2
import time
import pickle
import requests
import datetime
import json

from gpiozero import LED, Servo
from gpiozero.pins.pigpio import PiGPIOFactory
import paho.mqtt.client as mqtt

# --- Configurare GPIO ---
GREEN_LED_PIN = 17
RED_LED_PIN = 27
SERVO_PIN = 18

try:
    factory = PiGPIOFactory()
except OSError:
    print("[ERROR] pigpiod daemon not running.")
    factory = None

green_led = LED(GREEN_LED_PIN)
red_led = LED(RED_LED_PIN)

SERVO_LOCKED_VALUE = -0.8
SERVO_UNLOCKED_VALUE = 0.2

if factory:
    servo = Servo(SERVO_PIN, initial_value=SERVO_LOCKED_VALUE, min_pulse_width=0.0005, max_pulse_width=0.0025, pin_factory=factory)
else:
    servo = Servo(SERVO_PIN, initial_value=SERVO_LOCKED_VALUE, min_pulse_width=0.0005, max_pulse_width=0.0025)

print("[INFO] GPIO components initialized.")
green_led.off()
red_led.on() # Ușa pornește încuiată
servo.value = SERVO_LOCKED_VALUE
time.sleep(0.5)
# ------------------------

# --- Configurare Conexiune HTTP către Laptop (Django) ---
LAPTOP_IP_ADDRESS = "192.168.151.252"
LAPTOP_HTTP_URL = f"http://{LAPTOP_IP_ADDRESS}:8000/pi/update_status/"
# ------------------------------------------------------

# --- Configurare MQTT (pentru a primi comenzi de la Django) ---
MQTT_BROKER_HOST = "broker.hivemq.com"
MQTT_BROKER_PORT = 1883
MQTT_COMMAND_TOPIC = "usa/inteligenta/comanda"
MQTT_CLIENT_ID_PI_LISTENER = "raspberrypi_door_ctrl_listener" # Nume client unic
# -------------------------------------------------------------

# Load pre-trained face encodings
print("[INFO] loading encodings...")
try:
    with open("encodings.pickle", "rb") as f:
        data = pickle.loads(f.read())
    known_face_encodings = data["encodings"]
    known_face_names = data["names"]
    print(f"[INFO] Loaded {len(known_face_names)} known faces.")
except FileNotFoundError:
     print("[ERROR] encodings.pickle not found!")
     exit()
except Exception as e:
     print(f"[ERROR] Failed to load encodings: {e}")
     exit()

# Initialize the camera
print("[INFO] Initializing camera...")
picam2 = Picamera2()
config = picam2.create_preview_configuration(main={"format": 'XRGB8888', "size": (640, 480)})
picam2.configure(config)
picam2.start()
time.sleep(1.0)
print("[INFO] Camera started.")

# Initialize variables
cv_scaler = 1
face_locations = []
face_encodings = []
face_names_display = []
last_sent_status_tuple = None
status_change_time = 0
SEND_INTERVAL = 5.0
authorized_names = ["Abel Caluseri", "Alexandra Anghel"]

# --- Variabile pentru starea ușii controlată de MQTT ---
is_door_currently_open = False # Indică dacă ușa este fizic deschisă (servo la UNLOCKED)
door_open_start_time = 0
AUTO_CLOSE_DELAY = 5.0 # Secunde după care ușa se închide automat
# ----------------------------------------------------

# --- Funcții Callback MQTT ---
def on_mqtt_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[MQTT] Connected to Broker: {MQTT_BROKER_HOST}")
        client.subscribe(MQTT_COMMAND_TOPIC)
        print(f"[MQTT] Subscribed to command topic: {MQTT_COMMAND_TOPIC}")
    else:
        print(f"[MQTT] Failed to connect to broker, return code {rc}")

def open_door_sequence():
    """Secvența de deschidere a ușii."""
    global is_door_currently_open, door_open_start_time
    if not is_door_currently_open:
        print("[ACTION_MQTT] Opening door...")
        green_led.on()
        red_led.off()
        servo.value = SERVO_UNLOCKED_VALUE
        is_door_currently_open = True
        door_open_start_time = time.time()
        print(f"[INFO] Door opened. Will auto-close in {AUTO_CLOSE_DELAY}s if not closed manually.")
    else:
        print("[INFO_MQTT] Door is already open. Resetting auto-close timer.")
        door_open_start_time = time.time() # Resetăm timer-ul

def close_door_sequence():
    """Secvența de închidere a ușii."""
    global is_door_currently_open
    if is_door_currently_open:
        print("[ACTION_MQTT] Closing door...")
        servo.value = SERVO_LOCKED_VALUE
        green_led.off()
        red_led.on()
        is_door_currently_open = False
        print("[INFO] Door closed.")
    else:
        print("[INFO_MQTT] Door is already closed.")

def on_mqtt_message(client, userdata, msg):
    payload = msg.payload.decode().lower()
    print(f"[MQTT] Received command on '{msg.topic}': {payload}")

    if payload == "deschide":
        open_door_sequence()
    elif payload == "inchide":
        close_door_sequence()
    else:
        print(f"[MQTT_COMMAND] Unknown command received: {payload}")

# --- Inițializare Client MQTT ---
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID_PI_LISTENER)
mqtt_client.on_connect = on_mqtt_connect
mqtt_client.on_message = on_mqtt_message
try:
    mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
    mqtt_client.loop_start()
except Exception as e:
    print(f"[MQTT ERROR] Could not connect to MQTT broker: {e}")
    mqtt_client = None
# --------------------------------

# --- Funcție pentru a trimite statusul HTTP către laptop ---
def send_status_to_laptop(person_name, status_msg):
    # ... (codul funcției send_status_to_laptop este identic cu cel anterior) ...
    global last_sent_status_tuple, status_change_time
    current_status_tuple = (person_name, status_msg)
    current_time = time.time()
    if current_status_tuple != last_sent_status_tuple or (current_time - status_change_time > SEND_INTERVAL):
        payload = {
            "pi_timestamp": datetime.datetime.now().isoformat(),
            "person_name": person_name,
            "status": status_msg
        }
        try:
            # print(f"[HTTP] Sending status: {payload}") # Poate fi prea verbos
            response = requests.post(LAPTOP_HTTP_URL, json=payload, timeout=3.0)
            response.raise_for_status()
            # print(f"[HTTP] Server response: {response.status_code} - {response.json()}")
            last_sent_status_tuple = current_status_tuple
            status_change_time = current_time
        except requests.exceptions.Timeout:
            print(f"[ERROR_HTTP] Connection to {LAPTOP_HTTP_URL} timed out.")
        except requests.exceptions.ConnectionError:
            print(f"[ERROR_HTTP] Could not connect to {LAPTOP_HTTP_URL}. Is the server running?")
        except requests.exceptions.HTTPError as http_err:
             print(f"[ERROR_HTTP] HTTP error occurred: {http_err} - Response: {response.text}")
        except requests.exceptions.RequestException as e:
            print(f"[ERROR_HTTP] Failed to send status to laptop: {e}")
        except Exception as e:
             print(f"[ERROR_HTTP] An unexpected error occurred during HTTP send: {e}")


# --- Funcție pentru procesarea frame-ului (doar recunoaștere și trimitere HTTP) ---
def process_frame_for_recognition(frame):
    global face_locations, face_encodings, face_names_display

    if cv_scaler > 1:
        resized_frame = cv2.resize(frame, (0, 0), fx=(1/cv_scaler), fy=(1/cv_scaler))
    else:
        resized_frame = frame
    rgb_resized_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb_resized_frame, model='hog')
    http_status_message = "no_face"
    http_detected_person = "N/A"
    face_names_display = []

    if not face_locations:
        http_status_message = "no_face"
        http_detected_person = "N/A"
    else:
        face_encodings = face_recognition.face_encodings(rgb_resized_frame, face_locations, model='small', num_jitters=1)
        temp_best_status_for_http = "unknown"
        temp_person_for_http = "Unknown"
        is_authorized_person_in_frame = False # Doar pentru a ști dacă să trimitem "authorized"

        for face_encoding in face_encodings:
            matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.55)
            name = "Unknown"
            face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)

            if True in matches:
                best_match_index = np.argmin(face_distances)
                if matches[best_match_index] and face_distances[best_match_index] <= 0.55:
                    name = known_face_names[best_match_index]
                    if name in authorized_names:
                        is_authorized_person_in_frame = True
                        temp_best_status_for_http = "authorized"
                        temp_person_for_http = name
                        # Nu mai facem break, procesăm toate fețele pentru afișare
                    elif temp_best_status_for_http != "authorized":
                        temp_best_status_for_http = "unauthorized"
                        if temp_person_for_http == "Unknown": temp_person_for_http = name
            face_names_display.append(name)

        if is_authorized_person_in_frame:
            http_status_message = "authorized"
            http_detected_person = temp_person_for_http # Numele persoanei autorizate
        else:
            http_status_message = temp_best_status_for_http
            http_detected_person = temp_person_for_http
            if not face_names_display and face_locations:
                 http_detected_person = "Unknown"

    send_status_to_laptop(http_detected_person, http_status_message)
    # NU mai controlăm hardware-ul direct de aici pe baza recunoașterii
    return frame

# --- Funcția draw_results (rămâne la fel) ---
def draw_results(frame):
    # ... (codul tău existent pentru draw_results) ...
    for (top, right, bottom, left), name in zip(face_locations, face_names_display):
        top *= cv_scaler; right *= cv_scaler; bottom *= cv_scaler; left *= cv_scaler
        box_color = (0, 0, 255); auth_text = ""
        if name in authorized_names:
            box_color = (0, 255, 0); auth_text = "Auth"
        elif name != "Unknown":
             box_color = (0, 165, 255); auth_text = "Not Auth"
        cv2.rectangle(frame, (left, top), (right, bottom), box_color, 2)
        label_size, base_line = cv2.getTextSize(name, cv2.FONT_HERSHEY_DUPLEX, 0.7, 1)
        top_label = max(top - label_size[1], 0)
        cv2.rectangle(frame, (left, top_label - 5), (left + label_size[0], top), box_color, cv2.FILLED)
        cv2.putText(frame, name, (left, top - 3), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 255, 255), 1)
        if auth_text:
             cv2.putText(frame, auth_text, (left + 5, bottom - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return frame

# --- Funcția calculate_fps (rămâne la fel) ---
frame_count_fps = 0
start_time_fps = time.time()
fps_display = 0
def calculate_fps():
    # ... (codul tău existent pentru calculate_fps) ...
    global frame_count_fps, start_time_fps, fps_display
    frame_count_fps += 1; elapsed_time = time.time() - start_time_fps
    if elapsed_time > 1.0:
        fps_display = frame_count_fps / elapsed_time; frame_count_fps = 0; start_time_fps = time.time()
    return fps_display

# --- Funcție pentru a verifica și închide automat ușa ---
def check_auto_close_door():
    global is_door_currently_open, door_open_start_time
    if is_door_currently_open and (time.time() - door_open_start_time > AUTO_CLOSE_DELAY):
        print("[AUTO_CLOSE] Auto-closing door due to timeout.")
        close_door_sequence()

# --- Bucla Principală ---
print("[INFO] Starting main loop... Press 'q' to quit.")
try:
    while True:
        frame = picam2.capture_array()
        processed_frame = process_frame_for_recognition(frame) # Doar recunoaștere și HTTP
        display_frame = draw_results(processed_frame)
        current_fps_val = calculate_fps()
        cv2.putText(display_frame, f"FPS: {current_fps_val:.1f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow('Face Recognition (Status Only)', display_frame)

        # Verifică dacă ușa trebuie închisă automat
        check_auto_close_door()

        if cv2.waitKey(1) & 0xFF == ord('q'):
            print("[INFO] 'q' pressed, exiting loop.")
            break
        # Adăugăm un mic sleep pentru a nu suprasolicita CPU dacă nu e nevoie de FPS maxim
        # time.sleep(0.01) # Decomentează dacă vrei să reduci utilizarea CPU

finally:
    print("[INFO] Cleaning up...")
    cv2.destroyAllWindows()
    if 'picam2' in locals() and picam2: picam2.stop(); print("[INFO] Camera stopped.")
    if mqtt_client: mqtt_client.loop_stop(); mqtt_client.disconnect(); print("[MQTT] Disconnected.")
    if 'green_led' in locals(): green_led.off()
    if 'red_led' in locals(): red_led.on()
    if 'servo' in locals() and servo: servo.value = SERVO_LOCKED_VALUE; print("[INFO] Servo locked.")
    if factory: factory.close()
    print("[INFO] GPIO resources released.")
    print("[INFO] Script finished.")