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
from trytond.pyson import Equal, Eval, Not, PYSONEncoder, Date
from trytond.transaction import Transaction
import logging
import datetime
import base64
import time

MAX_LEVEL = 15
AVAILABLE_STATES = [
    ('draft','Draft'),
    ('open','Open'),
    ('cancel', 'Cancel'),
    ('done', 'Close'),
    ('pending','Pending')
]

AVAILABLE_PRIORITIES = [
    ('5','Lowest'),
    ('4','Low'),
    ('3','Normal'),
    ('2','High'),
    ('1','Highest')
]

icon_lst = {
    'form':'STOCK_NEW',
    'tree':'STOCK_JUSTIFY_FILL',
    'calendar':'STOCK_SELECT_COLOR'
}

class CrmCaseSection(ModelSQL, ModelView):
    _name = "ekd.crm.case.section"
    _description = "Case Section"

    name = fields.Char('Case Section',size=64, required=True, translate=True)
    code = fields.Char('Section Code',size=8)
    active = fields.Boolean('Active')
    allow_unlink = fields.Boolean('Allow Delete', help="Allows to delete non draft cases")
    sequence = fields.Integer('Sequence')
    user = fields.Many2One('res.user', 'Responsible User')
    reply_to = fields.Char('Reply-To', size=64, help="The email address put in the 'Reply-To' of all emails sent by Open ERP about cases in this section")
    parent = fields.Many2One('ekd.crm.case.section', 'Parent Section')
    child_ids = fields.One2Many('ekd.crm.case.section', 'parent', 'Child Sections')

    def __init__(self):
        super(CrmCaseSection, self).__init__()

        self._constraints += [
            ('_check_recursion', 'Error ! You cannot create recursive sections.')
        ]
        self._sql_constraints += [
            ('code_uniq', 'unique (code)', 'The code of the section must be unique !')
        ]

        self._error_messages.update({
            'recursive_accounts': 'You can not create recursive accounts!',
        })

        self._order.insert(0, ('code', 'ASC'))
        self._order.insert(1, ('name', 'ASC'))


    def default_active(self):
        return True

    def default_allow_unlink(self):
        return True

    def _check_recursion(self, ids):
        cr = Transaction().cursor
        level = 100
        while len(ids):
            cr.execute('SELECT DISTINCT parent FROM ekd_crm_case_section '\
                       'WHERE id IN %s',
                       (tuple(ids),))
            ids = filter(None, map(lambda x:x[0], cr.fetchall()))
            if not level:
                return False
            level -= 1
        return True

    # Mainly used by the wizard
    def menu_create_data(self, data, menu_lst):
        menus = {}
        menus[0] = data['menu_parent']
        section = self.browse(data['section'])
        for (index, mname, mdomain, latest, view_mode) in menu_lst:
            view_mode = data['menu'+str(index)+'_option']
            if view_mode=='no':
                menus[index] = data['menu_parent']
                continue
            icon = icon_lst.get(view_mode.split(',')[0], 'STOCK_JUSTIFY_FILL')
            menu_id=self.pool.get('ir.ui.menu').create( {
                'name': data['menu'+str(index)],
                'parent': menus[latest],
                'icon': icon
            })
            menus[index] = menu_id
            action_id = self.pool.get('ir.actions.act_window').create( {
                'name': data['menu'+str(index)],
                'res_model': 'ekd.crm.case',
                'domain': mdomain.replace('SECTION_ID', str(data['section'])),
                'view_type': 'form',
                'view_mode': view_mode,
            })
            seq = 0
            for mode in view_mode.split(','):
                self.pool.get('ir.actions.act_window.view').create( {
                    'sequence': seq,
                    'view_id': data['view_'+mode],
                    'view_mode': mode,
                    'act_window_id': action_id,
                    'multi': True
                })
                seq+=1
            self.pool.get('ir.values').create( {
                'name': data['menu'+str(index)],
                'key2': 'tree_but_open',
                'model': 'ir.ui.menu',
                'res_id': menu_id,
                'value': 'ir.actions.act_window,%d'%action_id,
                'object': True
            })
        return True

    #
    # Used when called from .XML file
    #
    def menu_create(self, ids, name, menu_parent_id=False):
        menus = {}
        menus[-1] = menu_parent_id
        for section in self.browse( ids):
            for (index, mname, mdomain, latest) in [
                (0,'',"[('section','=',"+str(section.id)+")]", -1),
                (1,'My ',"[('section','=',"+str(section.id)+"),('user','=',uid)]", 0),
                (2,'My Unclosed ',"[('section','=',"+str(section.id)+"),('user','=',uid), ('state','<>','cancel'), ('state','<>','done')]", 1),
                (5,'My Open ',"[('section','=',"+str(section.id)+"),('user','=',uid), ('state','=','open')]", 2),
                (6,'My Pending ',"[('section','=',"+str(section.id)+"),('user','=',uid), ('state','=','pending')]", 2),
                (7,'My Draft ',"[('section','=',"+str(section.id)+"),('user','=',uid), ('state','=','draft')]", 2),

                (3,'My Late ',"[('section','=',"+str(section.id)+"),('user','=',uid), ('date_deadline','<=',time.strftime('%Y-%m-%d')), ('state','<>','cancel'), ('state','<>','done')]", 1),
                (4,'My Canceled ',"[('section','=',"+str(section.id)+"),('user','=',uid), ('state','=','cancel')]", 1),
                (8,'All ',"[('section','=',"+str(section.id)+"),]", 0),
                (9,'Unassigned ',"[('section','=',"+str(section.id)+"),('user','=',False)]", 8),
                (10,'Late ',"[('section','=',"+str(section.id)+"),('user','=',uid), ('date_deadline','<=',time.strftime('%Y-%m-%d')), ('state','<>','cancel'), ('state','<>','done')]", 8),
                (11,'Canceled ',"[('section','=',"+str(section.id)+"),('state','=','cancel')]", 8),
                (12,'Unclosed ',"[('section','=',"+str(section.id)+"),('state','<>','cancel'), ('state','<>','done')]", 8),
                (13,'Open ',"[('section','=',"+str(section.id)+"),('state','=','open')]", 12),
                (14,'Pending ',"[('section','=',"+str(section.id)+"),('state','=','pending')]", 12),
                (15,'Draft ',"[('section','=',"+str(section.id)+"),('state','=','draft')]", 12),
                (16,'Unassigned ',"[('section','=',"+str(section.id)+"),('user','=',False),('state','<>','cancel'),('state','<>','done')]", 12),
            ]:
                view_mode = 'tree,form'
                icon = 'STOCK_JUSTIFY_FILL'
                if index==0:
                    view_mode = 'form,tree'
                    icon = 'STOCK_NEW'
                menu_id=self.pool.get('ir.ui.menu').create( {
                    'name': mname+name,
                    'parent_id': menus[latest],
                    'icon': icon
                })
                menus[index] = menu_id
                action_id = self.pool.get('ir.actions.act_window').create({
                    'name': mname+name+' Cases',
                    'res_model': 'ekd.crm.case',
                    'domain': mdomain,
                    'view_type': 'form',
                    'view_mode': view_mode,
                })
                self.pool.get('ir.values').create({
                    'name': 'Open Cases',
                    'key2': 'tree_but_open',
                    'model': 'ir.ui.menu',
                    'res_id': menu_id,
                    'value': 'ir.actions.act_window,%d'%action_id,
                    'object': True
                })
        return True

    def name_get(self, ids):
        if not len(ids):
            return []
        reads = self.read( ids, ['name','parent_id'])
        res = []
        for record in reads:
            name = record['name']
            if record['parent_id']:
                name = record['parent_id'][1]+' / '+name
            res.append((record['id'], name))
        return res

