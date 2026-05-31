"""Human keyboard pilot input (optional pynput)."""

from __future__ import annotations

from skymind_data.schema import ACTION_DIM


class KeyboardPilot:
    """Poll WASD/QE/throttle keys; returns SkyMind action vector."""

    def __init__(self) -> None:
        self._pressed: set[str] = set()
        self._throttle = 0.8
        self._feather = False
        self._listener = None
        self._available = False
        try:
            from pynput import keyboard

            self._keyboard = keyboard

            def on_press(key):
                name = _key_name(key)
                if name:
                    self._pressed.add(name)

            def on_release(key):
                name = _key_name(key)
                if name and name in self._pressed:
                    self._pressed.discard(name)

            self._listener = keyboard.Listener(on_press=on_press, on_release=on_release)
            self._listener.start()
            self._available = True
        except ImportError:
            pass

    @property
    def available(self) -> bool:
        return self._available

    def poll(self) -> list[float]:
        elevator = 0.0
        aileron = 0.0
        rudder = 0.0
        if "w" in self._pressed:
            elevator -= 0.3
        if "s" in self._pressed:
            elevator += 0.3
        if "a" in self._pressed:
            aileron -= 0.3
        if "d" in self._pressed:
            aileron += 0.3
        if "q" in self._pressed:
            rudder -= 0.3
        if "e" in self._pressed:
            rudder += 0.3
        if "up" in self._pressed:
            self._throttle = min(1.0, self._throttle + 0.02)
        if "down" in self._pressed:
            self._throttle = max(0.0, self._throttle - 0.02)
        if "f" in self._pressed:
            self._feather = True
        action = [self._throttle, elevator, aileron, rudder]
        while len(action) < ACTION_DIM:
            action.append(0.0)
        return action

    def feather_pressed(self) -> bool:
        val = self._feather
        self._feather = False
        return val

    def close(self) -> None:
        if self._listener is not None:
            self._listener.stop()


def _key_name(key) -> str | None:
    try:
        if hasattr(key, "char") and key.char:
            return key.char.lower()
    except Exception:
        pass
    name = str(key).replace("Key.", "").lower()
    if name in {"up", "down", "left", "right"}:
        return name
    return None


class NullKeyboardPilot:
    """Fallback when pynput unavailable."""

    def poll(self) -> list[float]:
        return [0.8, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]

    def feather_pressed(self) -> bool:
        return False

    def close(self) -> None:
        pass

    @property
    def available(self) -> bool:
        return False
