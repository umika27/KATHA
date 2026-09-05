class InputAdapter:
    """Hardware-neutral boundary; the Pi team can supply microphone/touch adapters."""
    def begin_microphone_capture(self):
        raise NotImplementedError("Microphone capture is not wired in the software simulator")
