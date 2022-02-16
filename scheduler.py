import datetime
import logging

# TODO: Allow specifying a source "local" or "remote" along with schedules

# Scheduling: A time range, associated with a temperature range
class Schedule:
    def __init__(self, default_range=[70, 72, 1]):

        self.log = logging.getLogger("Schedule")
        self.log.setLevel(logging.DEBUG)
        self.log.info("Schedule object being created")

        self.times = []
        self.temps = []

        self.add_range(default_range, "default")

    def get_current_target_temp_range(self, current_time=None):
        """Obtains the target temperature for the current time. Returns the default if no match is found."""

        current_range = self.default_range

        # You shouldn't pass a time in general, but this lets me test it more easily.
        if current_time is None:
            current_time = datetime.datetime.now().time()

        for time_idx, time_range in enumerate(self.times):
            if time_range[0] < current_time <= time_range[1]:
                current_range = self.temps[time_idx]
                break
            else:
                pass

        return current_range

    def add_range(self, temp_range, time_range, t_src=0):

        thermometer_source = ["local", "remote"][t_src]

        self.log.info("Adding schedule")

        # Allow setting a default range, in case no temp range has been set for the current time
        if time_range == "default":
            self.log.info(f"Setting default range to {temp_range}")
            self.default_range = temp_range
            return

        else:

            # If the time interval spans midnight, split it up into two
            midnight_pm = datetime.time(23, 59)
            midnight_am = datetime.time(0, 0)
            # TODO: Best way to handle midnight crossover? I can automatically split a time range that crosses midnight
            #   but that's a little janky
            # This is a hell of an if statement
            if midnight_pm > time_range[0] > time_range[1] > midnight_am:

                # Split the time range [start, end] into [start, midnight] [midnight, end]
                new_ranges = [
                    [time_range[0], midnight_pm],
                    [datetime.time(0, 0), time_range[1]],
                ]

                # And add as two independent schedule entries
                for time_range in new_ranges:
                    self.log.info(f"Adding range {time_range} with a midnight split")
                    self.times.append(time_range)
                    self.temps.append(temp_range)

            else:
                # Add the new time and temp ranges
                self.log.info(f"Adding time range {time_range}")
                self.times.append(time_range)
                self.temps.append(temp_range)

                # Make sure these lists didn't get out of whack somehow
                assert len(self.times) == len(self.temps)

            # TODO: Check that the current time range doesn't overlap anything existing...
            # TODO: Validate that time_range and temp_range are legitimate
            #   Time_range should both be times.
            #   Temp_range should have valid temps, and a valid hysteresis

            return

    def clear_ranges(self):

        self.log.info("Clearing schedule ranges")

        self.times = []
        self.temps = []
