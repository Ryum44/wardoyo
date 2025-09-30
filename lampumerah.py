# ===============================================================
# Simulasi Lampu Lalu Lintas 4-Arah Two-Way + BELOK
# ===============================================================
# • Tiap ruas jalan 2 arah terpisah
# • Timer lampu stabil 1 detik / tick
# • Mobil bisa belok kiri / kanan / lurus
# • Garis pembatas putih
# • Slider kecepatan & night-mode
# ===============================================================

import tkinter as tk
import random
import time
import threading

CLR_BG   = "#2e3f4f"
CLR_ROAD = "#404040"
CLR_CAR  = ["#e74c3c", "#3498db", "#2ecc71", "#f1c40f", "#9b59b6", "#34495e"]

PHASES   = {"green": 10, "yellow": 2, "red": 12}
LANE_WIDTH = 120          # lebar satu jalur arah
INTERP_STEPS = 20         # smoothness belokan

class TrafficLightGUI:
    def __init__(self, root):
        self.root = root
        root.title("Simulasi Lampu Lalu Lintas 4-Arah Two-Way + Belok")
        root.configure(bg=CLR_BG)
        self.canvas_w = 700
        self.canvas_h = 700
        self.center_x = self.canvas_w // 2
        self.center_y = self.canvas_h // 2

        # --- Frame Kontrol ---
        ctrl = tk.Frame(root, bg=CLR_BG)
        ctrl.pack(pady=10)

        tk.Button(ctrl, text="Start",  width=8, command=self.start).grid(row=0, column=0, padx=5)
        tk.Button(ctrl, text="Stop",   width=8, command=self.stop).grid(row=0, column=1, padx=5)
        tk.Button(ctrl, text="Reset",  width=8, command=self.reset).grid(row=0, column=2, padx=5)

        self.night_mode = False
        self.btn_night = tk.Button(ctrl, text="🌙", width=4, command=self.toggle_night)
        self.btn_night.grid(row=0, column=3, padx=10)

        # Slider kecepatan
        tk.Label(ctrl, text="Kecepatan:", fg="white", bg=CLR_BG).grid(row=1, column=0, pady=5)
        self.speed_var = tk.DoubleVar(value=2.0)
        tk.Scale(ctrl, from_=0.5, to=5, resolution=0.5, orient="horizontal",
                 variable=self.speed_var, bg=CLR_BG, fg="white",
                 troughcolor="#555").grid(row=1, column=1, columnspan=3, sticky="ew", padx=5)

        # --- Canvas ---
        self.canvas = tk.Canvas(root, width=self.canvas_w, height=self.canvas_h,
                                bg="#1e1e1e", highlightthickness=0)
        self.canvas.pack()
        self.draw_road()

        # Lampu
        offset = 80
        self.light_pos = {
            "Utara": (self.center_x, offset),
            "Timur": (self.canvas_w - offset, self.center_y),
            "Selatan": (self.center_x, self.canvas_h - offset),
            "Barat": (offset, self.center_y)
        }
        self.lights = {}
        for name, (x, y) in self.light_pos.items():
            self.lights[name] = {
                "circle": self.canvas.create_oval(x-25, y-25, x+25, y+25, fill="black"),
                "label":  self.canvas.create_text(x, y+35, text=name, fill="white", font=("Arial", 10)),
                "timer":  self.canvas.create_text(x, y+50, text="", fill="white", font=("Arial", 9))
            }

        self.dirs = ["Utara", "Timur", "Selatan", "Barat"]
        self.lights_state = {}
        self.current_green = "Utara"
        self.sequence_index = 0
        self.reset_lights()

        # Timer absolut
        self.next_light_change = time.monotonic() + 1.0
        self.spawn_timer = time.monotonic()

        self.cars = []
        self.running = False

    # ---------- jalan ----------
    def draw_road(self):
        r = 120
        # horizontal
        self.canvas.create_rectangle(0, self.center_y - r,
                                     self.canvas_w, self.center_y + r,
                                     fill=CLR_ROAD, outline="")
        # vertical
        self.canvas.create_rectangle(self.center_x - r, 0,
                                     self.center_x + r, self.canvas_h,
                                     fill=CLR_ROAD, outline="")
        # garis pembatas dua arah
        self.canvas.create_line(0, self.center_y,
                                self.center_x - r, self.center_y,
                                fill="white", width=2)
        self.canvas.create_line(self.center_x + r, self.center_y,
                                self.canvas_w, self.center_y,
                                fill="white", width=2)
        self.canvas.create_line(self.center_x, 0,
                                self.center_x, self.center_y - r,
                                fill="white", width=2)
        self.canvas.create_line(self.center_x, self.center_y + r,
                                self.center_x, self.canvas_h,
                                fill="white", width=2)

    # ---------- lampu ----------
    def reset_lights(self):
        for d in self.dirs:
            if d == self.current_green:
                self.lights_state[d] = {"color": "green", "remain": PHASES["green"]}
            else:
                self.lights_state[d] = {"color": "red", "remain": PHASES["red"]}
        self.update_lights_display()

    def update_lights_display(self):
        for d, data in self.lights_state.items():
            self.canvas.itemconfig(self.lights[d]["circle"], fill=data["color"])
            self.canvas.itemconfig(self.lights[d]["timer"], text=str(data["remain"]))

    def update_lights(self):
        now = time.monotonic()
        if now < self.next_light_change:
            return
        self.next_light_change = now + 1.0

        for d, data in self.lights_state.items():
            if data["remain"] > 0:
                data["remain"] -= 1
                continue
            if data["color"] == "green":
                data.update({"color": "yellow", "remain": PHASES["yellow"]})
            elif data["color"] == "yellow":
                data.update({"color": "red", "remain": PHASES["red"]})
                self.sequence_index = (self.sequence_index + 1) % len(self.dirs)
                self.current_green = self.dirs[self.sequence_index]
                self.lights_state[self.current_green].update(
                    {"color": "green", "remain": PHASES["green"]})
        self.update_lights_display()

    # ---------- mobil ----------
    def get_turn_vector(self, tgt):
        return {"Utara": (0, 1), "Timur": (-1, 0),
                "Selatan": (0, -1), "Barat": (1, 0)}[tgt]

    def spawn_car(self):
        now = time.monotonic()
        if now - self.spawn_timer < 1.5 or len(self.cars) >= 24:
            return
        self.spawn_timer = now

        src = random.choice(self.dirs)
        color = random.choice(CLR_CAR)
        speed = self.speed_var.get() * random.uniform(0.8, 1.2)

        turn = random.choices(["left", "straight", "right"],
                              weights=[0.25, 0.5, 0.25])[0]

        idx = self.dirs.index(src)
        if turn == "left":
            tgt = self.dirs[(idx + 1) % 4]
        elif turn == "right":
            tgt = self.dirs[(idx - 1) % 4]
        else:
            tgt = self.dirs[(idx + 2) % 4]

        lane_offset = -60 if src in ("Utara", "Timur") else 60
        if src == "Utara":
            y_spawn, x_lane = (-20, self.center_x + lane_offset) if tgt != "Utara" else (-20, self.center_x - lane_offset)
            car = {"x": x_lane, "y": y_spawn, "dx": 0, "dy": 1, "dir": src, "target_dir": tgt,
                   "color": color, "speed": speed, "state": "straight", "step": 0}
        elif src == "Timur":
            x_spawn, y_lane = (self.canvas_w + 20, self.center_y + lane_offset) if tgt != "Timur" else (self.canvas_w + 20, self.center_y - lane_offset)
            car = {"x": x_spawn, "y": y_lane, "dx": -1, "dy": 0, "dir": src, "target_dir": tgt,
                   "color": color, "speed": speed, "state": "straight", "step": 0}
        elif src == "Selatan":
            y_spawn, x_lane = (self.canvas_h + 20, self.center_x + lane_offset) if tgt != "Selatan" else (self.canvas_h + 20, self.center_x - lane_offset)
            car = {"x": x_lane, "y": y_spawn, "dx": 0, "dy": -1, "dir": src, "target_dir": tgt,
                   "color": color, "speed": speed, "state": "straight", "step": 0}
        else:  # Barat
            x_spawn, y_lane = (-20, self.center_y + lane_offset) if tgt != "Barat" else (-20, self.center_y - lane_offset)
            car = {"x": x_spawn, "y": y_lane, "dx": 1, "dy": 0, "dir": src, "target_dir": tgt,
                   "color": color, "speed": speed, "state": "straight", "step": 0}

        car["item"] = self.canvas.create_rectangle(
            car["x"] - 15, car["y"] - 15,
            car["x"] + 15, car["y"] + 15,
            fill=car["color"], outline="")
        self.cars.append(car)

    def should_stop(self, car):
        light = self.lights_state[car["dir"]]
        if light["color"] == "green":
            return False
        stop_dist = 140
        cx, cy = self.center_x, self.center_y
        if car["dir"] == "Utara" and cy - stop_dist <= car["y"] <= cy - stop_dist + 20:
            return True
        if car["dir"] == "Timur" and cx + stop_dist - 40 <= car["x"] <= cx + stop_dist:
            return True
        if car["dir"] == "Selatan" and cy + stop_dist - 20 <= car["y"] <= cy + stop_dist:
            return True
        if car["dir"] == "Barat" and cx - stop_dist <= car["x"] <= cx - stop_dist + 20:
            return True
        return False

    def car_ahead(self, car):
        for other in self.cars:
            if other is car or other["dir"] != car["dir"] or other["state"] == "turning":
                continue
            dx = other["x"] - car["x"]
            dy = other["y"] - car["y"]
            dist = dx * car["dx"] + dy * car["dy"]
            if 0 < dist < 35:
                return True
        return False

    def move_cars(self):
        for car in self.cars[:]:
            if car["state"] == "turning":
                if car["step"] < INTERP_STEPS:
                    t = car["step"] / INTERP_STEPS
                    x = car["turn_start_x"] + t * (car["turn_end_x"] - car["turn_start_x"])
                    y = car["turn_start_y"] + t * (car["turn_end_y"] - car["turn_start_y"])
                    self.canvas.coords(car["item"], x-15, y-15, x+15, y+15)
                    car["step"] += 1
                    continue
                else:
                    car["state"] = "straight"
                    car["dx"], car["dy"] = car["final_dx"], car["final_dy"]
                    car["x"], car["y"] = car["turn_end_x"], car["turn_end_y"]

            if self.should_stop(car) or self.car_ahead(car):
                continue

            car["x"] += car["dx"] * car["speed"]
            car["y"] += car["dy"] * car["speed"]
            self.canvas.coords(car["item"],
                               car["x"] - 15, car["y"] - 15,
                               car["x"] + 15, car["y"] + 15)

            # cek belok
            if car["target_dir"] != car["dir"] and car["state"] == "straight":
                dist = abs(car["x"] - self.center_x) + abs(car["y"] - self.center_y)
                if dist < 20:
                    car["state"] = "turning"
                    car["step"] = 0
                    car["turn_start_x"] = car["x"]
                    car["turn_start_y"] = car["y"]
                    car["final_dx"], car["final_dy"] = self.get_turn_vector(car["target_dir"])
                    # titik akhir belok
                    if car["target_dir"] == "Utara":
                        car["turn_end_x"], car["turn_end_y"] = car["x"], car["y"] + 30
                    elif car["target_dir"] == "Timur":
                        car["turn_end_x"], car["turn_end_y"] = car["x"] - 30, car["y"]
                    elif car["target_dir"] == "Selatan":
                        car["turn_end_x"], car["turn_end_y"] = car["x"], car["y"] - 30
                    elif car["target_dir"] == "Barat":
                        car["turn_end_x"], car["turn_end_y"] = car["x"] + 30, car["y"]

            margin = 30
            if (car["x"] < -margin or car["x"] > self.canvas_w + margin or
                car["y"] < -margin or car["y"] > self.canvas_h + margin):
                self.canvas.delete(car["item"])
                self.cars.remove(car)

    # ---------- kontrol ----------
    def start(self):
        if not self.running:
            self.running = True
            threading.Thread(target=self.loop, daemon=True).start()

    def stop(self):
        self.running = False

    def reset(self):
        self.stop()
        for c in self.cars:
            self.canvas.delete(c["item"])
        self.cars.clear()
        self.current_green = "Utara"
        self.sequence_index = 0
        self.reset_lights()
        self.next_light_change = time.monotonic() + 1.0

    def toggle_night(self):
        self.night_mode = not self.night_mode
        bg = "#0d1117" if self.night_mode else "#1e1e1e"
        self.canvas.config(bg=bg)
        self.btn_night.config(text="☀️" if self.night_mode else "🌙")

    # ---------- thread ----------
    def loop(self):
        while self.running:
            self.update_lights()
            self.move_cars()
            self.spawn_car()
            time.sleep(0.05)

if __name__ == "__main__":
    root = tk.Tk()
    TrafficLightGUI(root)
    root.mainloop()
