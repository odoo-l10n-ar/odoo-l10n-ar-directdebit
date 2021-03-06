# -*- coding: utf-8 -*-
from osv import fields,osv
from tools.translate import _
from openerp import netsvc
from datetime import date, datetime
from openerp.tools import DEFAULT_SERVER_DATE_FORMAT as D_FORMAT
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT as DT_FORMAT
import re
from StringIO import StringIO

eb_communication_line = "{bank_code:03d}"\
                        "{operation_code:02d}"\
                        "{date_due:6s}"\
                        "{directdebit_code:05d}"\
                        "{partner_id:<22s}"\
                        "{currency_code:1s}"\
                        "{cbu:022d}"\
                        "{amount:010d}"\
                        "{cuit:011d}"\
                        "{description:<10s}"\
                        "{document_id:<15s}\n"

be_communication_line = r"(?P<bank_id>.{3})"\
                        r"(?P<operation_code>.{2})"\
                        r"(?P<date_due>.{6})"\
                        r"(?P<directdebit_code>.{5})"\
                        r"(?P<partner_id>.{22})"\
                        r"(?P<currency_code>.{1})"\
                        r"(?P<cbu>.{22})"\
                        r"(?P<amount>.{10})"\
                        r"(?P<cuit>.{11})"\
                        r"(?P<description>.{10})"\
                        r"(?P<document_id>.{15})"\
                        r"(?P<response_code>.{3})"

re_be_communication_line = re.compile(be_communication_line)

currency_code_map = {
    'ARS': 'P',
    'USD': 'D',
}

ignore_symbol_chars = '-/\\'

def to_numeric(value):
    return int(value) if value and value.isnumeric() else 0

eb_communication_line_map = lambda l: {
    'bank_code': to_numeric(l.partner_bank_id.bank.bcra_code if l.partner_bank_id.bank else 0),
    'operation_code': 51,
    'date_due': datetime.strptime(l.communication_id.debit_date or l.invoice_id.date_due, D_FORMAT).strftime("%y%m%d"),
    'directdebit_code': l.communication_id.partner_bank_id.directdebit_code,
    'partner_id': "%05d" % l.partner_id.id,
    'currency_code': currency_code_map.get(l.invoice_id.currency_id.name, 'P'),
    'cbu': to_numeric(l.partner_bank_id.acc_number),
    'amount': int(l.invoice_id.amount_total * 100),
    'cuit': to_numeric(l.communication_id.company_id.partner_id.document_number),
    'description': (l.communication_id.line_description or l.invoice_id.name or '').encode('ascii','replace')[:10],
    'document_id': "%015i" % l.invoice_id.id,
#    'document_id': "%015i" % l.invoice_id.id,
    'document_id': l.invoice_id.number or 'ERROR',
    'response_code': '',
}

class directdebit_communication(osv.osv):
    _name = 'directdebit.communication'
    _inherit = 'directdebit.communication'

    def _get_credicoop_output(self, cr, uid, ids, fields, args, context=None):
        r = self.generate_output(cr, uid, ids, context=context)
        return r

    def _get_credicoop_input(self, cr, uid, ids, fields, args, context=None):
        #import pdb; pdb.set_trace()
        return {}

    def _set_credicoop_input(self, cr, uid, ids,
                             field_name, field_value, arg, context=None):
        dd_line_obj = self.pool.get('directdebit.communication.line')
        dd_input = field_value.decode('base64')
        if dd_input:
            dd_input = dd_input.split('\n')
            for line in dd_input:
                ml = re_be_communication_line.match(line)
                if ml:
                    data = ml.groupdict()
                    par_id = int(data['partner_id'])
                    amount = float(data['amount'])
                    dd_line_ids = dd_line_obj.search(cr, uid, [
                        ('id', '=', ids),
                        ('partner_id', '=', par_id),
                        ('amount', '=', amount)])
                    if len(dd_line_ids) == 1:
                        dd_line_obj.write(
                            cr, uid, dd_line_ids,
                            {'response_code': data['response_code']})

    _columns = {
        'credicoop_output': fields.function(_get_credicoop_output, type="binary", mode="model", string="File to send to credicoop", readonly="True", store=False),
        'credicoop_input': fields.function(_get_credicoop_input, fnct_inv = _set_credicoop_input, type="binary", mode="model", string="File from credicoop", store=False),
    }

    def generate_output(self, cr, uid, ids, context=None):
        r = {}
        for com in self.browse(cr, uid, ids):
            if com.state == 'draft':
                r[com.id] = None
                continue
            out = StringIO()
            for line in com.line_ids:
                ml = eb_communication_line_map(line)
                ol = eb_communication_line.format(**ml)
                out.write(ol)
            r[com.id] = out.getvalue().encode('base64')
        return r

    def read_input(self, cr, uid, ids, context=None):
        #import pdb; pdb.set_trace()
        return {}

directdebit_communication()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
