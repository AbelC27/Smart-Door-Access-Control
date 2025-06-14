# Smart Door Access Control System


A comprehensive IoT project that uses a Raspberry Pi for facial recognition to control a door lock. The system includes a web-based dashboard built with Django for real-time status monitoring and remote control via MQTT.

## 🌟 Features

-   **Facial Recognition Access:** The door unlocks only for authorized individuals.
-   **Real-time Status Dashboard:** A web interface built with Django to show the current status (e.g., "Authorized Access: [Name]", "Unknown Person Detected", "No Person Detected").
-   **Remote Control:** Manually open or close the door remotely from the web dashboard using MQTT commands.
-   **Visual Feedback:** On-device green and red LEDs indicate access status (granted/denied).
-   **Hardware Integration:** Utilizes a Raspberry Pi, Pi Camera, servo motor for the lock mechanism, and LEDs.
-   **Decoupled IoT Architecture:** Employs MQTT for robust and efficient communication between the Raspberry Pi and the Django backend.

## 🛠️ Tech Stack

### Hardware
-   Raspberry Pi 4B
-   Raspberry Pi Camera Module
-   Servo Motor (e.g., SG90) for the lock mechanism
-   External 5V Power Supply for the servo
-   Green & Red LEDs
-   Resistors & Jumper Wires

### Software & Frameworks
-   **Raspberry Pi (Device-side):**
    -   **Language:** Python 3
    -   **Core Libraries:**
        -   `face_recognition`: For detecting and recognizing faces.
        -   `OpenCV (cv2)`: For image processing and video stream handling.
        -   `Picamera2`: Modern library for interfacing with the Pi Camera.
        -   `gpiozero`: For easy control of GPIO components (LEDs, Servo).
        -   `paho-mqtt`: For publishing status and subscribing to commands.
        -   `requests`: For sending status updates to the Django backend via HTTP.
-   **Web Application (Server-side):**
    -   **Framework:** Django
    -   **Language:** Python 3
    -   **Database:** SQLite (default for development)
    -   **Communication:**
        -   Receives status updates via HTTP POST.
        -   Sends commands via MQTT (`paho-mqtt`).
-   **Communication Protocol:**
    -   **MQTT:** For sending commands from the web app to the Raspberry Pi.
    -   **HTTP:** For sending real-time status from the Raspberry Pi to the web app.

## ⚙️ Setup and Installation

### 1. Raspberry Pi Setup

**Prerequisites:**
-   A Raspberry Pi with Raspberry Pi OS (Bullseye or newer) installed.
-   Python 3 installed.
-   `pip` for Python 3 installed.
-   `pigpiod` daemon installed and running (`sudo systemctl start pigpiod`).

**Installation:**
1.  Clone this repository to your Raspberry Pi:
    ```bash
    git clone https://github.com/your-username/your-repo-name.git
    cd your-repo-name
    ```
2.  (Recommended) Create and activate a Python virtual environment:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
3.  Install the required Python packages:
    ```bash
    pip install -r requirements_pi.txt 
    ```
    *(You will need to create a `requirements_pi.txt` file with all the necessary libraries like `face_recognition`, `opencv-python`, `picamera2`, `gpiozero`, `paho-mqtt`, `requests`, etc.)*

4.  **Train the Face Recognition Model:**
    -   Place images of authorized people in the `dataset` folder, inside subfolders named after each person.
    -   Run the encoding script to create the `encodings.pickle` file:
        ```bash
        python encode_faces.py
        ```

5.  **Configure the Main Script:**
    -   Open `facial_recognition_hardware.py`.
    -   Update `LAPTOP_IP_ADDRESS` with the IP address of the machine running the Django server.
    -   Update `MQTT_BROKER_HOST` if you are using a local or private broker.
    -   Adjust `authorized_names` list to match the names of the people you trained.

6.  **Run the script:**
    ```bash
    python facial_recognition_hardware.py
    ```

### 2. Django Web Application Setup (on your Laptop/Server)

**Prerequisites:**
-   Python 3 installed.
-   `pip` for Python 3 installed.

**Installation:**
1.  Clone the repository to your machine.
2.  Navigate to the Django project directory (e.g., `door_control_web`).
3.  (Recommended) Create and activate a Python virtual environment.
4.  Install the required Python packages:
    ```bash
    pip install -r requirements_django.txt
    ```
    *(Create a `requirements_django.txt` file with libraries like `Django`, `paho-mqtt`, etc.)*

5.  **Configure the Django Project:**
    -   Open `ProiectPS/settings.py`.
    -   Add your machine's IP address to `ALLOWED_HOSTS`.
    -   Update MQTT settings if necessary.

6.  **Run the database migrations:**
    ```bash
    python manage.py migrate
    ```

7.  **Start the Django development server:**
    ```bash
    python manage.py runserver 0.0.0.0:8000
    ```

8.  Access the web panel in your browser at `http://127.0.0.1:8000/pi/status/`.

## 🚀 Usage

1.  Ensure the Django server is running on your laptop.
2.  Ensure your MQTT broker is running (if using a local one).
3.  Run the main script on the Raspberry Pi.
4.  Point the Pi Camera towards the area where faces will be detected.
5.  Open the web dashboard to monitor the status in real-time.
6.  Use the "Open Door" / "Close Door" buttons on the dashboard to manually control the lock.

## Future Improvements

-   [ ] Implement a database on the Django side to log all access events.
-   [ ] Use Django Channels and WebSockets for instant updates on the web dashboard without page refresh.
-   [ ] Add a Django admin interface to manage authorized users.
-   [ ] Improve security by using a private MQTT broker with username/password authentication.
--   [ ] Add more sensors (e.g., IR break-beam) to accurately detect entry vs. exit and count people in the room.
