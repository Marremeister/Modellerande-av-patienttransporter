WORK_LIMIT = 600  # 10 minutes
REST_DURATION = 180  # 3 minutes
LOUNGE = "Transporter Lounge"


class ShiftManager:
    def __init__(self, transporter, lounge_location="Transporter Lounge"):
        self.transporter = transporter
        self.lounge = lounge_location
        self.accumulated_work_time = 0.0  # seconds worked outside lounge
        self.resting = False
        self.rest_duration = 180  # simulated seconds to rest (e.g., 3 minutes)
        self.work_limit = 600     # simulated max before rest (e.g., 10 minutes)

    def update_work_time(self, seconds):
        """Add to work time if outside the lounge."""
        if self.transporter.current_location != self.lounge:
            self.accumulated_work_time += seconds

    def should_rest(self):
        return self.accumulated_work_time >= self.work_limit

    def begin_rest(self):
        self.resting = True
        print(f"🛌 {self.transporter.name} is now resting.")

    def end_rest(self):
        self.resting = False
        self.accumulated_work_time = 0.0
        print(f"☀️ {self.transporter.name} is back from rest.")
