import asyncio
import threading
from bleak import BleakClient

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from mpl_toolkits.mplot3d import Axes3D

import numpy as np
import struct

ADDRESS = "DC:DA:0C:A1:99:92"
CHAR_UUID = "8f3a2c11-7b21-4c9e-b8aa-001122334455"

# ==================================================
# VARIABLES GLOBALES
# ==================================================

force1 = 0  # Isquión izquierdo
force2 = 0  # Isquión derecho

force3 = 0  # Glúteo izquierdo
force4 = 0  # Glúteo derecho

force5 = 0  # Muslo izquierdo
force6 = 0  # Muslo derecho

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

def notification_handler(sender, data):

    global force1
    global force2
    global force3
    global force4
    global force5
    global force6

    if len(data) != 18:
        return

    if calculate_crc(data[:-1]) != data[-1]:
        return

    force1 = struct.unpack(">H", data[3:5])[0]
    force2 = struct.unpack(">H", data[5:7])[0]

    force3 = struct.unpack(">H", data[7:9])[0]
    force4 = struct.unpack(">H", data[9:11])[0]

    force5 = struct.unpack(">H", data[11:13])[0]
    force6 = struct.unpack(">H", data[13:15])[0]


async def ble_loop():

    async with BleakClient(ADDRESS) as client:

        print("Conectado a ESP32")

        await client.start_notify(
            CHAR_UUID,
            notification_handler
        )

        while True:
            await asyncio.sleep(0.1)


def start_ble():
    asyncio.run(ble_loop())


threading.Thread(
    target=start_ble,
    daemon=True
).start()

# ==================================================
# SUPERFICIE 3D
# ==================================================

fig = plt.figure(figsize=(10, 8))

ax = fig.add_subplot(
    111,
    projection='3d'
)

# ==================================================
# MALLA
# ==================================================

x = np.linspace(0, 10, 80)
y = np.linspace(0, 12, 100)

X, Y = np.meshgrid(x, y)

# ==================================================
# POSICIONES ANATÓMICAS
# ==================================================

# Glúteos
sensor3_pos = np.array([3.2, 8.5])
sensor4_pos = np.array([6.8, 8.5])

# Isquiones
sensor1_pos = np.array([3.5, 6.0])
sensor2_pos = np.array([6.5, 6.0])

# Muslos
sensor5_pos = np.array([3.5, 2.5])
sensor6_pos = np.array([6.5, 2.5])

# ==================================================
# FUNCIONES GAUSSIANAS
# ==================================================

def gaussian(x, y, cx, cy, intensity, sigma):

    return intensity * np.exp(
        -(
            (x - cx) ** 2 +
            (y - cy) ** 2
        ) /
        (2 * sigma ** 2)
    )

# ==================================================
# TEXTO
# ==================================================

title = ax.set_title(
    "Mapa de presión en sedestación"
)

# ==================================================
# ACTUALIZACIÓN
# ==================================================

def update(frame):

    ax.clear()

    # ===== Isquiones =====
    Z_isq = (

        gaussian(
            X, Y,
            sensor1_pos[0],
            sensor1_pos[1],
            force1,
            sigma=0.9
        )

        +

        gaussian(
            X, Y,
            sensor2_pos[0],
            sensor2_pos[1],
            force2,
            sigma=0.9
        )
    )

    # ===== Glúteos =====
    Z_glu = (

        gaussian(
            X, Y,
            sensor3_pos[0],
            sensor3_pos[1],
            force3,
            sigma=1.8
        )

        +

        gaussian(
            X, Y,
            sensor4_pos[0],
            sensor4_pos[1],
            force4,
            sigma=1.8
        )
    )

    # ===== Muslos =====
    Z_mus = (

        gaussian(
            X, Y,
            sensor5_pos[0],
            sensor5_pos[1],
            force5,
            sigma=2.4
        )

        +

        gaussian(
            X, Y,
            sensor6_pos[0],
            sensor6_pos[1],
            force6,
            sigma=2.4
        )
    )

    Z = Z_isq + Z_glu + Z_mus

    ax.plot_surface(
        X,
        Y,
        Z,
        cmap="jet",
        linewidth=0.25,
        antialiased=True
    )

    left = force1 + force3 + force5
    right = force2 + force4 + force6

    diff = left - right

    if abs(diff) < 50:
        estado = "Equilibrado"
    elif diff > 0:
        estado = "Carga izquierda"
    else:
        estado = "Carga derecha"

    ax.set_title(
        f"Mapa de presión en sedestación\n{estado}"
    )

    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12)

    ax.set_zlim(0, max(
        100,
        force1,
        force2,
        force3,
        force4,
        force5,
        force6
    ) * 1.1)

    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_zticks([])

    ax.view_init(
        elev=35,
        azim=-60
    )

    return []

# ==================================================
# ANIMACIÓN
# ==================================================

ani = FuncAnimation(
    fig,
    update,
    interval=200,
    cache_frame_data=False
)

plt.show()