CrmCaseSection()

class CrmCaseCategory(ModelSQL, ModelView):
    _name = "ekd.crm.case.category"
    _description = "Category of case"

    name = fields.Char('Case Category Name', size=64, required=True, translate=True)
    probability = fields.Float('Probability (%)', required=True)
    section = fields.Many2One('ekd.crm.case.section', 'Case Section')

    def default_probability(self):
        return 0.0

CrmCaseCategory()

class CrmCaseRule(ModelSQL, ModelView):
    _name = "ekd.crm.case.rule"
    _description = "Case Rule"

    name = fields.Char('Rule Name',size=64, required=True)
    active = fields.Boolean('Active')
    sequence = fields.Integer('Sequence')

    trg_state_from = fields.Selection([('',''),('escalate','Escalate')]+AVAILABLE_STATES, 'Case State')
    trg_state_to = fields.Selection([('',''),('escalate','Escalate')]+AVAILABLE_STATES, 'Button Pressed')

    trg_date_type = fields.Selection([
            ('none','None'),
            ('create','Creation Date'),
            ('action_last','Last Action Date'),
            ('deadline','Deadline'),
            ('date','Date'),
            ], 'Trigger Date')
    trg_date_range = fields.Integer('Delay after trigger date')
    trg_date_range_type = fields.Selection([('minutes', 'Minutes'),('hour','Hours'),('day','Days'),('month','Months')], 'Delay type')

    trg_section = fields.Many2One('ekd.crm.case.section', 'Section')
    trg_categ = fields.Many2One('ekd.crm.case.category', 'Category', domain=[('section','=',Eval('trg_section'))])
    trg_user = fields.Many2One('res.user', 'Responsible')

    trg_party = fields.Many2One('party.party', 'party')
    trg_party_categ = fields.Many2One('party.category', 'party Category')

    trg_priority_from = fields.Selection([('','')] + AVAILABLE_PRIORITIES, 'Minimum Priority')
    trg_priority_to = fields.Selection([('','')] + AVAILABLE_PRIORITIES, 'Maximim Priority')
    trg_max_history = fields.Integer('Maximum Communication History')

    act_method = fields.Char('Call Object Method', size=64)
    act_state = fields.Selection([('','')]+AVAILABLE_STATES, 'Set state to')
    act_section = fields.Many2One('ekd.crm.case.section', 'Set section to')
    act_user = fields.Many2One('res.user', 'Set responsible to')
    act_priority = fields.Selection([('','')] + AVAILABLE_PRIORITIES, 'Set priority to')
    act_email_cc = fields.Char('Add watchers (Cc)', size=250, help="These people will receive a copy of the futur communication between party and users by email")

    act_remind_party = fields.Boolean('Remind party', help="Check this if you want the rule to send a reminder by email to the party.")
    act_remind_user = fields.Boolean('Remind responsible', help="Check this if you want the rule to send a reminder by email to the user.")
    act_remind_attach = fields.Boolean('Remind with attachment', help="Check this if you want that all documents attached to the case be attached to the reminder email sent.")

    act_mail_to_user = fields.Boolean('Mail to responsible'),
    act_mail_to_party = fields.Boolean('Mail to party'),
    act_mail_to_watchers = fields.Boolean('Mail to watchers (Cc)'),
    act_mail_to_email = fields.Char('Mail to these emails', size=128),
    act_mail_body = fields.Text('Mail body')

    def __init__(self):
        super(CrmCaseRule, self).__init__()

        self._constraints += [
            ('_check_mail', 'Error: The mail is not well formated'),
        ]

        #self._constraints += [
        #    ('_check_recursion', 'Error ! You cannot create recursive sections.')
        #]
        #self._sql_constraints += [
        #    ('code_uniq', 'unique(code)', 'The code of the section must be unique !')
        #]

        #self._error_messages.update({
        #    'recursive_accounts': 'You can not create recursive accounts!',
        #})

        self._order.insert(0, ('sequence', 'ASC'))

    def default_active(self):
        return True

    def default_trg_date_type(self):
        return 'none'

    def default_trg_date_range_type(self):
        return 'day'

    def default_act_mail_to_user(self):
        return 0

    def default_act_remind_party(self):
        return 0

    def default_act_remind_user(self):
        return 0

    def default_act_mail_to_party(self):
        return 0

    def default_act_mail_to_watchers(self):
        return 0


    def _check(self, ids=False):
        '''
        Function called by the scheduler to process cases for date actions
        Only works on not done and cancelled cases
        '''
        cr.execute('select * from ekd_crm_case \
                where (date_action_last<%s or date_action_last is null) \
                and (date_action_next<=%s or date_action_next is null) \
                and state not in (\'cancel\',\'done\')',
                (time.strftime("%Y-%m-%d %H:%M:%S"),
                    time.strftime('%Y-%m-%d %H:%M:%S')))
        ids2 = map(lambda x: x[0], cr.fetchall() or [])
        case_obj = self.pool.get('ekd.crm.case')
        cases = case_obj.browse( ids2)
        return case_obj._action( cases, False, context=context)

    def _check_mail(self, ids):
        caseobj = self.pool.get('ekd.crm.case')
        emptycase = orm.browse_null()
        for rule in self.browse( ids):
            if rule.act_mail_body:
                try:
                    caseobj.format_mail(emptycase, rule.act_mail_body)
                except (ValueError, KeyError, TypeError):
                    return False
        return True


