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
import time

#
# Sale/Purchase Channel, Media
#
class PartyChannel(ModelSQL, ModelView):
    _name = "ekd.party.channel"
    _description = "Channels"

    name = fields.Char('Channel Name', size=64, required=True)
    active = fields.Boolean('Active')

    def default_active(self):
        return True

PartyChannel()

#
# Party: State of Mind
#
class PartySOM(ModelSQL, ModelView):
    _name = "ekd.party.som"

    name = fields.Char('State of Mind',size=64, required=True)
    factor =  fields.Float('Factor', required=True)

PartySOM()

class PartyEvent(ModelSQL, ModelView):
    _name = "ekd.party.event"

    name = fields.Char('Events',size=64, required=True)
    som = fields.Many2One('ekd.party.som', 'State of Mind')
    description = fields.Text('Description')
    planned_cost = fields.Float('Planned Cost')
    planned_revenue = fields.Float('Planned Revenue')
    probability = fields.Float('Probability (0.50)')
    document = fields.Reference('Document', '_links_get')
    party = fields.Many2One('party.party', 'Party', select=True)
    date = fields.DateTime('Date')
    user = fields.Many2One('res.user', 'User')
    channel = fields.Many2One('ekd.party.channel', 'Channel')
    party_type = fields.Selection([
            ('customer','Customer'),
            ('retailer','Retailer'),
            ('prospect','Commercial Prospect')
            ], 'Party Relation')
    type = fields.Selection([
            ('sale','Sale Opportunity'),
            ('purchase','Purchase Offer'),
            ('prospect','Prospect Contact')
            ], 'Type of Event')
    event_ical = fields.Char('iCal id', size=64)

    _order = 'date desc'

    def default_date(self):
        return time.strftime('%Y-%m-%d %H:%M:%S')

    def _links_get(self):
        request_link_obj = self.pool.get('res.request.link')
        ids = request_link_obj.search([])
        request_links = request_link_obj.browse(ids)
        return [(x.model, x.name) for x in request_links]

PartyEvent()

class PartyEventType(ModelSQL, ModelView):
    _name = "ekd.party.event.type"
    _description = "Party Events"

    name = fields.Char('Event Type',size=64, required=True)
    key = fields.Char('Key', size=64, required=True)
    active = fields.Boolean('Active')

    def default_active(self):
        return True

    def check(self, key):
        return self.search([('key','=',key)])

PartyEventType()
