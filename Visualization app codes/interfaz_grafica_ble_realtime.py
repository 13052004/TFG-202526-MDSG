import asyncio
import threading
import time
import csv
from bleak import BleakClient

import tkinter as tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt

import struct

ADDRESS = "DC:DA:0C:A1:99:92"
CHAR_UUID = "8f3a2c11-7b21-4c9e-b8aa-001122334455"

running = False

# ==================================================
# DATOS
# ==================================================

samples = []
timestamps = []

f1_data = []   # Isquión Izq
f2_data = []   # Isquión Der

f3_data = []   # Glúteo Izq
f4_data = []   # Glúteo Der

f5_data = []   # Muslo Izq
f6_data = []   # Muslo Der

sample_number = 0

# ==================================================
# ESTADO
# ==================================================

asym_state = "Equilibrado"

current_f1 = 0
current_f2 = 0
current_f3 = 0
current_f4 = 0
current_f5 = 0
current_f6 = 0

# ==================================================
# CRC
# ==================================================

def calculate_crc(data):

    crc = 0

    for b in data:
        crc ^= b

    return crc

# ==================================================
# BLE
# ==================================================

async def ble_loop():

    global running

    async with BleakClient(ADDRESS) as client:

        print("Conectado a ESP32")

        await client.start_notify(
            CHAR_UUID,
            notification_handler
        )

        while running:
            await asyncio.sleep(0.1)

def start_ble_thread():
    asyncio.run(ble_loop())

# ==================================================
# RECEPCIÓN BLE
# ==================================================

def notification_handler(sender, data):

    global sample_number
    global asym_state

    global current_f1
    global current_f2
    global current_f3
    global current_f4
    global current_f5
    global current_f6

    if not running:
        return

    if len(data) != 18:
        return

    if calculate_crc(data[:-1]) != data[-1]:
        return

    t = time.time()

    f1 = struct.unpack(">H", data[3:5])[0]
    f2 = struct.unpack(">H", data[5:7])[0]

    f3 = struct.unpack(">H", data[7:9])[0]
    f4 = struct.unpack(">H", data[9:11])[0]

    f5 = struct.unpack(">H", data[11:13])[0]
    f6 = struct.unpack(">H", data[13:15])[0]

    current_f1 = f1
    current_f2 = f2

    current_f3 = f3
    current_f4 = f4

    current_f5 = f5
    current_f6 = f6

    left = f1 + f3 + f5
    right = f2 + f4 + f6

    diff = left - right

    if abs(diff) < 50:
        asym_state = "Equilibrado"

    elif diff > 0:
        asym_state = "Izquierda"

    else:
        asym_state = "Derecha"

    sample_number += 1

    samples.append(sample_number)
    timestamps.append(t)

    f1_data.append(f1)
    f2_data.append(f2)

    f3_data.append(f3)
    f4_data.append(f4)

    f5_data.append(f5)
    f6_data.append(f6)

# ==================================================
# BOTONES
# ==================================================

def start():

    global running

    if not running:

        running = True

        threading.Thread(
            target=start_ble_thread,
            daemon=True
        ).start()

def stop():

    global running

    running = False

def reset():

    global sample_number

    samples.clear()
    timestamps.clear()

    f1_data.clear()
    f2_data.clear()

    f3_data.clear()
    f4_data.clear()

    f5_data.clear()
    f6_data.clear()

    sample_number = 0

# ==================================================
# CSV
# ==================================================

def save_csv():

    with open("datos_presion.csv", "w", newline="") as f:

        writer = csv.writer(f)

        writer.writerow([
            "Sample",
            "Timestamp",
            "Isquion_Izq",
            "Isquion_Der",
            "Gluteo_Izq",
            "Gluteo_Der",
            "Muslo_Izq",
            "Muslo_Der"
        ])

        for i in range(len(samples)):

            writer.writerow([

                samples[i],
                timestamps[i],

                f1_data[i],
                f2_data[i],

                f3_data[i],
                f4_data[i],

                f5_data[i],
                f6_data[i]
            ])

# ==================================================
# GUI
# ==================================================

root = tk.Tk()

root.title("Sistema de Monitorización de Presión")

fig, (ax1, ax2, ax3) = plt.subplots(
    3,
    1,
    figsize=(9, 8),
    sharex=True
)

canvas = FigureCanvasTkAgg(
    fig,
    master=root
)

canvas.get_tk_widget().pack()

label_status = tk.Label(
    root,
    text="Esperando datos...",
    font=("Arial", 12)
)

label_status.pack()

# ==================================================
# GRÁFICAS
# ==================================================

def update_plot():

    ax1.clear()
    ax2.clear()
    ax3.clear()

    # ===== ISQUIONES =====

    ax1.plot(
        samples,
        f1_data,
        label="Isquión Izq."
    )

    ax1.plot(
        samples,
        f2_data,
        label="Isquión Der."
    )

    ax1.set_title("Isquiones")
    ax1.grid()
    ax1.legend()

    # ===== GLÚTEOS =====

    ax2.plot(
        samples,
        f3_data,
        label="Glúteo Izq."
    )

    ax2.plot(
        samples,
        f4_data,
        label="Glúteo Der."
    )

    ax2.set_title("Glúteos")
    ax2.grid()
    ax2.legend()

    # ===== MUSLOS =====

    ax3.plot(
        samples,
        f5_data,
        label="Muslo Izq."
    )

    ax3.plot(
        samples,
        f6_data,
        label="Muslo Der."
    )

    ax3.set_title("Muslos")
    ax3.grid()
    ax3.legend()

    # ===== Estado =====

    arrow = "↔"

    if asym_state == "Izquierda":
        arrow = "←"

    elif asym_state == "Derecha":
        arrow = "→"

    label_status.config(
        text=
        f"{arrow} {asym_state}\n\n"
        f"Isq: {current_f1} / {current_f2}\n"
        f"Glúteos: {current_f3} / {current_f4}\n"
        f"Muslos: {current_f5} / {current_f6}"
    )

    canvas.draw()

    root.after(
        200,
        update_plot
    )

update_plot()

# ==================================================
# BOTONES
# ==================================================

frame = tk.Frame(root)
frame.pack()

tk.Button(
    frame,
    text="Start",
    command=start
).pack(side=tk.LEFT)

tk.Button(
    frame,
    text="Stop",
    command=stop
).pack(side=tk.LEFT)

tk.Button(
    frame,
    text="Reset",
    command=reset
).pack(side=tk.LEFT)

tk.Button(
    frame,
    text="Guardar CSV",
    command=save_csv
).pack(side=tk.LEFT)

root.mainloop()