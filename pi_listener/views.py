# pi_listener/views.py
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
import json
import datetime
import paho.mqtt.client as mqtt
import time

# Variabilă globală pentru a stoca ultimul status și starea butoanelor
latest_pi_status_data = {
    "message": "No data received yet from Raspberry Pi.",
    "person_name": None,
    "status": None,
    "received_at": None,
    "pi_timestamp": None,
    "show_buttons": False, # Butoanele sunt ascunse implicit
    "buttons_visible_since": 0 # Timpul când butoanele au devenit vizibile (după o acțiune autorizată sau manuală)
}

BUTTON_VISIBILITY_DURATION = 10 # Secunde cât rămân butoanele vizibile

@csrf_exempt
@require_http_methods(["POST"])
def update_status_view(request):
    global latest_pi_status_data
    try:
        data = json.loads(request.body)
        server_received_timestamp = datetime.datetime.now().isoformat()
        current_time_epoch = time.time()

        print(f"[{server_received_timestamp}] Received HTTP data from Pi: {data}")

        person_name = data.get('person_name')
        status_msg = data.get('status')
        pi_timestamp_from_payload = data.get('pi_timestamp')

        if person_name is None or status_msg is None:
             raise ValueError("Missing 'person_name' or 'status' in JSON data from Pi")

        # Logica pentru vizibilitatea butoanelor:
        new_show_buttons_state = latest_pi_status_data.get("show_buttons", False)
        new_buttons_visible_since = latest_pi_status_data.get("buttons_visible_since", 0)

        if status_msg == "authorized":
            new_show_buttons_state = True
            new_buttons_visible_since = current_time_epoch # Resetăm timer-ul la fiecare detecție autorizată
        elif status_msg == "unknown" or status_msg == "unauthorized":
            new_show_buttons_state = False # Ascundem butoanele explicit
            new_buttons_visible_since = 0
        elif status_msg == "no_face":
            # Dacă statusul devine "no_face", verificăm dacă butoanele erau vizibile
            # (de la o detecție autorizată anterioară sau o deschidere manuală)
            # și dacă a trecut timpul de vizibilitate.
            if latest_pi_status_data.get("show_buttons") and \
               (current_time_epoch - latest_pi_status_data.get("buttons_visible_since", 0) > BUTTON_VISIBILITY_DURATION):
                new_show_buttons_state = False
                new_buttons_visible_since = 0

        latest_pi_status_data.update({
            "person_name": person_name,
            "status": status_msg,
            "received_at": server_received_timestamp,
            "pi_timestamp": pi_timestamp_from_payload,
            "show_buttons": new_show_buttons_state,
            "buttons_visible_since": new_buttons_visible_since,
            "message": None
        })

        return JsonResponse({"message": "HTTP Data received by Django successfully"}, status=200)
    # ... (blocurile except rămân la fel) ...
    except json.JSONDecodeError:
        print("[DJANGO_ERROR] Invalid JSON received in HTTP POST")
        return JsonResponse({"error": "Invalid JSON format in HTTP POST"}, status=400)
    except ValueError as ve:
         print(f"[DJANGO_ERROR] Invalid HTTP data: {ve}")
         return JsonResponse({"error": str(ve)}, status=400)
    except Exception as e:
         print(f"[DJANGO_ERROR] Unexpected error in update_status_view: {e}")
         return JsonResponse({"error": "Internal server error processing HTTP POST"}, status=500)

@require_http_methods(["GET"])
def status_display_view(request):
    global latest_pi_status_data
    current_time_epoch = time.time()

    # Verificăm din nou timeout-ul butoanelor la fiecare refresh al paginii
    # Aceasta este o măsură de siguranță, mai ales dacă Pi-ul nu mai trimite statusuri.
    if latest_pi_status_data.get("show_buttons"): # Doar dacă sunt setate să fie vizibile
        # Verificăm dacă a trecut timpul de vizibilitate de la ultima acțiune care le-a făcut vizibile
        if (current_time_epoch - latest_pi_status_data.get("buttons_visible_since", 0) > BUTTON_VISIBILITY_DURATION):
            # Și dacă statusul curent NU este "authorized" (caz în care timer-ul s-ar fi resetat oricum)
            # Sau dacă statusul este "no_face" (caz în care vrem să expire)
            if latest_pi_status_data.get("status") != "authorized" or latest_pi_status_data.get("status") == "no_face":
                print("[DJANGO_VIEW_REFRESH] Button visibility timeout reached. Hiding buttons.")
                latest_pi_status_data["show_buttons"] = False
                latest_pi_status_data["buttons_visible_since"] = 0

    context = {
        'status_info': latest_pi_status_data
    }
    return render(request, 'status_display.html', context)

@require_http_methods(["GET"])
def send_door_command_view(request):
    global latest_pi_status_data
    command_to_send = request.GET.get('command', None)

    if command_to_send not in ["deschide", "inchide"]:
        return JsonResponse({"error": "Invalid command."}, status=400)

    # ... (codul MQTT pentru trimiterea comenzii rămâne la fel) ...
    mqtt_broker = getattr(settings, 'MQTT_BROKER_HOST', "broker.hivemq.com")
    mqtt_port = getattr(settings, 'MQTT_BROKER_PORT', 1883)
    mqtt_topic = getattr(settings, 'MQTT_COMMAND_TOPIC', "usa/inteligenta/comanda")
    client_id = f"django_cmd_sender_{int(time.time())}"
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=client_id)
    error_message = None # Inițializăm cu None
    try:
        client.connect(mqtt_broker, mqtt_port, 60)
        client.loop_start()
        result = client.publish(mqtt_topic, command_to_send.lower(), qos=1)
        result.wait_for_publish(timeout=3)
        if not result.is_published():
            error_message = f"MQTT publish failed. RC: {result.rc}" # Setăm mesajul de eroare
        client.loop_stop()
        client.disconnect()
    except Exception as e:
        error_message = f"MQTT error: {e}" # Setăm mesajul de eroare
        print(f"[DJANGO_MQTT_PUB_ERROR] {error_message}")


    if command_to_send == "deschide":
        # Când se deschide manual, vrem ca butoanele să apară/rămână vizibile pentru durata setată
        latest_pi_status_data["show_buttons"] = True
        latest_pi_status_data["buttons_visible_since"] = time.time() # Resetăm timer-ul
        print("[DJANGO_VIEW] 'deschide' command sent, ensuring buttons are visible.")
    elif command_to_send == "inchide":
        # Ascundem butoanele imediat după ce se apasă "inchide"
        latest_pi_status_data["show_buttons"] = False
        latest_pi_status_data["buttons_visible_since"] = 0 # Resetăm timer-ul
        print("[DJANGO_VIEW] 'inchide' command sent, hiding buttons.")

    if error_message:
        # Aici ai putea folosi django.contrib.messages pentru a afișa eroarea utilizatorului
        # messages.error(request, f"Failed to send command: {error_message}")
        print(f"Error to potentially display to user: {error_message}")


    return redirect('pi_listener:status_display')