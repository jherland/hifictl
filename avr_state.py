from dataclasses import dataclass
from typing import FrozenSet, Optional

import avr_status


@dataclass
class AVR_State:
    """Encapsulate the current state of the Harman/Kardon AVR 430."""

    off: Optional[bool] = None
    standby: Optional[bool] = None
    muted: Optional[bool] = None
    volume: Optional[int] = None
    source: Optional[str] = None
    digital: Optional[str] = None
    surround: FrozenSet[str] = frozenset()
    channels: FrozenSet[str] = frozenset()
    speakers: FrozenSet[str] = frozenset()
    line1: Optional[str] = None
    line2: Optional[str] = None

    def __str__(self):
        props = []
        if self.off:
            props.append('off')
        elif self.standby:
            props.append('standby')
        else:
            if self.muted:
                props.append('muted')
            if self.volume is not None:
                props.append(f'{self.volume}dB')
            else:
                props.append('???dB')
            props.append('{}/{}/{}/{} -> {}'.format(
                self.source,
                self.digital,
                avr_status.channels_string(self.channels),
                avr_status.surround_string(self.surround),
                avr_status.speakers_string(self.speakers),
            ))
            props.append(f'"{self.line1}"')
            props.append(f'"{self.line2}"')
        return '<AVR_State ' + ' '.join(props) + '>'

    def json(self):
        """Return current state as JSON."""
        return {
            'off': self.off,
            'standby': self.standby,
            'muted': self.muted,
            'volume': self.volume,
            'source': self.source,
            'digital': self.digital,
            'surround': list(self.surround),
            'surround_string': avr_status.surround_string(self.surround),
            'surround_string_short':
                avr_status.surround_string_short(self.surround),
            'channels': list(self.channels),
            'channels_string': avr_status.channels_string(self.channels),
            'speakers': list(self.speakers),
            'speakers_string': avr_status.speakers_string(self.speakers),
            'speakers_string_short':
                avr_status.speakers_string_short(self.speakers),
            'line1': self.line1,
            'line2': self.line2,
        }

    def update(self, status):
        """Return a new state after folding in the given status update.

        If status is None, we assume the receiver is powered off.
        """
        d = self.__dict__.copy()

        if status is None:
            d['off'] = True
        d['off'] = False

        d['standby'] = status.standby
        d['muted'] = status.muted

        if status.volume is not None:
            d['volume'] = status.volume
        if status.source is not None:
            d['source'] = status.source
        if status.digital is not None:
            d['digital'] = status.digital

        if status.channels:
            d['channels'] = status.channels
        if status.surround:
            d['surround'] = status.surround
        if status.speakers:
            d['speakers'] = status.speakers

        if status.line1.strip() or not status.muted:
            d['line1'] = status.line1
        if status.line2.strip():
            d['line2'] = status.line2

        return self.__class__(**d)
