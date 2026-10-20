from individual.models import Group, GroupIndividual
from payroll.models import BenefitAttachment, BenefitConsumption


def _primary_recipients(group_ids):
    names = {}
    rows = (GroupIndividual.objects
            .filter(group_id__in=group_ids, is_deleted=False, recipient_type='PRIMARY')
            .values_list('group_id', 'individual__first_name', 'individual__last_name'))
    for group_id, first, last in rows:
        name = f"{first or ''} {last or ''}".strip()
        if name:
            names.setdefault(str(group_id), name)
    return names


def _primary_accounts(group_ids):
    try:
        from tasaf_payment.models import PaymentAccount
    except ImportError:
        return {}
    accounts = {}
    rows = (PaymentAccount.objects
            .filter(group_beneficiary__group_id__in=group_ids, is_primary=True, is_deleted=False)
            .values_list('group_beneficiary__group_id', 'fsp_name', 'account_number'))
    for group_id, fsp, account in rows:
        accounts.setdefault(str(group_id), (fsp or '', account or ''))
    return accounts


def payment_slip_rows(payroll):
    benefits = list(BenefitConsumption.objects
                    .filter(payrollbenefitconsumption__payroll=payroll,
                            payrollbenefitconsumption__is_deleted=False, is_deleted=False)
                    .order_by('code')
                    .values_list('id', 'code', 'amount', 'json_ext',
                                 'individual__first_name', 'individual__last_name'))
    bills = {}
    for benefit_id, code, total in (BenefitAttachment.objects
                                    .filter(benefit_id__in=[b[0] for b in benefits], is_deleted=False)
                                    .values_list('benefit_id', 'bill__code', 'bill__amount_total')):
        bills.setdefault(benefit_id, (code, total))

    group_ids = {str((ext or {}).get('beneficiary_group_id')) for _, _, _, ext, _, _ in benefits
                 if (ext or {}).get('beneficiary_group_id')}
    groups = {str(row[0]): row[1:] for row in Group.objects.filter(id__in=group_ids).values_list(
        'id', 'code', 'location__name', 'location__parent__name', 'location__parent__parent__name')}
    representatives = _primary_recipients(group_ids)
    accounts = _primary_accounts(group_ids)

    rows = []
    for benefit_id, code, amount, ext, first, last in benefits:
        ext = ext or {}
        group_id = str(ext.get('beneficiary_group_id') or '')
        hhid, village, ward, council = groups.get(group_id, ('', '', '', ''))
        bill_code, bill_total = bills.get(benefit_id, (None, None))
        fsp, account = accounts.get(group_id, ('', ''))
        payee = f"{first or ''} {last or ''}".strip()
        rows.append({
            'payCode': bill_code or code or '',
            'code': code or '',
            'hhid': hhid or '',
            'payee': payee,
            'representative': representatives.get(group_id) or payee,
            'amount': float(bill_total if bill_total is not None else amount or 0),
            'breakdown': ext.get('pct_breakdown') or {},
            'village': village or '',
            'ward': ward or '',
            'council': council or '',
            'fsp': fsp,
            'account': account,
        })
    return rows
