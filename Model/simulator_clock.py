import time
import eventlet


class SimulationClock:
    def __init__(self, speed_factor=10):
        self.start_time_real = time.time()
        self.speed_factor = speed_factor
        self._current_sim_time = 0
        self.running = False

    def start(self):
        if not self.running:
            self.running = True
            eventlet.spawn_n(self._run_clock)

    def _run_clock(self):
        while self.running:
            now_real = time.time()
            elapsed_real = now_real - self.start_time_real
            self._current_sim_time = elapsed_real * self.speed_factor
            eventlet.sleep(0.1)

    def get_time(self):
        return self._current_sim_time

    def stop(self):
        self.running = False