CrmCaseRule()

class CrmCase(ModelSQL, ModelView):
    _name = "ekd.crm.case"
    _description = "Case"

    id = fields.Integer('ID', readonly=True)
    name = fields.Char('Description',size=64,required=True)
    priority = fields.Selection(AVAILABLE_PRIORITIES, 'Priority')
    active = fields.Boolean('Active')
    description = fields.Text('Your action')
    section = fields.Many2One('ekd.crm.case.section', 'Section', required=True, select=True)
    category = fields.Many2One('ekd.crm.case.category', 'Category', 
                on_change=['category'], required=True,
                domain=[('section','=',Eval('section'))])
    planned_revenue = fields.Float('Planned Revenue')
    planned_cost = fields.Float('Planned Costs')
    probability = fields.Float('Probability (%)')
    email_from = fields.Char('party Email', size=128)
    email_cc = fields.Char('Watchers Emails', size=252)
    email_last = fields.Function(fields.Text('Latest E-Mail'), '_email_last')
    party = fields.Many2One('party.party', 'Party')
    party_address = fields.Many2One('party.address', 'Party Contact', domain=[('party','=',Eval('party'))])
    som = fields.Many2One('ekd.party.som', 'State of Mind')
    date = fields.DateTime('Date')
    create_date = fields.DateTime('Created' ,readonly=True)
    date_deadline = fields.DateTime('Deadline')
    date_closed = fields.DateTime('Closed', readonly=True)
    channel = fields.Many2One('ekd.party.channel', 'Channel')
    user = fields.Many2One('res.user', 'Responsible')
    history_line = fields.One2Many('ekd.crm.case.history', 'case', 'Communication', readonly=1)
    log_ids = fields.One2Many('ekd.crm.case.log', 'case', 'Logs History', readonly=1)
    state = fields.Selection(AVAILABLE_STATES, 'State', readonly=True)
    ref = fields.Reference('Reference', '_links_get')
    ref2 = fields.Reference('Reference 2', '_links_get')

    date_action_last = fields.DateTime('Last Action', readonly=1)
    date_action_next = fields.DateTime('Next Action', readonly=1)

    def __init__(self):
        super(CrmCase, self).__init__()

        self._rpc.update({
            'button_case_log': True,
            'button_add_reply': True,
            'button_case_log_reply': True,
            'button_case_close': True,
            'button_case_open': True,
            'button_case_pending': True,
            'button_case_escalate': True,
            'button_case_reset': True,
            'button_case_cancel': True,
            'button_remind_party': True,
            'button_remind_user': True,
            })

        self._order.insert(0, ('priority', 'ASC'))
        self._order.insert(1, ('date_deadline', 'DESC'))
        self._order.insert(2, ('date', 'DESC'))
        self._order.insert(3, ('id', 'DESC'))

    def _email_last(self, ids, name, arg):
        res = {}
        for case in self.browse(ids):
            if case.history_line:
                res[case.id] = case.history_line[0].description
            else:
                res[case.id] = False
        return res

    def copy(self, id, default=None):
        if not default: default = {}
        default.update( {'state':'draft', 'id':False, 'history_line':[],'log_ids':[]})
        return super(crm_case, self).copy( id, default)

    def default_active(self):
        return True

