import os
import sys


def setup_django_settings() -> None:
	"""Configure Django settings so this script can run standalone."""
	current_dir = os.path.dirname(os.path.abspath(__file__))
	backend_dir = os.path.dirname(current_dir)
	if backend_dir not in sys.path:
		sys.path.insert(0, backend_dir)
	os.environ.setdefault("DJANGO_SETTINGS_MODULE", "AirlinePredictSystem.settings")


def delete_dirty_year_months(target_year_months: list[str]) -> int:
	"""Delete records in FlightMarketRecord where year_month is in target_year_months.

	Returns the number of deleted FlightMarketRecord rows.
	"""
	import django
	django.setup()

	from predict.models import FlightMarketRecord  # noqa: WPS433 – django import after setup

	queryset = FlightMarketRecord.objects.filter(year_month__in=target_year_months)
	to_delete_count = queryset.count()
	if to_delete_count == 0:
		return 0
	# queryset.delete() returns (num_deleted, {"app.Model": count, ...})
	deleted_count, _ = queryset.delete()
	return deleted_count


if __name__ == "__main__":
	setup_django_settings()
	targets = ["2024-06", "2024-07"]
	deleted = delete_dirty_year_months(targets)
	print(f"Deleted {deleted} rows where year_month in {targets}.")


