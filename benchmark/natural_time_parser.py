import re
from datetime import datetime, timedelta

class NaturalTimeParser:
    def __init__(self, now=None):
        self.now = now or datetime.now()
        self.time_units = {
            'minute': 60,
            'hour': 3600,
            'day': 86400,
            'week': 604800,
            'month': 2592000,  # approx
            'year': 31536000   # approx
        }

    def parse(self, text):
        text = text.lower().strip()
        dt = self._parse_combined(text) or self._parse_relative(text) or \
             self._parse_absolute(text) or self._parse_day_of_week(text) or \
             self._parse_special_cases(text)

        if dt:
            return dt

        raise ValueError(f'Unable to parse time: {text}')

    def _parse_combined(self, text):
        # Handle "X at Y" format (e.g., "tomorrow at 5pm")
        if ' at ' in text:
            date_part, time_part = text.split(' at ', 1)
            base_date = self.parse(date_part)
            return self._parse_time(base_date, time_part)
        return None

    def _parse_relative(self, text):
        # Handle "in X units" format first
        in_match = re.match(r'^in\s+(\d+)\s*(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b', text)
        if in_match:
            amount = int(in_match.group(1))
            unit = in_match.group(2).rstrip('s')
            return self.now + self._get_timedelta(amount, unit)

        # Handle "X units ago/from now" format
        amount_match = re.match(
            r'^(\d+)\s*(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\s+(ago|from now)\b',
            text
        )
        if amount_match:
            amount = int(amount_match.group(1))
            unit = amount_match.group(2).rstrip('s')
            direction = -1 if amount_match.group(3) == 'ago' else 1
            return self.now + direction * self._get_timedelta(amount, unit)

        # Handle "next/last X units" format with optional quantity
        next_last_match = re.match(
            r'^(next|last)\s+(\d+)?\s*(seconds?|minutes?|hours?|days?|weeks?|months?|years?)\b',
            text
        )

        if next_last_match:
            direction = 1 if next_last_match.group(1) == 'next' else -1
            amount = int(next_last_match.group(2)) if next_last_match.group(2) else 1
            unit = next_last_match.group(3).rstrip('s')
            return self.now + direction * self._get_timedelta(amount, unit)

        return None

    def _parse_absolute(self, text):
        # Handle special keywords first
        if text == "midnight":
            return self.now.replace(hour=0, minute=0, second=0, microsecond=0)
        if text == "noon":
            return self.now.replace(hour=12, minute=0, second=0, microsecond=0)

        # Handle numeric time formats
        time_match = re.match(r'(\d+)(?::(\d+))?\s*(am|pm)?', text)
        if time_match:
            return self._parse_time(self.now, text)

        return None

    def _parse_day_of_week(self, text):
        # Patterns like "next monday" or "last friday"
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        match = re.match(r'(next|last|this)\s+(' + '|'.join(days) + ')', text)
        if match:
            direction = match.group(1)
            target_day = days.index(match.group(2))
            current_day = self.now.weekday()
            delta = target_day - current_day

            if direction == 'next':
                delta += 7 if delta <= 0 else 0
            elif direction == 'last':
                delta -= 7 if delta >= 0 else 0
            else:  # this
                delta = delta % 7

            return self.now + timedelta(days=delta)
        return None

    def _parse_special_cases(self, text):
        # Handle standalone "now" first
        if text == "now":
            return self.now

        # Track if we make any changes
        modified = False

        # Handle replacements
        if 'tomorrow' in text:
            text = text.replace('tomorrow', 'in 1 day')
            modified = True
        if 'yesterday' in text:
            text = text.replace('yesterday', '1 day ago')
            modified = True

        # Handle today removal
        new_text, count = re.subn(r'\btoday\b', '', text)
        if count > 0:
            text = new_text.strip()
            modified = True

        if not modified:
            return None  # Prevent recursion if no changes

        return self.parse(text) if text else None

    def _parse_time(self, base_date, time_str):
        # Parse time component and apply to base date
        time_match = re.match(r'(\d+)(?::(\d+))?\s*(am|pm)?', time_str)
        if not time_match:
            return base_date

        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        period = time_match.group(3)

        if period == 'pm' and hour < 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0

        return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def _get_timedelta(self, amount, unit):
        unit = unit.rstrip('s')  # normalize plural
        if unit in ['second', 'minute', 'hour', 'day']:
            return timedelta(**{f'{unit}s': amount})
        elif unit == 'week':
            return timedelta(days=amount*7)
        elif unit == 'month':
            return timedelta(days=amount*30)
        elif unit == 'year':
            return timedelta(days=amount*365)
        return timedelta(0)