#    def default_user(self):
#        return Transaction().user

#    def default_party(self):
#        user = self.pool.get('res.user').browse(Transaction().user)
#        if not user.address:
#            return False
#        return user.address.party.id

#    def default_party_address(self):
#        return self.pool.get('res.user').browse(Transaction().user).address.id

#    def default_email_from(self):
#        context = Transaction().context
#        if not context.get('portal',False):
#            return False
#        user = self.pool.get('res.user').browse(Transaction().user)
#        if not user.address:
#            return False
#        raise Exception(Transaction().user)
#        return user.address.email

    def default_state(self):
        return 'draft'

    def default_priority(self):
        return AVAILABLE_PRIORITIES[2][0],

    def default_date(self):
        return datetime.datetime.now()

    def _links_get(self):
        request_link_obj = self.pool.get('res.request.link')
        ids = request_link_obj.search([])
        request_links = request_link_obj.browse(ids)
        if request_links:
            return [(x.model, x.name) for x in request_links]

    def unlink(self, ids):
        for case in self.browse( ids):
            if (not case.section.allow_unlink) and (case.state <> 'draft'):
                self.raise_user_error('Warning !',
                    'You can not delete this case. You should better cancel it.')
        return super(crm_case, self).unlink( ids)

    def _action(self, cases, state_to, scrit=None):
        if not scrit:
            scrit = []
        action_ids = self.pool.get('ekd.crm.case.rule').search( scrit)
        level = MAX_LEVEL
        while len(action_ids) and level:
            newactions = []
            actions = self.pool.get('ekd.crm.case.rule').browse( action_ids)
            for case in cases:
                for action in actions:
                    ok = True
                    ok = ok and (not action.trg_state_from or action.trg_state_from==case.state)
                    ok = ok and (not action.trg_state_to or action.trg_state_to==state_to)
                    ok = ok and (not action.trg_section or action.trg_section.id==case.section.id)
                    ok = ok and (not action.trg_categ or action.trg_categ.id==case.categ.id)
                    ok = ok and (not action.trg_user.id or action.trg_user.id==case.user.id)
                    ok = ok and (not action.trg_party.id or action.trg_party.id==case.party.id)
                    ok = ok and (not action.trg_max_history or action.trg_max_history<=(len(case.history_line)+1))
                    ok = ok and (
                        not action.trg_party_categ.id or
                        (
                            case.party.id and
                            (action.trg_party_categ.id in map(lambda x: x.id, case.party.category or []))
                        )
                    )
                    ok = ok and (not action.trg_priority_from or action.trg_priority_from>=case.priority)
                    ok = ok and (not action.trg_priority_to or action.trg_priority_to<=case.priority)
                    if not ok:
                        continue

                    base = False
                    if action.trg_date_type=='create':
                        base = mx.DateTime.strptime(case.create_date[:19], '%Y-%m-%d %H:%M:%S')
                    elif action.trg_date_type=='action_last':
                        if case.date_action_last:
                            base = mx.DateTime.strptime(case.date_action_last, '%Y-%m-%d %H:%M:%S')
                        else:
                            base = mx.DateTime.strptime(case.create_date[:19], '%Y-%m-%d %H:%M:%S')
                    elif action.trg_date_type=='deadline' and case.date_deadline:
                        base = mx.DateTime.strptime(case.date_deadline, '%Y-%m-%d %H:%M:%S')
                    elif action.trg_date_type=='date' and case.date:
                        base = mx.DateTime.strptime(case.date, '%Y-%m-%d %H:%M:%S')
                    if base:
                        fnct = {
                            'minutes': lambda interval: mx.DateTime.RelativeDateTime(minutes=interval),
                            'day': lambda interval: mx.DateTime.RelativeDateTime(days=interval),
                            'hour': lambda interval: mx.DateTime.RelativeDateTime(hours=interval),
                            'month': lambda interval: mx.DateTime.RelativeDateTime(months=interval),
                        }
                        d = base + fnct[action.trg_date_range_type](action.trg_date_range)
                        dt = d.strftime('%Y-%m-%d %H:%M:%S')
                        ok = (dt <= time.strftime('%Y-%m-%d %H:%M:%S')) and \
                                ((not case.date_action_next) or \
                                (dt >= case.date_action_next and \
                                case.date_action_last < case.date_action_next))
                        if not ok:
                            if not case.date_action_next or dt < case.date_action_next:
                                case.date_action_next = dt
                                self.write( [case.id], {'date_action_next': dt})

                    else:
                        ok = action.trg_date_type=='none'

                    if ok:
                        write = {}
                        if action.act_state:
                            case.state = action.act_state
                            write['state'] = action.act_state
                        if action.act_section:
                            case.section = action.act_section
                            write['section'] = action.act_section.id
                        if action.act_user:
                            case.user = action.act_user
                            write['user'] = action.act_user.id
                        if action.act_priority:
                            case.priority = action.act_priority
                            write['priority'] = action.act_priority
                        if action.act_email_cc:
                            if '@' in (case.email_cc or ''):
                                emails = case.email_cc.split(",")
                                if  action.act_email_cc not in emails:# and '<'+str(action.act_email_cc)+">" not in emails:
                                    write['email_cc'] = case.email_cc+','+action.act_email_cc
                            else:
                                write['email_cc'] = action.act_email_cc
                        write['date_action_last'] = time.strftime('%Y-%m-%d %H:%M:%S')
                        self.write( [case.id], write)
                        caseobj = self.pool.get('ekd.crm.case')
                        if action.act_remind_user:
                            caseobj.remind_user( [case.id], context, attach=action.act_remind_attach)
                        if action.act_remind_party:
                            caseobj.remind_party( [case.id], context, attach=action.act_remind_attach)
                        if action.act_method:
                            getattr(caseobj, 'act_method')( [case.id], action)
                        emails = []
                        if action.act_mail_to_user:
                            if case.user and case.user.address:
                                emails.append(case.user.address.email)
                        if action.act_mail_to_party:
                            emails.append(case.email_from)
                        if action.act_mail_to_watchers:
                            emails += (action.act_email_cc or '').split(',')
                        if action.act_mail_to_email:
                            emails += (action.act_mail_to_email or '').split(',')
                        emails = filter(None, emails)
                        if len(emails) and action.act_mail_body:
                            emails = list(set(emails))
                            self.email_send( case, emails, action.act_mail_body)
                        break
            action_ids = newactions
            level -= 1
        return True

    def format_body(self, body):
        return (body or u'').encode('utf8', 'replace')

    def format_mail(self, case, body):
        data = {
            'case': case.id,
            'case_subject': case.name,
            'case_date': case.date,
            'case_description': case.description,

            'case_user': (case.user and case.user.name) or '/',
            'case_user_email': (case.user and case.user.address and case.user.address.email) or '/',
            'case_user_phone': (case.user and case.user.address and case.user.address.phone) or '/',

            'email_from': case.email_from,
            'party': (case.party and case.party.name) or '/',
            'party_email': (case.party_address and case.party_address.email) or '/',
        }
        return self.format_body(body % data)

    def email_send(self, case, emails, body):
        body = self.format_mail(case, body)
        if case.user and case.user.address and case.user.address.email:
            emailfrom = case.user.address.email
        else:
            emailfrom = case.section.reply_to
        name = '[%d] %s' % (case.id, case.name.encode('utf8'))
        reply_to = case.section.reply_to or False
        if reply_to: reply_to = reply_to.encode('utf8')
        if not emailfrom:
            self.raise_user_error("No E-Mail ID Found for your Company address or missing reply address in section!")
        tools.email_send(emailfrom, emails, name, body, reply_to=reply_to, tinycrm=str(case.id))
        return True

    def __log(self, cases, keyword):
        if not self.pool.get('ekd.party.event.type').check( 'crm_case_'+keyword):
            return False
        for case in cases:
            if case.party:
                translated_keyword = keyword
                #if 'translated_keyword' in context:
                #    translated_keyword = context['translated_keyword']
                name = 'Case' +  ' ' + translated_keyword + ': ' + case.name
                if isinstance(name, str):
                    name = unicode(name, 'utf-8')
                if len(name) > 64:
                    name = name[:61] + '...'
                self.pool.get('ekd.party.event').create( {
                    'name': name,
                    'som':(case.som or False) and case.som.id,
                    'description':case.description,
                    'party':case.party.id,
                    'date':time.strftime('%Y-%m-%d %H:%M:%S'),
                    'channel':(case.channel or False) and case.channel.id,
                    'user': Transaction().user,
                    'document': 'ekd.crm.case,%i' % case.id,
                })
        return True

    def __history(self, cases, keyword, history=False, email=False):
        for case in cases:
            data = {
                'name': keyword,
                'som': case.som.id,
                'channel': case.channel.id,
                'user': Transaction().user,
                'date': time.strftime('%Y-%m-%d %H:%M:%S'),
                'case': case.id,
                'section': case.section.id
            }
            obj = self.pool.get('ekd.crm.case.log')
            if history and case.description:
                obj = self.pool.get('ekd.crm.case.history')
                data['description'] = case.description
                data['email'] = email or \
                        (case.user and case.user.email) or \
                        (case.user.employee and case.user.employee.email) or False
            obj.create( data)
        return True

    _history = __history

    def create(self, *args, **argv):
        res = super(CrmCase, self).create( *args, **argv)
        cases = self.browse([res])
        cases[0].state # to fill the browse record cache
        self.__log(cases, 'draft')
        self._action(cases, 'draft')
        return res

    def button_remind_party(self, ids, attach=False):
        return self.button_remind_user( ids, attach, destination=False)

    def button_remind_user(self, ids, attach=False, destination=True):
        for case in self.browse( ids):
            if case.section.reply_to and case.email_from:
                src = case.email_from

                if not src:
                    self.raise_user_error("No E-Mail ID Found for the Responsible party or missing reply address in section!")

                dest = case.section.reply_to
                body = case.email_last or case.description
                if not destination:
                    src,dest = dest,src
                    if case.user.signature:
                        body += '\n\n%s' % (case.user.signature)
                dest = [dest]

                attach_to_send = None

                if attach:
                    attach_ids = self.pool.get('ir.attachment').search( [('res_model', '=', 'ekd.crm.case'), ('res_id', '=', case.id)])
                    attach_to_send = self.pool.get('ir.attachment').read( attach_ids, ['datas_fname','datas'])
                    attach_to_send = map(lambda x: (x['datas_fname'], base64.decodestring(x['datas'])), attach_to_send)

                # Send an email
                tools.email_send(
                    src,
                    dest,
                    "Reminder: [%s] %s" % (str(case.id), case.name, ),
                    self.format_body(body),
                    reply_to=case.section.reply_to,
                    tinycrm=str(case.id),
                    attach=attach_to_send
                )

        return True

    def button_add_reply(self, ids):
        for case in self.browse(ids):
            if case.history_line:
                description = case.history_line[0].description
                self.write(case.id, {
                    'description': '> ' + description.replace('\n','\n> '),
                    })
        return True

    def button_case_log(self, ids,context={}, email=False, *args):
        cases = self.browse( ids)
        self.__history( cases, 'Historize', history=True, email=email)
        return self.write( ids, {'description': False, 'som': False,
            'channel': False})

    def button_case_log_reply(self, ids, context={}, email=False, *args):
        cases = self.browse(ids)
        for case in cases:
            if not case.email_from:
                self.raise_user_error('You must put a party eMail to use this action!')
            if not case.user:
                self.raise_user_error('You must define a responsible user for this case in order to use this action!')
            if not case.description:
                self.raise_user_error('Can not send mail with empty body,you should have description in the body')
        self.__history( cases, 'Send', history=True, email=False)
        for case in cases:
            self.write( [case.id], {
                'description': False,
                'som': False,
                'channel': False,
                })
            emails = [case.email_from] + (case.email_cc or '').split(',')
            emails = filter(None, emails)
            body = case.description or ''
            if case.user.signature:
                body += '\n\n%s' % (case.user.signature)

            emailfrom = case.user and case.user.email or False
            if not emailfrom:
                self.raise_user_error("No E-Mail Found for your Company address!")
            #tools.email_send(
            #    emails,
            #    '['+str(case.id)+'] '+case.name,
            #    self.format_body(body),
            #    reply_to=case.section.reply_to,
            #    tinycrm=str(case.id)
            #)

            try:
                server = get_smtp_server()
                server.sendmail(emailfrom, emals, msg.as_string())
                server.quit()
                success = True
            except Exception:
                logging.getLogger('ekd_crm').error(
                    'Unable to deliver reply mail for event %s' % Exception)
        return True

    def on_change_party(self, ids, vals):
        if not vals:
            return {}
        #addr = self.pool.get('party.party').address_get( [part], ['contact'])
        #data = {'party_address':addr['contact']}
        #if addr['contact'] and not email:
        #    data['email_from'] = self.pool.get('ekd.party.address').browse( addr['contact']).email
        return {}

    def on_change_category(self, ids, vals):
        if not vals:
            return {}
        #cat = self.pool.get('ekd.crm.case.category').browse( categ).probability
        return {}

    def on_change_party_address(self, ids, vals):
        if not vals:
            return {}
        #data = {}
        #if not email:
        #    data['email_from'] = self.pool.get('party.party').browse(part).email
        return {}

    def button_case_close(self, ids, *args):
        cases = self.browse( ids)
        cases[0].state # to fill the browse record cache
        self.__log( cases, 'done')
        self.__history( cases, 'Close')
        self.write( ids, {'state':'done', 'date_closed': time.strftime('%Y-%m-%d %H:%M:%S')})
        #
        # We use the cache of cases to keep the old case state
        #
        self._action( cases, 'done')
        return True

    def button_case_escalate(self, ids, *args):
        cases = self.browse( ids)
        for case in cases:
            data = {'active':True, 'user': False}
            if case.section.parent:
                data['section'] = case.section.parent.id
                if case.section.parent.user:
                    data['user'] = case.section.parent.user.id
            else:
                self.raise_user_error('You can not escalate this case.\nYou are already at the top level.')
            self.write( ids, data)
        cases = self.browse( ids)
        self.__history( cases, 'Escalate')
        self._action( cases, 'escalate')
        return True

    def button_case_open(self, ids, *args):
        cases = self.browse( ids)
        self.__log( cases, 'open')
        self.__history( cases, 'Open')
        for case in cases:
            data = {'state':'open', 'active':True}
            if not case.user:
                data['user'] = Transaction().user
            self.write( ids, data)
        self._action( cases, 'open')
        return True

    def emails_get(self, id):
        case = self.browse( id)
        return ((case.user and case.user.email and case.user.employee.email) or False, case.email_from, case.email_cc, case.priority)

    def button_case_cancel(self, ids, *args):
        cases = self.browse( ids)
        cases[0].state # to fill the browse record cache
        self.__log( cases, 'cancel')
        self.__history( cases, 'Cancel')
        self.write( ids, {'state':'cancel', 'active':True})
        self._action( cases, 'cancel')
        return True

    def button_case_pending(self, ids, *args):
        cases = self.browse( ids)
        cases[0].state # to fill the browse record cache
        self.__log( cases, 'pending')
        self.__history( cases, 'Pending')
        self.write( ids, {'state':'pending', 'active':True})
        self._action( cases, 'pending')
        return True

    def button_case_reset(self, ids, *args):
        cases = self.browse( ids)
        cases[0].state # to fill the browse record cache
        self.__log( cases, 'draft')
        self.__history( cases, 'Draft')
        self.write( ids, {'state':'draft', 'active':True})
        self._action( cases, 'draft')
        return True

