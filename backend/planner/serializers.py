import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers


class LogMetadataSerializer(serializers.Serializer):
    driver_name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    carrier_name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    carrier_address = serializers.CharField(required=False, allow_blank=True, max_length=180)
    vehicle_numbers = serializers.CharField(required=False, allow_blank=True, max_length=120)
    shipping_document = serializers.CharField(required=False, allow_blank=True, max_length=120)


class OffsetDateTimeField(serializers.DateTimeField):
    default_error_messages = {
        **serializers.DateTimeField.default_error_messages,
        "offset": "Departure time must include a UTC offset.",
    }

    def to_internal_value(self, value):
        if isinstance(value, str) and not re.search(r"(?:Z|[+-]\d{2}:\d{2})$", value.strip()):
            self.fail("offset")
        return super().to_internal_value(value)


class TripPlanRequestSerializer(serializers.Serializer):
    current_location = serializers.CharField(max_length=240)
    pickup_location = serializers.CharField(max_length=240)
    dropoff_location = serializers.CharField(max_length=240)
    cycle_hours_used = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=0,
        max_value=70,
    )
    departure_at = OffsetDateTimeField()
    terminal_timezone = serializers.CharField(max_length=80)
    log_metadata = LogMetadataSerializer(required=False, default=dict)

    def validate_terminal_timezone(self, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ValueError, ZoneInfoNotFoundError) as exc:
            raise serializers.ValidationError(
                "Use a valid IANA timezone, such as America/Chicago."
            ) from exc
        return value

    def validate_departure_at(self, value):
        if not 1970 <= value.year <= 2100:
            raise serializers.ValidationError("Departure year must be between 1970 and 2100.")
        return value
