from django.db.models import Count
from django.test import TestCase

from individual.models import Group
from payroll.models import BenefitConsumption, Payroll
from payroll.payment_slips import payment_slip_rows


class PaymentSlipRowsDbTest(TestCase):
    def setUp(self):
        self.payroll = (Payroll.objects.filter(is_deleted=False)
                        .annotate(n=Count('payrollbenefitconsumption')).filter(n__gt=0).order_by('-n', 'id').first())
        if self.payroll is None:
            self.skipTest('needs a payroll with benefits')
        self.rows = payment_slip_rows(self.payroll)

    def test_one_row_per_benefit_with_its_amount(self):
        benefits = BenefitConsumption.objects.filter(
            payrollbenefitconsumption__payroll=self.payroll,
            payrollbenefitconsumption__is_deleted=False, is_deleted=False)
        self.assertEqual(len(self.rows), benefits.count())
        self.assertTrue(all(row['amount'] > 0 for row in self.rows if row['amount'] is not None))

    def test_location_comes_from_the_household(self):
        benefit = BenefitConsumption.objects.filter(
            payrollbenefitconsumption__payroll=self.payroll, is_deleted=False,
            json_ext__has_key='beneficiary_group_id').order_by('code').first()
        if benefit is None:
            self.skipTest('no benefit linked to a household')
        group = Group.objects.select_related('location__parent__parent').get(
            id=benefit.json_ext['beneficiary_group_id'])
        row = next(r for r in self.rows if r['code'] == benefit.code)
        self.assertEqual((row['hhid'], row['village']), (group.code, group.location.name))
        self.assertEqual(row['ward'], group.location.parent.name)
        self.assertEqual(row['council'], group.location.parent.parent.name)