CrmCase()

class CrmCaseLog(ModelSQL, ModelView):
    _name = "ekd.crm.case.log"
    _description = "Case Communication History"

    name = fields.Char('Action', size=64)
    som = fields.Many2One('ekd.party.som', 'State of Mind')
    date = fields.DateTime('Date')
    channel = fields.Many2One('ekd.party.channel', 'Channel')
    section = fields.Many2One('ekd.crm.case.section', 'Section')
    user = fields.Many2One('res.user', 'User Responsible', readonly=True)
    case = fields.Many2One('ekd.crm.case', 'Case', required=True, ondelete='CASCADE')

    def __init__(self):
        super(CrmCaseLog, self).__init__()

    def default_date(self):
#        return time.strftime('%Y-%m-%d %H:%M:%S')
        return datetime.datetime.now()

CrmCaseLog()

class CrmCaseHistory(ModelSQL, ModelView):
    _name = "ekd.crm.case.history"
    _description = "Case history"
    _inherits = {'ekd.crm.case.log':"log"}

    description = fields.Text('Description')
    note = fields.Function(fields.Text("Description"), '_note_get')
    email = fields.Char('Email', size=84)
    log = fields.Many2One('ekd.crm.case.log', 'Log', ondelete='CASCADE')

    def __init__(self):
        super(CrmCaseHistory, self).__init__()

    def create(self, vals):
        if vals.has_key('case') and vals['case']:
            case_obj = self.pool.get('ekd.crm.case')
            cases = case_obj.browse([vals['case']])
            case_obj._action(cases, '')
        return super(CrmCaseHistory, self).create(vals)

    def _note_get(self, ids, name):
        res = {}
        for hist in self.browse(ids):
            res[hist.id] = (hist.email or '/') + ' (' + str(hist.date) + ')\n'
            res[hist.id] += (hist.description or '')
        return res

CrmCaseHistory()
