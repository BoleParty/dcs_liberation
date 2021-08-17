"""TACAN channel handling."""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterator, Set


class TacanUsage(Enum):
    TransmitReceive = "transmit receive"
    AirToAir = "air to air"


class TacanBand(Enum):
    X = "X"
    Y = "Y"

    def range(self) -> Iterator["TacanChannel"]:
        """Returns an iterator over the channels in this band."""
        return (TacanChannel(x, self) for x in range(1, 126 + 1))

    def valid_channels(self, usage: TacanUsage) -> Iterator["TacanChannel"]:
        for x in self.range():
            if x.number not in UNAVAILABLE[usage][self]:
                yield x


# Avoid certain TACAN channels for various reasons
# https://forums.eagle.ru/topic/276390-datalink-issue/
UNAVAILABLE = {
    TacanUsage.TransmitReceive: {
        TacanBand.X: set(range(2, 30 + 1)) | set(range(47, 63 + 1)),
        TacanBand.Y: set(range(2, 30 + 1)) | set(range(64, 92 + 1)),
    },
    TacanUsage.AirToAir: {
        TacanBand.X: set(range(1, 36 + 1)) | set(range(64, 99 + 1)),
        TacanBand.Y: set(range(1, 36 + 1)) | set(range(64, 99 + 1)),
    },
}


@dataclass(frozen=True)
class TacanChannel:
    number: int
    band: TacanBand

    def __str__(self) -> str:
        return f"{self.number}{self.band.value}"


class OutOfTacanChannelsError(RuntimeError):
    """Raised when all channels in this band have been allocated."""

    def __init__(self, band: TacanBand) -> None:
        super().__init__(f"No available channels in TACAN {band.value} band")


class TacanChannelInUseError(RuntimeError):
    """Raised when attempting to reserve an in-use channel."""

    def __init__(self, channel: TacanChannel) -> None:
        super().__init__(f"{channel} is already in use")


class TacanChannelForbiddenError(RuntimeError):
    """Raised when attempting to reserve a, for technical reasons, forbidden channel."""

    def __init__(self, channel: TacanChannel) -> None:
        super().__init__(f"{channel} is forbidden")


class TacanRegistry:
    """Manages allocation of TACAN channels."""

    def __init__(self) -> None:
        self.allocated_channels: Set[TacanChannel] = set()
        self.allocators: Dict[TacanBand, Dict[TacanUsage, Iterator[TacanChannel]]] = {}

        for band in TacanBand:
            self.allocators[band] = {}
            for usage in TacanUsage:
                self.allocators[band][usage] = band.valid_channels(usage)

    def alloc_for_band(
        self, band: TacanBand, intended_usage: TacanUsage
    ) -> TacanChannel:
        """Allocates a TACAN channel in the given band.

        Args:
            band: The TACAN band to allocate a channel for.
            intended_usage: What the caller intends to use the tacan channel for.

        Returns:
            A TACAN channel in the given band.

        Raises:
            OutOfTacanChannelsError: All channels compatible with the given radio are
                already allocated.
        """
        allocator = self.allocators[band][intended_usage]
        try:
            while (channel := next(allocator)) in self.allocated_channels:
                pass
            return channel
        except StopIteration:
            raise OutOfTacanChannelsError(band)

    def reserve(self, channel: TacanChannel, intended_usage: TacanUsage) -> None:
        """Reserves the given channel.

        Reserving a channel ensures that it will not be allocated in the future.

        Args:
            channel: The channel to reserve.
            intended_usage: What the caller intends to use the tacan channel for.

        Raises:
            TacanChannelInUseError: The given channel is already in use.
            TacanChannelForbiddenError: The given channel is forbidden.
        """
        if channel.number in UNAVAILABLE[intended_usage][channel.band]:
            raise TacanChannelForbiddenError(channel)
        if channel in self.allocated_channels:
            raise TacanChannelInUseError(channel)
        self.allocated_channels.add(channel)
