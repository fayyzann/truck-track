from django.urls import path

from planner.views import HealthView, LocationSearchView, TripPlanView

urlpatterns = [
    path("health", HealthView.as_view(), name="health"),
    path("locations", LocationSearchView.as_view(), name="locations"),
    path("trips/plan", TripPlanView.as_view(), name="trip-plan"),
]
