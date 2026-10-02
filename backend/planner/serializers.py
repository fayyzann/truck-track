from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from rest_framework import serializers


class LogMetadataSerializer(serializers.Serializer):
    driver_name = serializers.CharField(required=False, allow_blank=True, max_length=120)
    carrier_name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    carrier_address = serializers.CharField(required=False, allow_blank=True, max_length=180)
    vehicle_numbers = serializers.CharField(required=False, allow_blank=True, max_length=120)
    shipping_document = serializers.CharField(required=False, allow_blank=True, max_length=120)


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
    departure_at = serializers.DateTimeField()
    terminal_timezone = serializers.CharField(max_length=80)
    log_metadata = LogMetadataSerializer(required=False, default=dict)

    def validate_terminal_timezone(self, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise serializers.ValidationError(
                "Use a valid IANA timezone, such as America/Chicago."
            ) from exc
        return value

    def validate_departure_at(self, value):
        if value.utcoffset() is None:
            raise serializers.ValidationError("Departure time must include a UTC offset.")
        return value
