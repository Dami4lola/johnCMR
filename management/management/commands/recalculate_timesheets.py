from django.core.management.base import BaseCommand
from management.models import Timesheet


class Command(BaseCommand):
    help = 'Recalculate all timesheet payments based on current worker rates'

    def handle(self, *args, **options):
        timesheets = Timesheet.objects.all()
        count = 0

        for timesheet in timesheets:
            old_pay = timesheet.calculated_pay
            # Recalculate using current worker rates
            timesheet.calculated_pay = timesheet.calculate_payout()
            timesheet.save()
            count += 1

            if old_pay != timesheet.calculated_pay:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Updated {timesheet.worker.name} - {timesheet.job} '
                        f'from ${old_pay} to ${timesheet.calculated_pay}'
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nRecalculated {count} timesheet(s) successfully!'
            )
        )
