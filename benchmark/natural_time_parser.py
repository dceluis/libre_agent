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
        # Patterns like "3 hours ago" or "in 2 weeks"
        match = re.match(r'(\d+)\s*(minutes?|hours?|days?|weeks?|months?|years?)\s+(ago|from now)', text)
        if not match:
            match = re.match(r'(next|last)\s+(\d+)\s*(minutes?|hours?|days?|weeks?)', text)
            if match:
                direction = 1 if match.group(1) == 'next' else -1
                return self.now + direction * self._get_timedelta(
                    int(match.group(2)), match.group(3)
                )
            return None

        amount = int(match.group(1))
        unit = match.group(2).rstrip('s')  # normalize plural
        direction = -1 if match.group(3) == 'ago' else 1
        return self.now + direction * self._get_timedelta(amount, unit)

    def _parse_absolute(self, text):
        # Time formats like "5pm" or "17:30"
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
        text = text.replace('tomorrow', 'in 1 day').replace('yesterday', '1 day ago')
        text = re.sub(r'\btoday\b', '', text)
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
        if unit in ['minute', 'hour', 'day']:
            return timedelta(**{f'{unit}s': amount})
        elif unit == 'week':
            return timedelta(days=amount*7)
        elif unit == 'month':
            return timedelta(days=amount*30)
        elif unit == 'year':
            return timedelta(days=amount*365)
        return timedelta(0)
