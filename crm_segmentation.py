# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from trytond.model import ModelView, ModelSQL, fields
from trytond.transaction import Transaction
from decimal import Decimal
import crm_operators

class CrmSegmentation(ModelSQL, ModelView):
    '''
        A segmentation is a tool to automatically assign categories on partys.
        These assignations are based on criterions.
    '''
    _name = "ekd.crm.segmentation"
    _description = "Party Segmentation"

    name = fields.Char('Name', size=64, required=True, help='The name of the segmentation.')
    description = fields.Text('Description')
    categ = fields.Many2One('party.category', 'party Category', required=True, help='The party category that will be added to partys that match the segmentation criterions after computation.')
    exclusif = fields.Boolean('Exclusive', help='Check if the category is limited to partys that match the segmentation criterions. If checked, remove the category from partys that doesn\'t match segmentation criterions')
    state = fields.Selection([('not running','Not Running'),('running','Running')], 'Execution Status', readonly=True)
    party = fields.Integer('Max party ID processed')
    segmentation_line = fields.One2Many('ekd.crm.segmentation.line', 'segmentation', 'Criteria', required=True)
    som_interval = fields.Integer('Days per Periode', help="A period is the average number of days between two cycle of sale or purchase for this segmentation. It's mainly used to detect if a party has not purchased or buy for a too long time, so we suppose that his state of mind has decreased because he probably bought goods to another supplier. Use this functionality for recurring businesses.")
    som_interval_max = fields.Integer('Max Interval', help="The computation is made on all events that occured during this interval, the past X periods.")
    som_interval_decrease = fields.Float('Decrease (0>1)', help="If the party has not purchased (or bought) during a period, decrease the state of mind by this factor. It\'s a multiplication")
    som_interval_default = fields.Float('Default (0=None)', help="Default state of mind for period preceeding the 'Max Interval' computation. This is the starting state of mind by default if the party has no event.")
    sales_purchase_active = fields.Boolean('Use The Sales Purchase Rules', help='Check if you want to use this tab as part of the segmentation rule. If not checked, the criteria beneath will be ignored')

    def __init__(self):
        super(CrmSegmentation, self).__init__()

        self._rpc.update({
            'button_process_start': True,
            'button_process_stop': True,
            'button_process_continue': True,
            })

    def default_party(self):
        return 0

    def default_state(self):
        return 'not running'

    def default_som_interval_max(self):
        return 3

    def default_som_interval_decrease(self):
        return Decimal('0.8')

    def default_som_interval_default(self):
        return Decimal('0.5')

    def button_process_continue(self, ids, start=False):
        cr = Transaction().cursor
        categs = self.read(ids,['category','exclusif','party', 'sales_purchase_active', 'profiling_active'])
        for categ in categs:
            if start:
                if categ['exclusif']:
                    cr.execute('delete from party_category_rel where category=%s', (categ['categ'][0],))

            id = categ['id']

            cr.execute('select id from res_party order by id ')
            partys = [x[0] for x in cr.fetchall()]

            if categ['sales_purchase_active']:
                to_remove_list=[]
                cr.execute('select id from ekd_crm_segmentation_line where segmentation=%s', (id,))
                line_ids = [x[0] for x in cr.fetchall()]

                for pid in partys:
                    if (not self.pool.get('ekd.crm.segmentation.line').test(cr, uid, line_ids, pid)):
                        to_remove_list.append(pid)
                for pid in to_remove_list:
                    partys.remove(pid)

            for party in partys:
                cr.execute('insert into party_category_rel (category,party) values (%s,%s)', (categ['categ'][0],party))
            cr.commit()

            self.write([id], {'state':'not running', 'party':0})
            cr.commit()
        return True

    def button_process_stop(self, ids, *args):
        return self.write(ids, {'state':'not running', 'party':0})

    def button_process_start(self, ids, *args):
        self.write(ids, {'state':'running', 'party':0})
        return self.process_continue(cr, uid, ids, start=True)

CrmSegmentation()

class CrmSegmentationLine(ModelSQL, ModelView):
    _name = "ekd.crm.segmentation.line"
    _description = "Segmentation line"

    name = fields.Char('Rule Name', size=64, required=True)
    segmentation = fields.Many2One('ekd.crm.segmentation', 'Segmentation')
    expr_name = fields.Selection([('sale','Sale Amount'),('som','State of Mind'),('purchase','Purchase Amount')], 'Control Variable', required=True)
    expr_operator = fields.Selection([('<','<'),('=','='),('>','>')], 'Operator', required=True)
    expr_value = fields.Float('Value', required=True)
    operator = fields.Selection([('and','Mandatory Expression'),('or','Optional Expression')],'Mandatory / Optional', required=True)

    def defaults_expr_name(self):
        return 'sale'
    def defaults_expr_operator(self):
        return '>'

    def defaults_operator(self):
        return 'and'

    def test(self, cr, uid, ids, party):
        expression = {'<': lambda x,y: x<y, '=':lambda x,y:x==y, '>':lambda x,y:x>y}
        ok = False
        lst = self.read(cr, uid, ids)
        for l in lst:
            cr.execute('select * from ir_module_module where name=%s and state=%s', ('account','installed'))
            if cr.fetchone():
                if l['expr_name']=='som':
                    datas = self.pool.get('crm.segmentation').read(cr, uid, [l['segmentation'][0]],
                            ['som','som_interval','som_interval_max','som_interval_default', 'som_interval_decrease'])
                    value = crm_operators.som(cr, uid, party, datas[0])
                elif l['expr_name']=='sale':
                    cr.execute('SELECT SUM(l.price_unit * l.quantity) ' \
                            'FROM account_invoice_line l, account_invoice i ' \
                            'WHERE (l.invoice = i.id) ' \
                                'AND i.party = %s '\
                                'AND i.type = \'out_invoice\'',
                            (party,))
                    value = cr.fetchone()[0] or 0.0
                    cr.execute('SELECT SUM(l.price_unit * l.quantity) ' \
                            'FROM account_invoice_line l, account_invoice i ' \
                            'WHERE (l.invoice = i.id) ' \
                                'AND i.party = %s '\
                                'AND i.type = \'out_refund\'',
                            (party,))
                    value -= cr.fetchone()[0] or 0.0
                elif l['expr_name']=='purchase':
                    cr.execute('SELECT SUM(l.price_unit * l.quantity) ' \
                            'FROM account_invoice_line l, account_invoice i ' \
                            'WHERE (l.invoice = i.id) ' \
                                'AND i.party = %s '\
                                'AND i.type = \'in_invoice\'',
                            (party,))
                    value = cr.fetchone()[0] or 0.0
                    cr.execute('SELECT SUM(l.price_unit * l.quantity) ' \
                            'FROM account_invoice_line l, account_invoice i ' \
                            'WHERE (l.invoice = i.id) ' \
                                'AND i.party = %s '\
                                'AND i.type = \'in_refund\'',
                            (party,))
                    value -= cr.fetchone()[0] or 0.0
                res = expression[l['expr_operator']](value, l['expr_value'])
                if (not res) and (l['operator']=='and'):
                    return False
                if res:
                    return True
        return True

CrmSegmentationLine()
