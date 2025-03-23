from Model.hospital_system import HospitalSystem

class HospitalController:
    def __init__(self, socketio):
        # Accept the socketio instance
        self.socketio = socketio

        # Create and initialize the hospital system
        self.system = HospitalSystem(self.socketio)
        self.system.initialize()
